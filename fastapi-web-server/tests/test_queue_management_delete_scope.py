"""Queue management delete only reaches queues stored on the subject's own links (#69)."""

import uuid
from unittest.mock import Mock

import pytest

from test_queue_stored_names import manage, seed_linked_subject, seed_owner
from test_subject_subscription_hardening import client_with


@pytest.fixture
def broker():
    fake = Mock()
    fake.delete_queue.return_value = 0
    return fake


@pytest.fixture
def tag(setup_test_env):
    return f"d{uuid.uuid4().hex[:8]}"


class TestOwnedQueueDelete:
    async def test_owner_deletes_a_queue_by_its_stored_name(self, tag, broker):
        participant, endpoint_id = await seed_owner(f"own-{tag}")
        subject, stored = await seed_linked_subject(participant, endpoint_id, "feeder")
        async with client_with(broker) as c:
            response = await manage(
                c, f"own-{tag}", subject.subject_uuid, action="delete", queue_name=stored
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["queue_info"]["deleted_queue"] == stored
        broker.delete_queue.assert_called_once_with(stored)

    async def test_an_unknown_name_is_404_with_no_broker_call(self, tag, broker):
        participant, endpoint_id = await seed_owner(f"own-{tag}")
        subject, _ = await seed_linked_subject(participant, endpoint_id, "feeder")
        async with client_with(broker) as c:
            response = await manage(
                c, f"own-{tag}", subject.subject_uuid, action="delete", queue_name="no-such-queue"
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subject not found"
        broker.delete_queue.assert_not_called()

    async def test_another_subjects_stored_name_is_404_with_no_broker_call(self, tag, broker):
        participant, endpoint_id = await seed_owner(f"own-{tag}")
        mine, _ = await seed_linked_subject(participant, endpoint_id, "mine")
        _, theirs = await seed_linked_subject(participant, endpoint_id, "theirs")
        async with client_with(broker) as c:
            response = await manage(
                c, f"own-{tag}", mine.subject_uuid, action="delete", queue_name=theirs
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subject not found"
        broker.delete_queue.assert_not_called()
