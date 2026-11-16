"""The caller is read from the certificate the verifying proxy forwards, and from nothing else."""

import base64
import logging
import uuid
from urllib.parse import unquote_plus

import pytest
from cryptography.hazmat.primitives import serialization

from conftest import (
    TRUSTED,
    UNTRUSTED,
    b64_der,
    ca_pair,
    client_from,
    forwarded_chain,
    identity_headers,
    make_leaf,
    seed_endpoint,
)
from uudex_server.core.client_cert import FORWARDED_CERT_HEADER, MAX_HEADER_CHARS
from uudex_server.main import INVALID_CERT_BODY, UNTRUSTED_PEER_BODY

NO_CERT_BODY = "No certificate detected."
NO_CN_BODY = "No Common Name found in certificate."
OLD_HEADERS = {
    "X-Client-Cert-Subject": "CN={cn},O=Test Org,C=US",
    "X-Client-Cert-Issuer": "CN=Test CA",
    "X-Client-Cert-Serial": "12345",
}


@pytest.fixture
def alice(setup_test_env):
    return f"alice-{uuid.uuid4().hex[:8]}"


def old_headers(cn: str) -> dict[str, str]:
    return {k: v.format(cn=cn) for k, v in OLD_HEADERS.items()}


def leaf_for(cn: str):
    return make_leaf([("CN", cn), ("O", "Test Org"), ("C", "US")])


async def get_me(peer: str, headers: dict[str, str] | list[tuple[str, str]]):
    async with client_from(peer) as c:
        return await c.get("/endpoint/me", headers=headers)


async def test_old_identity_headers_alone_never_name_the_caller(alice):
    await seed_endpoint(alice)
    response = await get_me(TRUSTED, old_headers(alice))
    assert (response.status_code, response.json()) == (401, NO_CERT_BODY)


async def test_old_headers_cannot_override_the_forwarded_certificate(alice):
    alice_uuid = await seed_endpoint(alice)
    victim = f"victim-{uuid.uuid4().hex[:8]}"
    victim_uuid = await seed_endpoint(victim)
    # The forwarded certificate says alice; the passed-through old headers claim the victim.
    response = await get_me(TRUSTED, identity_headers(alice) | old_headers(victim))
    assert response.status_code == 200
    assert response.json()["endpoint_uuid"] == alice_uuid != victim_uuid


async def test_forwarded_leaf_names_the_caller(alice):
    expected = await seed_endpoint(alice)
    response = await get_me(TRUSTED, {FORWARDED_CERT_HEADER: b64_der(leaf_for(alice))})
    assert response.status_code == 200
    assert response.json()["endpoint_uuid"] == expected


async def test_first_element_of_the_chain_is_the_leaf(alice):
    expected = await seed_endpoint(alice)
    response = await get_me(TRUSTED, {FORWARDED_CERT_HEADER: forwarded_chain(leaf_for(alice))})
    assert response.status_code == 200
    assert response.json()["endpoint_uuid"] == expected


async def test_a_ca_in_the_leaf_slot_never_becomes_the_caller(alice):
    ca_cn = "Test CA"
    await seed_endpoint(ca_cn)
    await seed_endpoint(alice)
    reversed_chain = f"{b64_der(ca_pair()[1])},{b64_der(leaf_for(alice))}"
    response = await get_me(TRUSTED, {FORWARDED_CERT_HEADER: reversed_chain})
    assert (response.status_code, response.json()) == (401, INVALID_CERT_BODY)


async def test_untrusted_peer_with_a_valid_forwarded_leaf_is_refused(alice):
    await seed_endpoint(alice)
    response = await get_me(UNTRUSTED, identity_headers(alice))
    assert (response.status_code, response.json()) == (401, UNTRUSTED_PEER_BODY)


async def test_base64_with_plus_and_slash_parses_unescaped(alice):
    expected = await seed_endpoint(alice)
    # Each random key gives a different base64 string; the cap keeps a bad run from hanging.
    for _ in range(200):
        value = b64_der(leaf_for(alice))
        if {"+", "/"} <= set(value):
            break
    else:
        pytest.fail("no generated certificate base64 held both '+' and '/'")
    # Control: URL-decoding this value would change it, so a 200 shows it was not decoded.
    assert unquote_plus(value) != value
    response = await get_me(TRUSTED, {FORWARDED_CERT_HEADER: value})
    assert response.status_code == 200
    assert response.json()["endpoint_uuid"] == expected


def _der(leaf) -> bytes:
    return leaf.public_bytes(serialization.Encoding.DER)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


SECRET = f"leak-{uuid.uuid4().hex}"
REFUSALS = {
    "empty": ("", NO_CERT_BODY, "empty"),
    "blank": ("   ", NO_CERT_BODY, "empty"),
    "leading_comma": ("," + _b64(b"x" * 40), NO_CERT_BODY, "empty"),
    "not_base64": ("not*base64*" + SECRET, INVALID_CERT_BODY, "not_base64"),
    "url_escaped": ("%41%42%43" + SECRET, INVALID_CERT_BODY, "not_base64"),
    "not_a_certificate": (_b64(SECRET.encode() * 8), INVALID_CERT_BODY, "not_certificate"),
    "truncated_der": (_b64(_der(leaf_for(SECRET))[:-40]), INVALID_CERT_BODY, "not_certificate"),
    "no_cn": (
        _b64(_der(make_leaf([("O", SECRET), ("C", "US")]))),
        NO_CN_BODY,
        "no_cn",
    ),
    "two_cns": (
        _b64(_der(make_leaf([("CN", SECRET + "-a"), ("CN", SECRET + "-b")]))),
        INVALID_CERT_BODY,
        "multiple_cn",
    ),
    "oversize": (
        forwarded_chain(leaf_for("big")) + "," + "A" * MAX_HEADER_CHARS,
        INVALID_CERT_BODY,
        "too_large",
    ),
}


@pytest.mark.parametrize(("value", "body", "reason"), REFUSALS.values(), ids=REFUSALS.keys())
async def test_unusable_forwarded_value_is_refused_with_a_reason_and_no_value_in_the_log(
    caplog, value, body, reason
):
    caplog.set_level(logging.DEBUG)
    response = await get_me(TRUSTED, {FORWARDED_CERT_HEADER: value})
    assert (response.status_code, response.json()) == (401, body)
    assert f"Refused client certificate: {reason}" in caplog.text
    assert SECRET not in caplog.text
    probe = value.strip(", ")
    assert len(probe) < 30 or probe[10:30] not in caplog.text


async def test_two_forwarded_header_lines_are_refused(alice, caplog):
    await seed_endpoint(alice)
    caplog.set_level(logging.DEBUG)
    value = b64_der(leaf_for(alice))
    response = await get_me(
        TRUSTED, [(FORWARDED_CERT_HEADER, value), (FORWARDED_CERT_HEADER, value)]
    )
    assert (response.status_code, response.json()) == (401, INVALID_CERT_BODY)
    assert "Refused client certificate: multiple_headers" in caplog.text
    assert value[10:30] not in caplog.text
