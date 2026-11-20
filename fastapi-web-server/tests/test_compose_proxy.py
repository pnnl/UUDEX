"""The compose stack's safety rules, read from the shipped files rather than from comments."""

import json
import re
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any

import pytest
import yaml

SERVER_DIR = Path(__file__).resolve().parents[1]

# Parsed YAML: the shape is checked by the tests below, so it is not typed further.
Doc = dict[str, Any]

PROXY_PORT = "${UUDEX_PROXY_BIND:-127.0.0.1}:8443:8443"
CERTS_DIR = "${UUDEX_CERTS_DIR:?set in .env.compose}"
PROXY_CERT_FILES = [f"{CERTS_DIR}/{name}" for name in ("ca.crt", "localhost.crt", "localhost.key")]
# Spelled out in full: a pattern would also accept names that do not exist.
TLS12_SUITES = {
    "TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256",
    "TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
    "TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256",
    "TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256",
}


# Compose is read as plain YAML: only Traefik matches keys case-insensitively.
def load(relative: str) -> Doc:
    return yaml.safe_load((SERVER_DIR / relative).read_text())


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses a key repeated in one mapping; PyYAML would keep the last."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        # Taken before the parent merges "<<" entries in, so an override of a merged key is fine.
        pairs = list(node.value)
        mapping = super().construct_mapping(node, deep=deep)
        seen: set[Any] = set()
        for key_node, _ in pairs:
            if key_node.tag == "tag:yaml.org,2002:merge":
                continue
            key = self.construct_object(key_node, deep=True)
            if key in seen:
                raise AssertionError(f"repeated key {ascii(key)}")
            seen.add(key)
        return mapping


def fold_keys(node: Any, source: str) -> Any:
    """Lower-case every mapping key, failing when two keys fold to the same name.

    Keys must be ASCII: Go folds some non-ASCII letters that Python's lower() leaves alone."""
    if isinstance(node, dict):
        folded: Doc = {}
        for key, value in node.items():
            if isinstance(key, str):
                assert key.isascii(), f"{source}: non-ASCII key {ascii(key)}"
            name = key.lower() if isinstance(key, str) else key
            assert name not in folded, f"{source}: keys differing only in case: {key!r}"
            folded[name] = fold_keys(value, source)
        return folded
    if isinstance(node, list):
        return [fold_keys(item, source) for item in node]
    return node


def parse_traefik(text: str, source: str) -> Doc:
    """Read Traefik YAML the way Traefik does: keys match case-insensitively and the
    file is rendered as a Go template, so a template action can rewrite what YAML shows.
    Every key in the result is lower case."""
    assert "{{" not in text, f"{source}: template syntax"
    try:
        document = yaml.load(text, Loader=UniqueKeyLoader)
    except AssertionError as error:
        raise AssertionError(f"{source}: {error}") from None
    assert isinstance(document, dict), f"{source}: document is not a mapping"
    return fold_keys(document, source)


def load_traefik(relative: str) -> Doc:
    return parse_traefik((SERVER_DIR / relative).read_text(), relative)


def ping_host(address: str) -> str:
    """The host part of a "host:port" address, without the brackets of an IPv6 literal."""
    host = address.rpartition(":")[0].removeprefix("[").removesuffix("]")
    assert host, f"ping address has no host: {address!r}"
    return host


def key_names(node: Any) -> set[str]:
    """Every mapping key at any depth, through lists as well."""
    if isinstance(node, dict):
        return set(node) | {name for value in node.values() for name in key_names(value)}
    if isinstance(node, list):
        return {name for item in node for name in key_names(item)}
    return set()


@pytest.fixture(scope="module")
def compose() -> Doc:
    return load("compose.yaml")


@pytest.fixture(scope="module")
def dynamic() -> Doc:
    return load_traefik("traefik/dynamic.yml")


@pytest.fixture(scope="module")
def static() -> Doc:
    return load_traefik("traefik/traefik.yml")


def proxy_app_address(compose: Doc) -> str:
    return compose["services"]["proxy"]["networks"]["app"]["ipv4_address"]


def mount_strings(service: Doc) -> list[str]:
    """Every source and target a service mounts, whichever volume syntax it uses."""
    found: list[str] = []
    for volume in service.get("volumes", []):
        if isinstance(volume, str):
            found.append(volume)
        else:
            found.extend(str(volume.get(key, "")) for key in ("source", "target"))
    return found


HELPER_REFUSALS = [
    pytest.param("Routers: {}\nrouters: {}\n", "keys differing only in case", id="case-collision"),
    pytest.param("a:\n  - B: 1\n    b: 2\n", "keys differing only in case", id="case-in-list-item"),
    pytest.param("a: '{{ x }}'\n", "template syntax", id="template"),
    # U+017F lower-cases to itself in Python but folds to "s" in Go.
    pytest.param("router\u017f: {}\n", r"non-ASCII key 'router\\u017f'", id="non-ascii-key"),
    pytest.param("routers: {}\nrouters: {}\n", "repeated key 'routers'", id="repeated-key"),
    pytest.param(
        "http:\n  middlewares: []\n  middlewares: [x]\n",
        "repeated key 'middlewares'",
        id="repeated-nested-key",
    ),
    pytest.param("a:\n  - k: 1\n    k: 2\n", "repeated key 'k'", id="repeated-key-in-list-item"),
    pytest.param("- a\n- b\n", "document is not a mapping", id="list-document"),
    pytest.param("", "document is not a mapping", id="empty-document"),
]


@pytest.mark.parametrize(("text", "message"), HELPER_REFUSALS)
def test_traefik_parser_refuses_ambiguous_files(text, message):
    with pytest.raises(AssertionError, match=message):
        parse_traefik(text, "sample.yml")


def test_traefik_parser_lowers_every_key_through_lists():
    parsed = parse_traefik("Http:\n  List:\n    - Inner: 1\n", "sample.yml")
    assert parsed == {"http": {"list": [{"inner": 1}]}}


def test_traefik_parser_allows_a_key_that_overrides_a_merged_one():
    parsed = parse_traefik("a: &x {k: 1}\nb:\n  <<: *x\n  k: 2\n", "sample.yml")
    assert parsed["b"] == {"k": 2}


@pytest.mark.parametrize(
    ("address", "host"),
    [("127.0.0.1:8082", "127.0.0.1"), ("[::1]:8082", "::1")],
)
def test_ping_host_drops_the_port_and_the_ipv6_brackets(address, host):
    assert ping_host(address) == host


@pytest.mark.parametrize("address", [":8082", "[]:8082", "8082"])
def test_ping_host_refuses_an_address_with_no_host(address):
    with pytest.raises(AssertionError, match="no host"):
        ping_host(address)


def test_key_names_walks_nested_mappings_and_lists():
    node = {"a": [{"b": {"c": 1}}, [{"d": 2}]], "e": 3}
    assert key_names(node) == {"a", "b", "c", "d", "e"}


def test_traefik_files_load_without_template_text_or_ambiguous_keys():
    for relative in ("traefik/dynamic.yml", "traefik/traefik.yml"):
        assert load_traefik(relative), relative


def test_dynamic_config_has_only_tls_options_and_the_one_client_cert_middleware(dynamic):
    assert set(dynamic) <= {"tls", "http"}, "only TLS options and HTTP routers may exist"
    # One middleware type only: any other could rewrite the identity header after it is set.
    assert dynamic["http"]["middlewares"] == {"client-cert": {"passtlsclientcert": {"pem": True}}}


def test_every_router_is_tls_only_on_websecure_with_the_client_cert_middleware(dynamic):
    routers = dynamic["http"]["routers"]
    assert routers
    for name, router in routers.items():
        assert "tls" in router, name
        # Any other middleware could set the identity header the app believes.
        assert router.get("middlewares") == ["client-cert"], name
        assert router.get("entrypoints") == ["websecure"], name
        assert router.get("tls", {}).get("options", "default") == "default", name


def test_every_client_must_present_a_certificate_from_the_mounted_ca(dynamic, compose):
    # A second option set could be picked by a router or an entrypoint.
    assert set(dynamic["tls"]["options"]) == {"default"}
    options = dynamic["tls"]["options"]["default"]
    assert options["clientauth"]["clientauthtype"] == "RequireAndVerifyClientCert"
    assert options["clientauth"]["cafiles"] == ["/certs/ca.crt"]
    targets = {v["target"] for v in compose["services"]["proxy"]["volumes"]}
    assert "/certs/ca.crt" in targets
    assert options["snistrict"] is True


def test_tls_floor_is_1_2_with_ecdhe_aead_suites_only(dynamic):
    options = dynamic["tls"]["options"]["default"]
    version = int(options["minversion"].removeprefix("VersionTLS"))
    assert version >= 12
    if version == 12:
        suites = options["ciphersuites"]
        assert len(suites) == len(set(suites))
        assert set(suites) == TLS12_SUITES, suites


def test_only_the_proxy_publishes_a_port_and_only_on_the_bind_address(compose):
    published = {n: s["ports"] for n, s in compose["services"].items() if "ports" in s}
    assert published == {"proxy": [PROXY_PORT]}


def test_no_service_mounts_the_ca_key_or_the_docker_socket(compose):
    for name, service in compose["services"].items():
        for text in mount_strings(service):
            assert "ca.key" not in text, (name, text)
            assert "docker.sock" not in text, (name, text)
    for secret in compose["secrets"].values():
        assert "ca.key" not in secret["file"]


def test_proxy_mounts_exactly_the_three_certificate_files(compose):
    volumes = compose["services"]["proxy"]["volumes"]
    assert sorted(volume["source"] for volume in volumes) == sorted(PROXY_CERT_FILES)


def test_proxy_loads_the_config_files_these_tests_read(compose, static):
    assert compose["configs"] == {
        "traefik_static": {"file": "./traefik/traefik.yml"},
        "traefik_dynamic": {"file": "./traefik/dynamic.yml"},
    }
    mounted = {c["source"]: c["target"] for c in compose["services"]["proxy"]["configs"]}
    assert mounted["traefik_static"] == "/etc/traefik/traefik.yml"
    assert static["providers"]["file"]["filename"] == mounted["traefik_dynamic"]


def test_every_proxy_bind_mount_is_read_only(compose):
    volumes = compose["services"]["proxy"]["volumes"]
    assert volumes
    for volume in volumes:
        assert not isinstance(volume, str), volume
        assert volume["type"] == "bind"
        assert volume["read_only"] is True, volume["target"]
        assert volume["bind"]["create_host_path"] is False, volume["target"]


def test_static_config_has_only_the_allowed_sections(static):
    # No "api" section and no docker provider: neither may appear in any spelling.
    allowed = {"global", "entrypoints", "ping", "providers", "log", "accesslog"}
    assert set(static) <= allowed


def test_static_providers_are_exactly_the_one_file_provider(static):
    providers = static["providers"]
    assert set(providers) == {"file"}
    assert set(providers["file"]) == {"filename"}


def test_static_entrypoints_are_the_tls_listener_and_a_loopback_ping(static):
    entrypoints = static["entrypoints"]
    assert set(entrypoints) == {"websecure", "ping"}
    assert set(entrypoints["websecure"]) == {"address"}, "no per-entrypoint TLS or http options"
    assert ip_address(ping_host(entrypoints["ping"]["address"])).is_loopback


def test_no_entrypoint_trusts_forwarded_headers_or_proxy_protocol(static):
    assert not {"forwardedheaders", "proxyprotocol"} & key_names(static["entrypoints"])


def test_proxy_cannot_enable_the_api_or_docker_provider_from_compose(compose):
    proxy = compose["services"]["proxy"]
    for key in ("command", "entrypoint", "environment", "env_file"):
        assert key not in proxy, key


def test_access_log_drops_request_headers(static):
    headers = static["accesslog"]["fields"]["headers"]
    assert headers["defaultmode"] == "drop"
    assert "keep" not in set(headers.get("names", {}).values())


def test_trusted_proxy_hosts_is_the_proxy_app_address(compose):
    env = compose["services"]["server"]["environment"]
    assert json.loads(env["TRUSTED_PROXY_HOSTS"]) == [proxy_app_address(compose)]


def test_server_address_agrees_across_bind_healthcheck_and_network(compose):
    server = compose["services"]["server"]
    address = server["networks"]["app"]["ipv4_address"]
    command = server["command"]
    assert command[command.index("--host") + 1] == address
    probe = server["healthcheck"]["test"][-1]
    assert re.search(rf"http://{re.escape(address)}:8000/", probe)


def test_fixed_addresses_sit_in_the_subnet_and_outside_the_dynamic_range(compose):
    config = compose["networks"]["app"]["ipam"]["config"][0]
    subnet = ip_network(config["subnet"])
    dynamic_range = ip_network(config["ip_range"])
    assert dynamic_range.subnet_of(subnet)
    server = compose["services"]["server"]["networks"]["app"]["ipv4_address"]
    for address in (server, proxy_app_address(compose)):
        assert ip_address(address) in subnet
        assert ip_address(address) not in dynamic_range


OVERLAYS = {"rabbitmq": "compose.rabbitmq.yaml", "kafka": "compose.kafka.yaml"}


@pytest.fixture(params=sorted(OVERLAYS))
def overlay(request) -> tuple[str, Doc]:
    return request.param, load(OVERLAYS[request.param])


def test_base_file_has_no_broker_and_includes_nothing(compose):
    assert not set(OVERLAYS) & set(compose["services"])
    assert "broker" not in compose["networks"]
    assert "include" not in compose


def test_overlay_adds_only_its_broker_and_the_server_block(overlay):
    broker, doc = overlay
    assert set(doc["services"]) == {broker, "server"}


def test_no_overlay_service_publishes_or_exposes_a_port_or_joins_the_host_network(overlay):
    _, doc = overlay
    for name, service in doc["services"].items():
        for key in ("ports", "expose", "network_mode"):
            assert key not in service, (name, key)


def test_overlay_network_is_only_the_internal_broker_network(overlay):
    _, doc = overlay
    assert doc["networks"] == {"broker": {"internal": True}}


def test_broker_joins_only_the_broker_network_with_a_digest_pinned_image(overlay):
    broker, doc = overlay
    service = doc["services"][broker]
    assert service["networks"] == ["broker"]
    assert re.fullmatch(r"[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}", service["image"]), service["image"]


def test_overlay_server_block_only_waits_for_the_broker_and_joins_its_network(overlay):
    broker, doc = overlay
    server = doc["services"]["server"]
    assert set(server) == {"depends_on", "networks"}
    assert server["depends_on"] == {broker: {"condition": "service_healthy"}}
    assert set(server["networks"]) == {"broker"}


def test_overlay_swaps_the_connection_secret_for_an_existing_example(overlay):
    broker, doc = overlay
    assert doc["secrets"]["messagebus_connection"] == {"file": f"./secrets/compose_{broker}_connection"}
    assert (SERVER_DIR / "secrets" / f"example.compose_{broker}_connection").is_file()


def test_rabbitmq_example_user_and_password_agree_between_its_two_secrets():
    fragment = (SERVER_DIR / "secrets/example.compose_rabbitmq_credentials").read_text()
    pairs = dict(re.findall(r"^(default_user|default_pass)\s*=\s*(\S+)\s*$", fragment, re.M))
    connection = (SERVER_DIR / "secrets/example.compose_rabbitmq_connection").read_text().strip()
    query = dict(re.findall(r"[?&](username|password)=([^&\s]+)", connection))
    assert set(pairs) == {"default_user", "default_pass"}
    assert query["username"] == pairs["default_user"]
    assert query["password"] == pairs["default_pass"]
