"""Consume reads the queue names stored on the subscription's links (#69)."""

import uuid
from unittest.mock import Mock, patch

import pytest
from pyrabbit2 import api as pyrabbit_api
from pyrabbit2 import http as pyrabbit_http

from conftest import identity_headers
from test_queue_stored_names import new_uuid, seed_link, seed_owner, seed_subscription
from test_subject_subscription_hardening import client_with, seed_subject
from uudex_server.routes import subscription_routes
from uudex_server.services.message_services.base import BrokerError
from uudex_server.services.message_services.rabbit_mq import RabbitMqService


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
        renamed = await c.put(
            f"/subject/{a.subject_id}",
            json={"subject_name": "renamed"},
            headers=identity_headers(f"own-{tag}"),
        )
        assert renamed.status_code == 200, renamed.text
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


async def _consume_two_queues(tag, broker):
    """Seed a subscription with two linked queues and POST consume for two messages."""
    participant, endpoint_id = await seed_owner(f"own-{tag}")
    subscription_uuid = new_uuid()
    subscription_id = await seed_subscription(endpoint_id, subscription_uuid)
    for name in ("feeder", "grid"):
        subject = await seed_subject(new_uuid(), participant, name=name)
        await seed_link(subject.subject_id, subscription_id, f"q_legacy_{tag}_{name}")
    async with client_with(broker) as c:
        with patch.object(subscription_routes, "message_broker_factory", lambda _: broker):
            return await c.post(
                f"/subscription/{subscription_uuid}/consume",
                json={"count": 2, "timeout": 5},
                headers=identity_headers(f"own-{tag}"),
            )


async def test_consume_fails_with_502_when_the_broker_is_unreachable(tag, broker):
    broker.get_messages.side_effect = BrokerError("RabbitMQ get_messages failed: refused")
    response = await _consume_two_queues(tag, broker)
    assert response.status_code == 502, response.text
    assert response.json() == {"detail": "Message broker unavailable"}
    assert "refused" not in response.text


async def test_consume_fails_with_502_on_a_non_404_http_error(tag, broker):
    broker.get_messages.side_effect = BrokerError("unauthorized", status_code=401)
    response = await _consume_two_queues(tag, broker)
    assert response.status_code == 502, response.text


async def test_consume_skips_only_a_queue_the_broker_says_is_missing(tag, broker):
    message = {"payload": "kept", "message_id": "m1"}
    broker.get_messages.side_effect = [
        BrokerError("queue gone", status_code=404),
        [message],
    ]
    response = await _consume_two_queues(tag, broker)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_consumed"] == 1
    assert [m["payload"] for m in body["messages"]] == ["kept"]
    assert broker.get_messages.call_count == 2


async def test_consume_returns_messages_already_read_when_a_later_queue_fails(tag, broker):
    # The read is destructive, so failing the request would lose these messages.
    broker.get_messages.side_effect = [
        [{"payload": "kept", "message_id": "m1"}],
        BrokerError("connection lost"),
    ]
    response = await _consume_two_queues(tag, broker)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_consumed"] == 1
    assert [m["payload"] for m in body["messages"]] == ["kept"]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (pyrabbit_http.HTTPError({}, 404, "Not Found", "/api/x", None), 404),
        (pyrabbit_http.HTTPError({}, 500, "Server Error", "/api/x", None), 500),
        (pyrabbit_http.NetworkError("timeout"), None),
        (pyrabbit_api.PermissionError("denied"), None),
    ],
)
def test_wrapper_keeps_the_http_status_on_broker_error(error, expected_status):
    service = object.__new__(RabbitMqService)
    service._client = Mock()
    service._client.get_messages.side_effect = error
    with pytest.raises(BrokerError) as raised:
        service.get_messages("q")
    assert raised.value.status_code == expected_status
