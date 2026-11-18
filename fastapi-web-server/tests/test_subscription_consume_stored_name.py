"""Consume reads the queue names stored on the subscription's links (#69)."""

import uuid
from unittest.mock import Mock, patch

import pytest

from conftest import identity_headers
from test_queue_stored_names import new_uuid, seed_link, seed_owner, seed_subscription
from test_subject_subscription_hardening import client_with, seed_subject
from uudex_server.routes import subscription_routes


@pytest.fixture
def broker():
    fake = Mock()
    fake.get_messages.return_value = []
    return fake


@pytest.fixture
def tag(setup_test_env):
    return f"c{uuid.uuid4().hex[:8]}"


async def test_consume_reads_each_stored_name_after_a_rename(tag, broker):
    participant, endpoint_id = await seed_owner(f"own-{tag}")
    subscription_uuid = new_uuid()
    subscription_id = await seed_subscription(endpoint_id, subscription_uuid)
    a = await seed_subject(new_uuid(), participant, name="feeder")
    b = await seed_subject(new_uuid(), participant, name="grid")
    stored = {a.subject_id: f"q_legacy_{tag}_a", b.subject_id: f"q_legacy_{tag}_b"}
    for subject_id, name in stored.items():
        await seed_link(subject_id, subscription_id, name)
    async with client_with(broker) as c:
        await c.put(
            f"/subject/{a.subject_id}",
            json={"subject_name": "renamed"},
            headers=identity_headers(f"own-{tag}"),
        )
        with patch.object(subscription_routes, "message_broker_factory", lambda _: broker):
            response = await c.post(
                f"/subscription/{subscription_uuid}/consume",
                json={"count": 2, "timeout": 5},
                headers=identity_headers(f"own-{tag}"),
            )
    assert response.status_code == 200, response.text
    assert sorted(call.args[0] for call in broker.get_messages.call_args_list) == sorted(
        stored.values()
    )
