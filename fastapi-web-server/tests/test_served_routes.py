import pytest
from fastapi.routing import APIRoute, iter_route_contexts

from uudex_server.main import app

# The 2024 API surface as served before the FastAPI upgrade. /v1 is not served.
EXPECTED_ROUTES = {
    ("DELETE", "/subject/{subject_id}"),
    ("GET", "/"),
    ("GET", "/dataset/{dataset_id}"),
    ("GET", "/dataset/{dataset_id}/download"),
    ("GET", "/datasets/"),
    ("GET", "/docs"),
    ("GET", "/endpoint/"),
    ("GET", "/endpoint/me"),
    ("GET", "/endpoint/{endpoint_id}"),
    ("GET", "/openapi.json"),
    ("GET", "/participants/"),
    ("GET", "/subject/uuid/{subject_uuid}"),
    ("GET", "/subject/{subject_id}"),
    ("GET", "/subject/{subject_uuid}/queue-info"),
    ("GET", "/subjects/"),
    ("GET", "/subjects/discover"),
    ("GET", "/subjects/with-metrics"),
    ("GET", "/subscription/{subscription_uuid}"),
    ("GET", "/subscription/{subscription_uuid}/subjects"),
    ("GET", "/subscriptions/"),
    ("GET", "/subscriptions/admin"),
    ("POST", "/datasets/"),
    ("POST", "/endpoint/"),
    ("POST", "/participants/"),
    ("POST", "/subject/{subject_uuid}/queue-management"),
    ("POST", "/subjects/"),
    ("POST", "/subjects/bulk-operations"),
    ("POST", "/subjects/{subject_uuid}/publish"),
    ("POST", "/subscription/"),
    ("POST", "/subscription/{subscription_uuid}/consume"),
    ("PUT", "/subject/{subject_id}"),
}


@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Shadow the database reset in conftest; these tests never touch the database."""
    yield


def served_routes() -> set[tuple[str, str]]:
    """Read through routing so routers that FastAPI includes lazily are counted."""
    return {
        (method, ctx.path)
        for ctx in iter_route_contexts(app.routes)
        if isinstance(ctx.original_route, APIRoute)
        for method in ctx.methods
    }


def test_served_routes_are_exactly_the_2024_surface():
    assert served_routes() == EXPECTED_ROUTES


def test_no_v1_path_is_served():
    assert [path for _, path in served_routes() if path.startswith("/v1")] == []
