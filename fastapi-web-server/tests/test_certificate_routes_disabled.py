import pytest
from fastapi import FastAPI
from starlette.routing import Match

from uudex_server.main import app
from uudex_server.routes.uudex_routes import certificates_router


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Shadow the database reset in conftest; these tests never touch the database."""
    yield


def resolves(target: FastAPI, method: str, path: str) -> bool:
    """True when some route fully matches; the auth middleware answers 401 before a 404 can show."""
    scope = {"type": "http", "method": method, "path": path}
    return any(route.matches(scope)[0] == Match.FULL for route in target.routes)


def test_resolver_detects_a_mounted_certificate_route():
    probe = FastAPI()
    probe.include_router(certificates_router)
    assert resolves(probe, "GET", "/certificates/") is True


@pytest.mark.parametrize("path", ["/certificates/", "/v1/certificates/"])
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_certificate_paths_do_not_resolve(method, path):
    assert resolves(app, method, path) is False


def test_openapi_lists_no_certificate_paths():
    assert [p for p in app.openapi()["paths"] if "certificates" in p] == []


def test_endpoint_routes_still_registered():
    paths = {getattr(r, "path", "") for r in app.routes}
    assert {"/endpoint/", "/endpoint/me", "/endpoint/{endpoint_id}"} <= paths
