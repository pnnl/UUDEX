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

EXPECTED_OPERATION_IDS = {
    ("DELETE", "/subject/{subject_id}"): "delete_subject",
    ("GET", "/"): "root__get",
    ("GET", "/dataset/{dataset_id}"): "get_dataset_by_id",
    ("GET", "/dataset/{dataset_id}/download"): "download_dataset",
    ("GET", "/datasets/"): "get_all_datasets",
    ("GET", "/endpoint/"): "get_all_endpoints",
    ("GET", "/endpoint/me"): "get_endpoint_user",
    ("GET", "/endpoint/{endpoint_id}"): "get_endpoint_by_id",
    ("GET", "/participants/"): "get_all_participants",
    ("GET", "/subject/uuid/{subject_uuid}"): "get_subject_by_uuid",
    ("GET", "/subject/{subject_id}"): "get_subject_by_id",
    ("GET", "/subject/{subject_uuid}/queue-info"): "get_subject_queue_info",
    ("GET", "/subjects/"): "get_all_subjects",
    ("GET", "/subjects/discover"): "discover_subjects",
    ("GET", "/subjects/with-metrics"): "get_subjects_with_metrics",
    ("GET", "/subscription/{subscription_uuid}"): "get_subscription_by_uuid",
    ("GET", "/subscription/{subscription_uuid}/subjects"): "get_subscription_subjects",
    ("GET", "/subscriptions/"): "get_user_subscriptions",
    ("GET", "/subscriptions/admin"): "get_admin_subscriptions",
    ("POST", "/datasets/"): "create_dataset",
    ("POST", "/endpoint/"): "create_endpoint",
    ("POST", "/participants/"): "create_participant",
    ("POST", "/subject/{subject_uuid}/queue-management"): "manage_subject_queues",
    ("POST", "/subjects/"): "create_subject",
    ("POST", "/subjects/bulk-operations"): "bulk_subject_operations",
    ("POST", "/subjects/{subject_uuid}/publish"): "publish_messages_to_subject",
    ("POST", "/subscription/"): "create_subscription",
    ("POST", "/subscription/{subscription_uuid}/consume"): "consume_messages",
    ("PUT", "/subject/{subject_id}"): "update_subject",
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


def test_operation_ids_are_the_route_names_generated_clients_depend_on():
    actual = {
        (method.upper(), path): operation["operationId"]
        for path, item in app.openapi()["paths"].items()
        for method, operation in item.items()
    }
    assert actual == EXPECTED_OPERATION_IDS
