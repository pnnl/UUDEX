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


def load(relative: str) -> Doc:
    return yaml.safe_load((SERVER_DIR / relative).read_text())


def fold_keys(node: Any, source: str) -> Any:
    """Lower-case every mapping key, failing when two keys fold to the same name."""
    if isinstance(node, dict):
        folded: Doc = {}
        for key, value in node.items():
            name = key.lower() if isinstance(key, str) else key
            assert name not in folded, f"{source}: keys differing only in case: {key!r}"
            folded[name] = fold_keys(value, source)
        return folded
    if isinstance(node, list):
        return [fold_keys(item, source) for item in node]
    return node


def load_traefik(relative: str) -> Doc:
    """Read a Traefik file the way Traefik does: keys match case-insensitively and the
    file is rendered as a Go template, so a template action can rewrite what YAML shows.
    Every key in the result is lower case."""
    text = (SERVER_DIR / relative).read_text()
    assert "{{" not in text, f"{relative}: template syntax"
    return fold_keys(yaml.safe_load(text), relative)


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


def test_traefik_files_are_plain_yaml_with_no_case_duplicates():
    for relative in ("traefik/dynamic.yml", "traefik/traefik.yml"):
        assert load_traefik(relative), relative


def test_every_router_carries_only_the_client_cert_middleware(dynamic):
    assert set(dynamic) <= {"tls", "http"}, "only TLS options and HTTP routers may exist"
    routers = dynamic["http"]["routers"]
    assert routers
    for name, router in routers.items():
        assert "tls" in router, name
        # Any other middleware could set the identity header the app believes.
        assert router.get("middlewares") == ["client-cert"], name
        assert router.get("entrypoints") == ["websecure"], name
        assert router.get("tls", {}).get("options", "default") == "default", name
    assert set(dynamic["http"]["middlewares"]) == {"client-cert"}
    assert dynamic["http"]["middlewares"]["client-cert"]["passtlsclientcert"]["pem"] is True


def test_every_client_must_present_a_certificate_from_the_mounted_ca(dynamic, compose):
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
    host = entrypoints["ping"]["address"].rpartition(":")[0]
    assert ip_address(host).is_loopback


def test_no_entrypoint_trusts_forwarded_headers_or_proxy_protocol(static):
    def names(node: Any) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {name for value in node.values() for name in names(value)}
        if isinstance(node, list):
            return {name for item in node for name in names(item)}
        return set()

    assert not {"forwardedheaders", "proxyprotocol"} & names(static["entrypoints"])


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
