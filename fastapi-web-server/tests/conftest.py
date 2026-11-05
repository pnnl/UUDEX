import asyncio
import os
from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import AsyncClient

from uudex_server.core.settings import Settings, get_settings
from uudex_server.main import app
from uudex_server.services.database_service import init_db, shutdown_db


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_test_env(event_loop: asyncio.AbstractEventLoop) -> AsyncGenerator[None, None]:
    """Setup test environment before any tests run"""
    get_settings.cache_clear()  # Force settings reload

    # Create SQLite database
    await init_db()
    yield

    # Cleanup
    await shutdown_db()
    if os.path.exists("test.db"):
        os.remove("test.db")


@pytest.fixture(scope="session")
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


# Certificate fixtures
def read_cert_file(filename: str) -> str:
    """Read certificate from certs directory"""
    cert_path = os.path.join("certs", filename)
    with open(cert_path) as f:
        return f.read().strip()


@pytest.fixture
async def admin_headers():
    """Headers for admin user"""
    return {"x-ssl-cert": "-----BEGIN CERTIFICATE-----\nADMIN_TEST_CERT\n-----END CERTIFICATE-----"}


@pytest.fixture
async def non_admin_headers():
    """Headers for non-admin user"""
    return {"x-ssl-cert": "-----BEGIN CERTIFICATE-----\nUSER_TEST_CERT\n-----END CERTIFICATE-----"}


@pytest.fixture
async def invalid_cert_headers():
    """Headers with invalid certificate"""
    return {"x-ssl-cert": "-----BEGIN CERTIFICATE-----INVALID-----END CERTIFICATE-----"}


@pytest.fixture
async def missing_cert_headers():
    """Headers without certificate"""
    return {}
