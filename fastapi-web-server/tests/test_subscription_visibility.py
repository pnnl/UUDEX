"""A subscription is visible only to its owner endpoint or an administrator (#48)."""

import uuid
from unittest.mock import Mock, patch

import pytest

import uudex_server.models as m
from conftest import identity_headers
from test_caller import trusted_client
from test_queue_stored_names import new_uuid, seed_link, seed_owner, seed_subscription
from test_repository_async import seed_endpoint
from test_subject_subscription_hardening import seed_subject
from uudex_server.routes import subscription_routes
from uudex_server.services.database_service import get_db_session


@pytest.fixture
def tag(setup_test_env):
    return f"v{uuid.uuid4().hex[:8]}"


async def seed_two_owners(tag: str) -> tuple[str, int]:
    """Owner `own-<tag>` holds a subscription and `other-<tag>` is a known non-owner."""
    await seed_owner(f"other-{tag}")
    _, endpoint_id = await seed_owner(f"own-{tag}")
    subscription_uuid = new_uuid()
    subscription_id = await seed_subscription(endpoint_id, subscription_uuid)
    return subscription_uuid, subscription_id


async def test_unknown_caller_gets_401_on_subscription_by_uuid(tag):
    subscription_uuid, _ = await seed_two_owners(tag)
    async with trusted_client() as c:
        response = await c.get(
            f"/subscription/{subscription_uuid}", headers=identity_headers(f"nobody-{tag}")
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized: Invalid certificate"


async def test_non_owner_gets_404_on_subscription_by_uuid_like_missing(tag):
    subscription_uuid, _ = await seed_two_owners(tag)
    async with trusted_client() as c:
        headers = identity_headers(f"other-{tag}")
        denied = await c.get(f"/subscription/{subscription_uuid}", headers=headers)
        missing = await c.get(f"/subscription/{new_uuid()}", headers=headers)
    assert denied.status_code == 404
    assert denied.json() == missing.json()
    assert subscription_uuid not in denied.text


async def test_non_owner_consume_gets_404_like_missing(tag):
    subscription_uuid, _ = await seed_two_owners(tag)
    async with trusted_client() as c:
        headers = identity_headers(f"other-{tag}")
        denied = await c.post(
            f"/subscription/{subscription_uuid}/consume", json={"count": 1}, headers=headers
        )
        missing = await c.post(
            f"/subscription/{new_uuid()}/consume", json={"count": 1}, headers=headers
        )
    assert denied.status_code == 404
    assert denied.json() == missing.json()
    assert subscription_uuid not in denied.text


async def test_owner_and_admin_get_the_subscription_by_uuid(tag):
    subscription_uuid, _ = await seed_two_owners(tag)
    await seed_owner(f"adm-{tag}", admin=True)
    async with trusted_client() as c:
        owner = await c.get(
            f"/subscription/{subscription_uuid}", headers=identity_headers(f"own-{tag}")
        )
        admin = await c.get(
            f"/subscription/{subscription_uuid}", headers=identity_headers(f"adm-{tag}")
        )
    for response in (owner, admin):
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["subscription_uuid"] == subscription_uuid
        assert body["subscription_name"] == "n"
        assert body["subscription_state"] == "ACTIVE"
        assert "owner_endpoint_id" in body


async def test_owner_consume_with_no_subjects_returns_empty_200(tag):
    subscription_uuid, _ = await seed_two_owners(tag)
    async with trusted_client() as c:
        response = await c.post(
            f"/subscription/{subscription_uuid}/consume",
            json={"count": 1},
            headers=identity_headers(f"own-{tag}"),
        )
    assert response.status_code == 200, response.text
    assert response.json()["total_consumed"] == 0
    assert response.json()["subscription_uuid"] == subscription_uuid


@pytest.mark.parametrize("who", ["own", "adm"])
async def test_owner_and_admin_consume_reaches_the_stored_queue_through_the_link(tag, who):
    participant, endpoint_id = await seed_owner(f"own-{tag}")
    await seed_owner(f"adm-{tag}", admin=True)
    subscription_uuid = new_uuid()
    subscription_id = await seed_subscription(endpoint_id, subscription_uuid)
    subject = await seed_subject(new_uuid(), participant, name="feeder")
    await seed_link(subject.subject_id, subscription_id, f"q_stored_{tag}")
    broker = Mock()
    broker.get_messages.return_value = []
    async with trusted_client() as c:
        with patch.object(subscription_routes, "message_broker_factory", lambda _: broker):
            response = await c.post(
                f"/subscription/{subscription_uuid}/consume",
                json={"count": 1},
                headers=identity_headers(f"{who}-{tag}"),
            )
    assert response.status_code == 200, response.text
    assert [call.args[0] for call in broker.get_messages.call_args_list] == [f"q_stored_{tag}"]


async def seed_linked_subscription(tag: str) -> tuple[str, int, int]:
    """Owner `own-<tag>` with a subscription linked to one subject: (uuid, participant, link subject id)."""
    participant, endpoint_id = await seed_owner(f"own-{tag}")
    subscription_uuid = new_uuid()
    subscription_id = await seed_subscription(endpoint_id, subscription_uuid)
    subject = await seed_subject(new_uuid(), participant, name="feeder")
    await seed_link(subject.subject_id, subscription_id, f"q_stored_{tag}")
    return subscription_uuid, participant, subject.subject_id


async def test_owner_and_admin_list_the_linked_subjects(tag):
    subscription_uuid, _, subject_id = await seed_linked_subscription(tag)
    await seed_owner(f"adm-{tag}", admin=True)
    async with trusted_client(raise_app_exceptions=False) as c:
        for who in ("own", "adm"):
            response = await c.get(
                f"/subscription/{subscription_uuid}/subjects",
                headers=identity_headers(f"{who}-{tag}"),
            )
            assert response.status_code == 200, response.text
            links = response.json()
            assert [link["subject_id"] for link in links] == [subject_id]
            assert links[0]["backing_queue_name"] == f"q_stored_{tag}"


async def test_non_owner_gets_404_on_subjects_like_missing(tag):
    subscription_uuid, _, _ = await seed_linked_subscription(tag)
    await seed_owner(f"other-{tag}")
    async with trusted_client(raise_app_exceptions=False) as c:
        headers = identity_headers(f"other-{tag}")
        denied = await c.get(f"/subscription/{subscription_uuid}/subjects", headers=headers)
        missing = await c.get(f"/subscription/{new_uuid()}/subjects", headers=headers)
    assert denied.status_code == 404
    assert denied.json() == missing.json()
    assert subscription_uuid not in denied.text


@pytest.mark.parametrize("suffix", ["", "/subjects", "/consume"])
async def test_second_endpoint_of_the_owners_participant_is_not_the_owner(tag, suffix):
    subscription_uuid, participant, _ = await seed_linked_subscription(tag)
    await seed_endpoint(participant, f"sib-{tag}")
    headers = identity_headers(f"sib-{tag}")
    async with trusted_client(raise_app_exceptions=False) as c:
        if suffix == "/consume":
            denied = await c.post(
                f"/subscription/{subscription_uuid}{suffix}", json={"count": 1}, headers=headers
            )
            missing = await c.post(
                f"/subscription/{new_uuid()}{suffix}", json={"count": 1}, headers=headers
            )
        else:
            denied = await c.get(f"/subscription/{subscription_uuid}{suffix}", headers=headers)
            missing = await c.get(f"/subscription/{new_uuid()}{suffix}", headers=headers)
    assert denied.status_code == 404
    assert denied.json() == missing.json()


async def test_inactive_owner_endpoint_gets_401(tag):
    subscription_uuid, endpoint_id = None, None
    _, endpoint_id = await seed_owner(f"own-{tag}")
    subscription_uuid = new_uuid()
    await seed_subscription(endpoint_id, subscription_uuid)
    async with get_db_session() as session:
        endpoint = await session.get(m.EndPoint, endpoint_id)
        assert endpoint is not None
        endpoint.active_sw = "N"
    async with trusted_client() as c:
        response = await c.get(
            f"/subscription/{subscription_uuid}", headers=identity_headers(f"own-{tag}")
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized: Invalid certificate"


async def test_non_uuid_path_value_gets_the_missing_404(tag):
    await seed_owner(f"own-{tag}")
    headers = identity_headers(f"own-{tag}")
    async with trusted_client() as c:
        odd = await c.get("/subscription/not-a-uuid", headers=headers)
        missing = await c.get(f"/subscription/{new_uuid()}", headers=headers)
    assert odd.status_code == 404
    assert odd.json() == missing.json()
