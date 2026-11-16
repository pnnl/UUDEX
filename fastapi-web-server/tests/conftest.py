import base64
import datetime
import functools
import os
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import pytest_asyncio
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from httpx import ASGITransport, AsyncClient

import uudex_server.models as m
from uudex_server.core.client_cert import FORWARDED_CERT_HEADER
from uudex_server.core.settings import Settings, get_settings
from uudex_server.main import app
from uudex_server.repos import DatasetDefinitionRepository
from uudex_server.services.database_service import get_db_session, init_db, shutdown_db


@pytest_asyncio.fixture(scope="session")
async def setup_test_env() -> AsyncGenerator[None, None]:
    """Setup test environment before any tests run"""
    get_settings.cache_clear()  # Force settings reload

    # Create SQLite database
    await init_db()
    yield

    # Cleanup
    await shutdown_db()
    test_db = Path(__file__).parent / "test.db"
    if test_db.exists():
        test_db.unlink()


@pytest_asyncio.fixture(scope="session")
async def client(setup_test_env) -> AsyncGenerator[AsyncClient, None]:
    """Get async HTTP client for FastAPI testing"""
    # Use the transport parameter to connect to FastAPI app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Load test settings from env file"""
    return get_settings()


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Reset database to known state after each test"""
    yield  # Test runs here
    await init_db()  # Recreate tables after each test


@pytest_asyncio.fixture
async def dataset_definition_repo(
    setup_test_env,
) -> AsyncGenerator[DatasetDefinitionRepository, None]:
    """Repository bound to a session on the test database"""
    async with get_db_session() as session:
        yield DatasetDefinitionRepository(session)


# Certificate fixtures
def read_cert_file(filename: str) -> str:
    """Read certificate from certs directory"""
    cert_path = os.path.join("certs", filename)
    with open(cert_path) as f:
        return f.read().strip()


_NAME_OIDS = {"CN": NameOID.COMMON_NAME, "O": NameOID.ORGANIZATION_NAME, "C": NameOID.COUNTRY_NAME}


def _name(attrs: list[tuple[str, str]]) -> x509.Name:
    return x509.Name([x509.NameAttribute(_NAME_OIDS[key], value) for key, value in attrs])


def _build_cert(
    subject: x509.Name,
    issuer: x509.Name,
    public_key: ec.EllipticCurvePublicKey,
    signing_key: ec.EllipticCurvePrivateKey,
    *,
    is_ca: bool,
) -> x509.Certificate:
    now = datetime.datetime.now(datetime.UTC)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
        .sign(signing_key, hashes.SHA256())
    )


@functools.cache
def ca_pair() -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    """A CA made for the test session; no key or certificate file is kept."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = _name([("CN", "Test CA")])
    return key, _build_cert(name, name, key.public_key(), key, is_ca=True)


def make_leaf(attrs: list[tuple[str, str]]) -> x509.Certificate:
    """A leaf signed by the test CA, with exactly the subject attributes given."""
    ca_key, ca_cert = ca_pair()
    key = ec.generate_private_key(ec.SECP256R1())
    return _build_cert(_name(attrs), ca_cert.subject, key.public_key(), ca_key, is_ca=False)


def b64_der(cert: x509.Certificate) -> str:
    """The proxy's encoding of one certificate: plain base64 DER, not URL-escaped."""
    return base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode("ascii")


def forwarded_chain(leaf: x509.Certificate) -> str:
    """The forwarded header value for a verified leaf: the leaf, then the CA."""
    return f"{b64_der(leaf)},{b64_der(ca_pair()[1])}"


def identity_headers(cn: str | None = None, *, subject: str | None = None) -> dict[str, str]:
    """Identity headers as the verifying proxy sends them; the one place tests build them.

    `subject` is a comma-separated DN such as "CN=alice,O=Org"; an empty one means the
    proxy forwarded no certificate. Without a `subject`, `cn` is required.
    """
    if subject is None:
        if cn is None:
            raise ValueError("identity_headers needs a cn when no subject is given")
        subject = f"CN={cn},O=Test Org,C=US"
    if not subject:
        return {}
    attrs: list[tuple[str, str]] = []
    for part in subject.split(","):
        key, separator, value = part.strip().partition("=")
        if not separator:
            raise ValueError(f"subject part is not key=value: {part!r}")
        attrs.append((key, value))
    return {FORWARDED_CERT_HEADER: forwarded_chain(make_leaf(attrs))}


TRUSTED = "127.0.0.1"
UNTRUSTED = "10.1.2.3"


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
async def admin_headers():
    """Headers for admin user"""
    return identity_headers("admin")


@pytest.fixture
async def non_admin_headers():
    """Headers for non-admin user"""
    return identity_headers("user")


@pytest.fixture
async def invalid_cert_headers():
    """Headers whose subject carries no common name"""
    return identity_headers(subject="O=Test Org,C=US")


@pytest.fixture
async def missing_cert_headers():
    """Headers without certificate"""
    return {}
