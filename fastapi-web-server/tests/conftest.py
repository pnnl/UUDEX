import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient

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
    from httpx import ASGITransport

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


def identity_headers(cn: str | None = None, *, subject: str | None = None) -> dict[str, str]:
    """Identity headers as the verifying proxy sends them; the one place tests build them."""
    if subject is None:
        subject = f"CN={cn},O=Test Org,C=US"
    return {
        "X-Client-Cert-Subject": subject,
        "X-Client-Cert-Issuer": "CN=Test CA",
        "X-Client-Cert-Serial": "12345",
    }


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
