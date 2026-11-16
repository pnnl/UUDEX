"""The identity headers are believed only from a trusted proxy peer."""

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
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
BASE_SETTINGS = {
    "x_ssl_cert": "x",
    "postgres_dsn": "sqlite+aiosqlite:///x.db",
    "messagebus_connection": "rabbitmq://x",
}


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
    assert (trusted.status_code, trusted.json()) == (401, NO_IDENTITY_BODY)
    assert (untrusted.status_code, untrusted.json()) == (401, UNTRUSTED_PEER_BODY)


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


@contextmanager
def uvicorn_server(proxy_headers: bool) -> Iterator[int]:
    """Run the app under a real uvicorn server on a loopback port; yield the port."""
    with socket.socket() as sock:
        sock.bind((TRUSTED, 0))
        config = uvicorn.Config(app, lifespan="off", log_level="error", proxy_headers=proxy_headers)
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                assert time.monotonic() < deadline, "uvicorn did not start"
                time.sleep(0.01)
            yield sock.getsockname()[1]
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive(), "uvicorn thread did not stop"


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
    monkeypatch, proxy_headers, header, body
):
    monkeypatch.setattr(main.settings, "trusted_proxy_hosts", [ip_address(FORGED_CLAIM)])
    value = FORGED_CLAIM if header == "X-Forwarded-For" else f"for={FORGED_CLAIM}"
    with uvicorn_server(proxy_headers) as port:
        async with AsyncClient(base_url=f"http://{TRUSTED}:{port}") as c:
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
    assert '"--proxy-headers"' not in commands[0]


@pytest.mark.parametrize("name", ["README.md", "build_client.sh"])
def test_documented_uvicorn_start_commands_ignore_proxy_headers(name):
    commands = [
        line
        for line in (SERVER_DIR / name).read_text().splitlines()
        if "uvicorn " in line and "--port" in line
    ]
    assert len(commands) == 1
    assert " --no-proxy-headers" in commands[0]
    assert " --proxy-headers" not in commands[0]


def test_trusted_hosts_default_to_none(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HOSTS", raising=False)
    assert Settings(**BASE_SETTINGS).trusted_proxy_hosts == []


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


@pytest.mark.parametrize(
    "value",
    [
        "null",
        '"10.0.0.1"',
        "[2886749460]",
        "[null]",
        "[true]",
        '["::ffff:10.0.0.1"]',
        '["::ffff:a00:1"]',
        '["fe80::1%eth0"]',
    ],
)
def test_trusted_hosts_that_would_never_match_or_load_as_something_else_are_refused(value):
    with pytest.raises(ValidationError) as excinfo:
        Settings(**BASE_SETTINGS, trusted_proxy_hosts=value)
    messages = [error["msg"] for error in excinfo.value.errors()]
    assert len(messages) == 1
    assert "trusted_proxy_hosts" in messages[0]


@pytest.mark.parametrize("value", [None, 5, [2886749460], [None], ["::ffff:10.0.0.1"]])
def test_trusted_hosts_given_as_python_values_are_checked_too(value):
    with pytest.raises(ValidationError):
        Settings(**BASE_SETTINGS, trusted_proxy_hosts=value)


@pytest.mark.parametrize("value", ["[2886749460]", '["::ffff:10.0.0.1"]', '["fe80::1%eth0"]'])
def test_refused_trusted_hosts_in_the_environment_fail_at_load(monkeypatch, value):
    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", value)
    with pytest.raises((SettingsError, ValidationError)):
        Settings(**BASE_SETTINGS)


def test_a_null_in_the_environment_is_read_as_unset_and_so_trusts_no_peer(monkeypatch):
    # The environment source drops a decoded null before validation, so this is the unset
    # case, which the startup warning announces.
    monkeypatch.setenv("TRUSTED_PROXY_HOSTS", "null")
    assert Settings(**BASE_SETTINGS).trusted_proxy_hosts == []


@pytest.mark.parametrize("value", ["[]", '["10.0.0.1", "2001:db8::1"]'])
def test_plain_address_lists_still_load(value):
    hosts = Settings(**BASE_SETTINGS, trusted_proxy_hosts=value).trusted_proxy_hosts
    assert [str(h) for h in hosts] == json.loads(value)


async def call_asgi(scope_overrides: dict) -> tuple[int, bytes]:
    """Call the app with a hand-built HTTP scope; return the status and the body."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/endpoint/me",
        "raw_path": b"/endpoint/me",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in identity_headers("x").items()],
        "server": ("test", 80),
    } | scope_overrides
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body


async def test_a_request_with_no_client_address_is_refused():
    status, body = await call_asgi({"client": None})
    assert status == 401
    assert json.loads(body) == UNTRUSTED_PEER_BODY


async def test_the_asgi_control_with_a_trusted_client_passes_the_gate():
    status, body = await call_asgi({"client": (TRUSTED, 54321)})
    assert json.loads(body) != UNTRUSTED_PEER_BODY


def test_an_empty_trusted_list_logs_one_warning_naming_the_setting(caplog):
    caplog.set_level(logging.WARNING)
    main.warn_if_no_trusted_proxies([])
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "trusted_proxy_hosts" in warnings[0].getMessage()
    assert "refused" in warnings[0].getMessage()


def test_a_non_empty_trusted_list_logs_no_warning(caplog):
    caplog.set_level(logging.WARNING)
    main.warn_if_no_trusted_proxies([ip_address(TRUSTED)])
    assert caplog.records == []


def import_app_in_a_fresh_process(
    tmp_path: Path, trusted: str | None
) -> subprocess.CompletedProcess:
    """Import uudex_server.main as a server start would, with only the settings given here.

    The environment is built from nothing, and the settings file and secrets directory are
    named explicitly, so no .env or secrets directory of the developer is read.
    """
    secrets = tmp_path / "secrets"
    secrets.mkdir(exist_ok=True)
    env_file = tmp_path / "settings.env"
    env_file.write_text(
        "X_SSL_CERT=x\n"
        f"postgres_dsn=sqlite+aiosqlite:///{tmp_path}/x.db\n"
        "messagebus_connection=rabbitmq://x\n"
    )
    env = {
        "PYTHONPATH": os.pathsep.join([str(SERVER_DIR / "src"), *sys.path]),
        "PYTHONPYCACHEPREFIX": str(tmp_path / "pycache"),
        "UUDEX_SETTINGS": str(env_file),
        "UUDEX_SECRETS_DIR": str(secrets),
    }
    if trusted is not None:
        env["TRUSTED_PROXY_HOSTS"] = trusted
    return subprocess.run(
        [sys.executable, "-c", "import uudex_server.main"],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


SENTINEL = "sentinel-4f2a9c"


@pytest.mark.parametrize(
    "value",
    [f'["{SENTINEL}"]', f"{SENTINEL} garbage"],
    ids=["validation-error", "unparsable-environment-value"],
)
def test_a_bad_trusted_list_stops_startup_without_echoing_the_value(tmp_path, value):
    result = import_app_in_a_fresh_process(tmp_path, value)
    output = result.stdout + result.stderr
    assert result.returncode == 1
    # A deliberate exit, not a crash further on: the log names the setting, no traceback.
    assert "Traceback" not in output
    assert "trusted_proxy_hosts" in output
    assert SENTINEL not in output


def test_a_valid_trusted_list_starts_without_the_empty_warning(tmp_path):
    result = import_app_in_a_fresh_process(tmp_path, '["127.0.0.1"]')
    assert result.returncode == 0, result.stderr
    assert "Settings initialized successfully" in result.stdout
    assert "no peer is trusted" not in result.stdout + result.stderr


@pytest.mark.parametrize("value", ["[]", None], ids=["empty-list", "unset"])
def test_an_empty_trusted_list_is_announced_at_startup(tmp_path, value):
    result = import_app_in_a_fresh_process(tmp_path, value)
    assert result.returncode == 0, result.stderr
    assert "no peer is trusted" in result.stdout + result.stderr
