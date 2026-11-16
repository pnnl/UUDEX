"""Read the caller's identity from the client certificate the verifying proxy forwards."""

import base64
import binascii
import unicodedata
from dataclasses import dataclass

from cryptography import x509
from cryptography.x509.oid import NameOID

__all__ = [
    "FORWARDED_CERT_HEADER",
    "MAX_HEADER_CHARS",
    "ClientCert",
    "ClientCertError",
    "parse_forwarded_cert",
]

FORWARDED_CERT_HEADER = "X-Forwarded-Tls-Client-Cert"

# A leaf plus its CA is about 3 KiB of base64; 16 KiB leaves room for a long chain
# while stopping a client-sized body from reaching the base64 and DER parsers.
MAX_HEADER_CHARS = 16384


# The CN reaches the debug log and the endpoint lookup: refuse control, format, line and
# paragraph separator, private-use, surrogate and unassigned characters.
_BAD_CN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp", "Co", "Cs", "Cn"})


class ClientCertError(Exception):
    """The forwarded certificate cannot name a caller; `reason` is safe to log."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ClientCert:
    cn: str
    subject: str
    issuer: str
    serial: int


def parse_forwarded_cert(value: str | None) -> ClientCert:
    """Parse the leaf of a comma-separated, base64 DER chain (leaf first).

    The value is plain base64, not URL-escaped: decoding it as a URL would turn
    '+' into a space and corrupt the certificate.
    """
    if value is None:
        raise ClientCertError("absent")
    if len(value) > MAX_HEADER_CHARS:
        raise ClientCertError("too_large")
    if not value.strip():
        raise ClientCertError("empty")
    leaf_b64 = value.split(",", 1)[0].strip()
    if not leaf_b64:
        raise ClientCertError("empty_leaf")
    try:
        der = base64.b64decode(leaf_b64, validate=True)
    except (binascii.Error, ValueError):
        raise ClientCertError("not_base64") from None
    try:
        cert = x509.load_der_x509_certificate(der)
        extensions = cert.extensions
        try:
            is_ca = extensions.get_extension_for_class(x509.BasicConstraints).value.ca
        except x509.ExtensionNotFound:
            # generate-certs.sh signs client certificates with no extensions at all.
            is_ca = False
        try:
            may_sign_certs = extensions.get_extension_for_class(x509.KeyUsage).value.key_cert_sign
        except x509.ExtensionNotFound:
            may_sign_certs = False
        names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        subject = cert.subject.rfc4514_string()
        issuer = cert.issuer.rfc4514_string()
        serial = cert.serial_number
    except Exception:
        # cryptography has no common base class for a bad certificate; every failure here is one.
        raise ClientCertError("not_certificate") from None
    # The proxy sends the leaf first; a CA in that slot means a wrong order, never a caller.
    # A CA without BasicConstraints still declares itself through KeyUsage.
    if is_ca or may_sign_certs:
        raise ClientCertError("ca_as_leaf")
    if not names:
        raise ClientCertError("no_cn")
    if len(names) > 1:
        raise ClientCertError("multiple_cn")
    cn = names[0].value
    if not isinstance(cn, str) or not cn.strip():
        raise ClientCertError("no_cn")
    if cn != cn.strip() or any(unicodedata.category(char) in _BAD_CN_CATEGORIES for char in cn):
        raise ClientCertError("bad_cn")
    return ClientCert(cn=cn, subject=subject, issuer=issuer, serial=serial)
