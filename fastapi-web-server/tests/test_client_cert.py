"""The caller is read from the certificate the verifying proxy forwards, and from nothing else."""

import base64
import logging
import uuid
from urllib.parse import unquote_plus

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

from conftest import (
    TRUSTED,
    UNTRUSTED,
    b64_der,
    ca_pair,
    client_from,
    forwarded_chain,
    identity_headers,
    key_usage,
    make_leaf,
    seed_endpoint,
)
from uudex_server.core.client_cert import (
    FORWARDED_CERT_HEADER,
    MAX_HEADER_CHARS,
    ClientCertError,
    parse_forwarded_cert,
)
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


BASIC_CONSTRAINTS_OID = bytes.fromhex("0603551d13")
KEY_USAGE_OID = bytes.fromhex("0603551d0f")
VERSION_3 = bytes.fromhex("a003020102")
VERSION_4 = bytes.fromhex("a003020103")


def _duplicate_extension_der() -> bytes:
    """A leaf whose extension list names KeyUsage twice (BasicConstraints retagged as it)."""
    leaf = make_leaf([("CN", "dup")], usage=key_usage(digital_signature=True))
    return _der(leaf).replace(BASIC_CONSTRAINTS_OID, KEY_USAGE_OID, 1)


def _version_4_der() -> bytes:
    """A leaf whose version field says 4, which X.509 does not define."""
    return _der(leaf_for("v4")).replace(VERSION_3, VERSION_4, 1)


def _bit_string_cn_der() -> bytes:
    """A leaf whose CN is a BIT STRING (tag 0x03), which only one attribute type may be."""
    cn_utf8 = bytes.fromhex("0c06") + b"\x00alice"
    der = _der(make_leaf([("CN", "\x00alice")]))
    assert der.count(cn_utf8) == 1
    return der.replace(cn_utf8, b"\x03" + cn_utf8[1:], 1)


def test_the_duplicate_extension_fixture_trips_the_library():
    with pytest.raises(x509.DuplicateExtension):
        x509.load_der_x509_certificate(_duplicate_extension_der()).extensions  # noqa: B018


def test_the_version_4_fixture_trips_the_library():
    with pytest.raises(x509.InvalidVersion):
        x509.load_der_x509_certificate(_version_4_der())


def test_the_bit_string_cn_fixture_trips_the_library():
    cert = x509.load_der_x509_certificate(_bit_string_cn_der())
    with pytest.raises(TypeError):
        cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)


SECRET = f"leak-{uuid.uuid4().hex}"
REFUSALS = {
    "empty": ("", NO_CERT_BODY, "empty"),
    "blank": ("   ", NO_CERT_BODY, "empty"),
    "only_a_comma": (",", INVALID_CERT_BODY, "empty_leaf"),
    "leading_comma_before_a_valid_leaf": (
        "," + b64_der(leaf_for("alice")),
        INVALID_CERT_BODY,
        "empty_leaf",
    ),
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
    "empty_cn": (_b64(_der(make_leaf([("CN", "")]))), NO_CN_BODY, "no_cn"),
    "blank_cn": (_b64(_der(make_leaf([("CN", "  \t ")]))), NO_CN_BODY, "no_cn"),
    "control_character_in_cn": (
        _b64(_der(make_leaf([("CN", SECRET + "\x07")]))),
        INVALID_CERT_BODY,
        "bad_cn",
    ),
    "newline_in_cn": (
        _b64(_der(make_leaf([("CN", SECRET + "\nadmin")]))),
        INVALID_CERT_BODY,
        "bad_cn",
    ),
    "ca_without_basic_constraints": (
        _b64(_der(make_leaf([("CN", SECRET)], is_ca=None, usage=key_usage(key_cert_sign=True)))),
        INVALID_CERT_BODY,
        "ca_as_leaf",
    ),
    "leaf_that_may_sign_certificates": (
        _b64(_der(make_leaf([("CN", SECRET)], usage=key_usage(key_cert_sign=True)))),
        INVALID_CERT_BODY,
        "ca_as_leaf",
    ),
    "duplicate_extension": (_b64(_duplicate_extension_der()), INVALID_CERT_BODY, "not_certificate"),
    "version_4": (_b64(_version_4_der()), INVALID_CERT_BODY, "not_certificate"),
    "bit_string_cn": (_b64(_bit_string_cn_der()), INVALID_CERT_BODY, "not_certificate"),
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


@pytest.mark.parametrize("usage", [None, key_usage(digital_signature=True, key_encipherment=True)])
async def test_a_client_certificate_without_basic_constraints_names_the_caller(alice, usage):
    # infrastructure/certs/generate-certs.sh signs clients with `openssl x509 -req` and no
    # extension file, so the real client certificate carries no BasicConstraints at all.
    expected = await seed_endpoint(alice)
    leaf = make_leaf([("CN", alice), ("O", "Test Org"), ("C", "US")], is_ca=None, usage=usage)
    assert not any(isinstance(e.value, x509.BasicConstraints) for e in leaf.extensions)
    response = await get_me(TRUSTED, {FORWARDED_CERT_HEADER: b64_der(leaf)})
    assert response.status_code == 200
    assert response.json()["endpoint_uuid"] == expected


def _padded_to(length: int, leaf_b64: str) -> str:
    return leaf_b64 + "," + "A" * (length - len(leaf_b64) - 1)


def test_a_value_of_exactly_the_size_limit_is_parsed():
    value = _padded_to(MAX_HEADER_CHARS, b64_der(leaf_for("alice")))
    assert len(value) == MAX_HEADER_CHARS
    assert parse_forwarded_cert(value).cn == "alice"


def test_a_value_one_over_the_size_limit_is_refused():
    value = _padded_to(MAX_HEADER_CHARS + 1, b64_der(leaf_for("alice")))
    assert len(value) == MAX_HEADER_CHARS + 1
    with pytest.raises(ClientCertError) as refused:
        parse_forwarded_cert(value)
    assert refused.value.reason == "too_large"
