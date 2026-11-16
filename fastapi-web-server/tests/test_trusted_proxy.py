"""The identity headers are believed only from a trusted proxy peer."""

import logging
import socket
import threading
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from ipaddress import ip_address
from pathlib import Path

import pytest
import uvicorn
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from pydantic_settings import SettingsError

import uudex_server.main as main
import uudex_server.models as m
from conftest import identity_headers
from uudex_server.core.settings import Settings
from uudex_server.main import UNTRUSTED_PEER_BODY, app
from uudex_server.services.database_service import get_db_session

TRUSTED = "127.0.0.1"
UNTRUSTED = "10.1.2.3"
FORGED_CLAIM = "10.9.9.9"
NO_IDENTITY_BODY = "No certificate detected."
SERVER_DIR = Path(__file__).resolve().parents[1]


@asynccontextmanager
async def client_from(peer: str):
    """A client whose TCP peer, as the app sees it, is `peer`."""
    transport = ASGITransport(app=app, client=(peer, 54321))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def seed_endpoint(cn: str) -> str:
    """Create an active participant and endpoint for `cn`; return the endpoint_uuid."""
    endpoint_uuid = str(uuid.uuid4())
    async with get_db_session() as session:
        participant = m.Participant(
            participant_uuid=str(uuid.uuid4()),
            participant_short_name="p",
            participant_long_name="p",
            root_org_sw="N",
            create_datetime=None,
        )
        session.add(participant)
        await session.flush()
        session.add(
            m.EndPoint(
                endpoint_uuid=endpoint_uuid,
                endpoint_user_name=cn,
                certificate_dn=cn,
                description="seeded for the trusted proxy tests",
                uudex_administrator_sw="N",
                participant_administrator_sw="N",
                participant_id=participant.participant_id,
                create_datetime=None,
            )
        )
    return endpoint_uuid


@pytest.fixture
def alice(setup_test_env):
    return f"alice-{uuid.uuid4().hex[:8]}"


async def test_untrusted_peer_with_valid_identity_is_refused(alice):
    await seed_endpoint(alice)
    async with client_from(UNTRUSTED) as c:
        response = await c.get("/endpoint/me", headers=identity_headers(alice))
    assert response.status_code == 401
    assert response.json() == UNTRUSTED_PEER_BODY


async def test_trusted_peer_with_valid_identity_gets_the_endpoint(alice):
    expected = await seed_endpoint(alice)
    async with client_from(TRUSTED) as c:
        response = await c.get("/endpoint/me", headers=identity_headers(alice))
    assert response.status_code == 200
    assert response.json()["endpoint_uuid"] == expected


async def test_forged_forwarded_header_does_not_make_an_untrusted_peer_trusted(alice):
    await seed_endpoint(alice)
    headers = identity_headers(alice) | {"X-Forwarded-For": TRUSTED}
    async with client_from(UNTRUSTED) as c:
        response = await c.get("/endpoint/me", headers=headers)
    assert response.status_code == 401
    assert response.json() == UNTRUSTED_PEER_BODY


@pytest.mark.parametrize("peer", [TRUSTED, UNTRUSTED, "::1"])
async def test_empty_trusted_list_refuses_every_peer(monkeypatch, alice, peer):
    await seed_endpoint(alice)
    monkeypatch.setattr(main.settings, "trusted_proxy_hosts", [])
    async with client_from(peer) as c:
        response = await c.get("/endpoint/me", headers=identity_headers(alice))
    assert response.status_code == 401
    assert response.json() == UNTRUSTED_PEER_BODY


@pytest.mark.parametrize("peer", ["not-an-address", "", "999.1.1.1"])
async def test_unparsable_peer_is_refused(peer):
    async with client_from(peer) as c:
        response = await c.get("/endpoint/me", headers=identity_headers("x"))
    assert response.status_code == 401
    assert response.json() == UNTRUSTED_PEER_BODY


async def test_mapped_ipv6_peer_is_judged_by_its_ipv4_address():
    async with client_from(f"::ffff:{TRUSTED}") as c:
        trusted = await c.get("/endpoint/me")
    async with client_from(f"::ffff:{UNTRUSTED}") as c:
        untrusted = await c.get("/endpoint/me")
    assert trusted.json() == NO_IDENTITY_BODY
    assert untrusted.json() == UNTRUSTED_PEER_BODY


@pytest.mark.parametrize("path", ["/docsx", "/openapi.jsonx", "/docs/", "/statusx", "/health"])
async def test_only_exact_public_paths_skip_the_gate(path):
    async with client_from(UNTRUSTED) as c:
        untrusted = await c.get(path)
    async with client_from(TRUSTED) as c:
        trusted = await c.get(path)
    assert (untrusted.status_code, untrusted.json()) == (401, UNTRUSTED_PEER_BODY)
    assert (trusted.status_code, trusted.json()) == (401, NO_IDENTITY_BODY)


@pytest.mark.parametrize("path", ["/openapi.json", "/docs"])
async def test_exact_public_paths_are_open_to_any_peer(path):
    async with client_from(UNTRUSTED) as c:
        response = await c.get(path)
    assert response.status_code == 200


async def test_refusal_log_has_the_peer_and_no_header_value(caplog):
    secret = f"CN=leak-{uuid.uuid4().hex}"
    headers = identity_headers(subject=secret) | {"X-Client-Cert-Serial": "serial-" + secret[-12:]}
    caplog.set_level(logging.DEBUG)
    async with client_from(UNTRUSTED) as c:
        await c.get("/endpoint/me", headers=headers)
    assert UNTRUSTED in caplog.text
    for value in (secret, secret[-12:], "Test CA"):
        assert value not in caplog.text


class UvicornServer:
    """The app under a real uvicorn server on a loopback port."""

    def __init__(self, proxy_headers: bool):
        self.sock = socket.socket()
        self.sock.bind((TRUSTED, 0))
        self.port = self.sock.getsockname()[1]
        config = uvicorn.Config(app, lifespan="off", log_level="error", proxy_headers=proxy_headers)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.sock]})

    def __enter__(self):
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            assert time.monotonic() < deadline, "uvicorn did not start"
            time.sleep(0.01)
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=10)
        self.sock.close()


@pytest.fixture
def uvicorn_server() -> Callable[[bool], UvicornServer]:
    return UvicornServer


# The real peer is 127.0.0.1, which uvicorn trusts by default. The forged claim is the only
# address in the list, so a 401 identity answer (not the gate's) means the gate was fooled.
@pytest.mark.parametrize(
    ("proxy_headers", "header", "body"),
    [
        (True, "X-Forwarded-For", NO_IDENTITY_BODY),
        (False, "X-Forwarded-For", UNTRUSTED_PEER_BODY),
        (False, "Forwarded", UNTRUSTED_PEER_BODY),
        (True, "Forwarded", UNTRUSTED_PEER_BODY),
    ],
)
async def test_uvicorn_proxy_headers_decide_whether_a_forged_claim_works(
    monkeypatch, uvicorn_server, proxy_headers, header, body
):
    monkeypatch.setattr(main.settings, "trusted_proxy_hosts", [ip_address(FORGED_CLAIM)])
    value = FORGED_CLAIM if header == "X-Forwarded-For" else f"for={FORGED_CLAIM}"
    with uvicorn_server(proxy_headers) as server:
        async with AsyncClient(base_url=f"http://{TRUSTED}:{server.port}") as c:
            response = await c.get("/endpoint/me", headers={header: value})
    assert response.status_code == 401
    assert response.json() == body


@pytest.mark.parametrize("name", ["Dockerfile", "compose.yaml"])
def test_shipped_uvicorn_commands_ignore_proxy_headers(name):
    commands = [
        line for line in (SERVER_DIR / name).read_text().splitlines() if '"uvicorn"' in line
    ]
    assert len(commands) == 1
    assert '"--no-proxy-headers"' in commands[0]


def test_trusted_hosts_default_to_none(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOSTS", raising=False)
    assert Settings(**BASE_SETTINGS).trusted_proxy_hosts == []


BASE_SETTINGS = {
    "x_ssl_cert": "x",
    "postgres_dsn": "sqlite+aiosqlite:///x.db",
    "messagebus_connection": "rabbitmq://x",
}


@pytest.mark.parametrize("value", ['["not-an-ip"]', "[1.2.3", '["10.0.0.1", "10.0.0.256"]', "{}"])
def test_malformed_trusted_hosts_fail_at_load(value):
    with pytest.raises(ValidationError):
        Settings(**BASE_SETTINGS, trusted_proxy_hosts=value)


@pytest.mark.parametrize("value", ["garbage", "", '["10.0.0.256"]'])
def test_malformed_trusted_hosts_in_the_environment_fail_at_load(monkeypatch, value):
    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", value)
    with pytest.raises((SettingsError, ValidationError)):
        Settings(**BASE_SETTINGS)


def test_trusted_hosts_parse_from_a_json_list(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", '["172.29.77.20", "::1"]')
    hosts = Settings(**BASE_SETTINGS).trusted_proxy_hosts
    assert [str(h) for h in hosts] == ["172.29.77.20", "::1"]
