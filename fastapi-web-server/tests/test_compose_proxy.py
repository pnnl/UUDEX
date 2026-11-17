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
AEAD_ECDHE_SUITE = re.compile(
    r"^TLS_ECDHE_(RSA|ECDSA)_WITH_(AES_(128|256)_GCM_SHA\d+|CHACHA20_POLY1305_SHA256)$"
)


def load(relative: str) -> Doc:
    return yaml.safe_load((SERVER_DIR / relative).read_text())


@pytest.fixture(scope="module")
def compose() -> Doc:
    return load("compose.yaml")


@pytest.fixture(scope="module")
def dynamic() -> Doc:
    return load("traefik/dynamic.yml")


@pytest.fixture(scope="module")
def static() -> Doc:
    return load("traefik/traefik.yml")


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


def test_every_router_carries_the_client_cert_middleware(dynamic):
    routers = dynamic["http"]["routers"]
    assert routers
    for name, router in routers.items():
        assert "client-cert" in router.get("middlewares", []), name
        assert router.get("tls", {}).get("options", "default") == "default", name
    assert dynamic["http"]["middlewares"]["client-cert"]["passTLSClientCert"]["pem"] is True


def test_every_client_must_present_a_certificate_from_the_mounted_ca(dynamic, compose):
    options = dynamic["tls"]["options"]["default"]
    assert options["clientAuth"]["clientAuthType"] == "RequireAndVerifyClientCert"
    assert options["clientAuth"]["caFiles"] == ["/certs/ca.crt"]
    targets = {v["target"] for v in compose["services"]["proxy"]["volumes"]}
    assert "/certs/ca.crt" in targets
    assert options["sniStrict"] is True


def test_tls_floor_is_1_2_with_ecdhe_aead_suites_only(dynamic):
    options = dynamic["tls"]["options"]["default"]
    version = int(options["minVersion"].removeprefix("VersionTLS"))
    assert version >= 12
    if version == 12:
        suites = options["cipherSuites"]
        assert suites
        assert all(AEAD_ECDHE_SUITE.match(suite) for suite in suites), suites


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


def test_every_proxy_bind_mount_is_read_only(compose):
    volumes = compose["services"]["proxy"]["volumes"]
    assert volumes
    for volume in volumes:
        assert not isinstance(volume, str), volume
        assert volume["type"] == "bind"
        assert volume["read_only"] is True, volume["target"]
        assert volume["bind"]["create_host_path"] is False, volume["target"]


def test_static_config_enables_neither_the_api_nor_the_docker_provider(static):
    assert "api" not in static
    assert set(static["providers"]) == {"file"}


def test_proxy_cannot_enable_the_api_or_docker_provider_from_compose(compose):
    proxy = compose["services"]["proxy"]
    for key in ("command", "entrypoint", "environment", "env_file"):
        assert key not in proxy, key


def test_access_log_drops_request_headers(static):
    headers = static["accessLog"]["fields"]["headers"]
    assert headers["defaultMode"] == "drop"
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
