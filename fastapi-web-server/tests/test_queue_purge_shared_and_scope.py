"""Purge, consume and delete edge cases around stored queue names (#69)."""

import uuid
from unittest.mock import Mock

import pytest

from conftest import identity_headers
from test_queue_stored_names import (
    manage,
    new_uuid,
    seed_link,
    seed_linked_subject,
    seed_owner,
    seed_subscription,
)
from test_subject_subscription_hardening import client_with, seed_subject


@pytest.fixture
def broker():
    fake = Mock()
    fake.delete_queue.return_value = 0
    return fake


@pytest.fixture
def tag(setup_test_env):
    return f"s{uuid.uuid4().hex[:8]}"


async def seed_shared_and_own(tag: str):
    """Two owners; subject a stores a name shared with b, plus one name of its own."""
    p1, e1 = await seed_owner(f"p1-{tag}")
    p2, e2 = await seed_owner(f"p2-{tag}")
    shared = f"q_legacy_shared_{tag}"
    own = f"q_legacy_own_{tag}"
    a, _ = await seed_linked_subject(p1, e1, "feeder", shared)
    await seed_link(a.subject_id, await seed_subscription(e1, new_uuid()), own)
    await seed_linked_subject(p2, e2, "feeder", shared)
    return a, shared, own


class TestPurgeSkipsSharedNames:
    async def test_single_purge_does_not_delete_a_shared_queue(self, tag, broker):
        a, shared, own = await seed_shared_and_own(tag)
        async with client_with(broker) as c:
            response = await manage(c, f"p1-{tag}", a.subject_uuid, action="purge")
        body = response.json()
        assert response.status_code == 200, response.text
        assert body["success"] is False
        assert body["queue_info"]["purged_queues"] == [own]
        assert body["queue_info"]["failed_queues"] == [shared]
        assert "shared with another subject" in body["message"]
        assert [call.args[0] for call in broker.delete_queue.call_args_list] == [own]

    async def test_bulk_purge_does_not_delete_a_shared_queue(self, tag, broker):
        a, shared, own = await seed_shared_and_own(tag)
        await seed_owner(f"adm-{tag}", admin=True)
        async with client_with(broker) as c:
            response = await c.post(
                "/subjects/bulk-operations",
                json={"subject_uuids": [a.subject_uuid], "operation": "purge_queues"},
                headers=identity_headers(f"adm-{tag}"),
            )
        body = response.json()
        assert response.status_code == 200, response.text
        assert body["successful"] == []
        assert len(body["failed"]) == 1
        assert body["failed"][0]["subject_uuid"] == a.subject_uuid
        assert shared in body["failed"][0]["error"]
        assert "shared with another subject" in body["failed"][0]["error"]
        assert [call.args[0] for call in broker.delete_queue.call_args_list] == [own]


class TestDeleteWithoutName:
    @pytest.mark.parametrize("body", [{"action": "delete"}, {"action": "delete", "queue_name": ""}])
    async def test_a_delete_without_a_queue_name_is_400(self, tag, broker, body):
        participant, endpoint_id = await seed_owner(f"own-{tag}")
        a, _ = await seed_linked_subject(participant, endpoint_id, "feeder")
        async with client_with(broker) as c:
            response = await manage(c, f"own-{tag}", a.subject_uuid, **body)
        assert response.status_code == 400
        assert response.json()["detail"] == "Unsupported action: delete"
        broker.delete_queue.assert_not_called()
