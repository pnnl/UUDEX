"""Broker names are minted by the server and read back from the row, never rebuilt (#67)."""

import uuid
from unittest.mock import Mock, patch

import pytest
from sqlmodel import select

import uudex_server.models as m
from conftest import identity_headers
from test_repository_async import seed_endpoint, seed_participant
from test_subject_subscription_hardening import (
    client_with,
    create_body,
    seed_subject,
    stored_subject,
)
from uudex_server.services.database_service import get_db_session
from uudex_server.services.message_services import base
from uudex_server.services.message_services.rabbit_mq import RabbitMqService

BROKER_URL = "amqp://host:15672?username=u&password=p"


@pytest.fixture
def broker():
    fake = Mock()
    fake.publish_message.return_value = 0
    return fake


@pytest.fixture
def tag(setup_test_env):
    return f"i{uuid.uuid4().hex[:8]}"


def new_uuid() -> str:
    return str(uuid.uuid4())


async def seed_owner(tag: str, *, admin: bool = False) -> int:
    """A participant with one endpoint, `own-<tag>`; returns the participant id."""
    participant = await seed_participant()
    endpoint_id = await seed_endpoint(participant, f"own-{tag}")
    if admin:
        async with get_db_session() as session:
            endpoint = await session.get(m.EndPoint, endpoint_id)
            assert endpoint is not None
            endpoint.uudex_administrator_sw = "Y"
    return participant


async def subject_rows(subject_uuid: str) -> list[m.Subject]:
    async with get_db_session() as session:
        result = await session.execute(
            select(m.Subject).where(m.Subject.subject_uuid == subject_uuid)
        )
        return list(result.scalars().all())


def all_broker_calls_text(broker: Mock) -> str:
    return repr(broker.mock_calls)


class TestSubjectUuidIsServerOwned:
    async def test_a_body_uuid_cannot_alias_another_subjects_exchange(self, tag, broker):
        victim_uuid = new_uuid()
        await seed_owner(tag)
        victim = await seed_subject(victim_uuid, await seed_participant(), name="feeder_7")
        attack = f"7_{victim_uuid}"
        headers = identity_headers(f"own-{tag}")

        async with client_with(broker) as c:
            created = await c.post(
                "/subjects/", json=create_body("feeder", attack), headers=headers
            )
            assert created.status_code == 200, created.text
            body = created.json()
            published = await c.post(
                f"/subjects/{body['subject_uuid']}/publish",
                json={"messages": ["a"]},
                headers=headers,
            )
            deleted = await c.delete(f"/subject/{body['subject_id']}", headers=headers)

        minted = body["subject_uuid"]
        assert minted != attack
        assert str(uuid.UUID(minted)) == minted
        assert body["backing_exchange_name"] == f"e_{minted}"
        assert body["backing_exchange_name"] != victim.backing_exchange_name
        assert published.status_code == 200, published.text
        assert deleted.status_code == 200, deleted.text
        assert victim.backing_exchange_name not in all_broker_calls_text(broker)
        assert len(await subject_rows(victim_uuid)) == 1
        assert await subject_rows(attack) == []

    async def test_create_stores_the_minted_exchange_on_the_row(self, tag, broker):
        await seed_owner(tag)
        async with client_with(broker) as c:
            response = await c.post(
                "/subjects/",
                json=create_body("feeder", ""),
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 200, response.text
        minted = response.json()["subject_uuid"]
        stored = await stored_subject(minted)
        assert stored is not None
        assert stored.backing_exchange_name == f"e_{minted}"


class TestOneMintingFunction:
    def test_the_formats(self):
        subject_uuid, subscription_uuid = new_uuid(), new_uuid()
        assert base.exchange_name(subject_uuid) == f"e_{subject_uuid}"
        assert base.queue_name(subject_uuid, subscription_uuid) == (
            f"q_uudex_{subject_uuid}_{subscription_uuid}"
        )

    async def test_create_passes_the_stored_name_to_the_broker(self, tag, broker):
        await seed_owner(tag)
        long_name = "n" * 300
        async with client_with(broker) as c:
            response = await c.post(
                "/subjects/",
                json=create_body(long_name, ""),
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 200, response.text
        minted = response.json()["subject_uuid"]
        stored = await stored_subject(minted)
        assert stored is not None
        assert stored.backing_exchange_name == f"e_{minted}"
        assert long_name not in stored.backing_exchange_name
        broker.create_exchange.assert_called_once_with(stored.backing_exchange_name)

    def test_the_service_creates_and_deletes_the_exchange_it_is_given(self):
        with patch("uudex_server.services.message_services.rabbit_mq.Client") as client_cls:
            service = RabbitMqService(BROKER_URL)
            service.create_exchange("e_x")
            service.delete_exchange("e_x")
        client = client_cls.return_value
        client.create_exchange.assert_called_once_with("/", "e_x", "fanout", False, True, False)
        client.delete_exchange.assert_called_once_with("/", "e_x")


class TestDeleteUsesTheStoredExchange:
    async def create_and_rename(self, c, tag: str, headers) -> dict:
        created = await c.post("/subjects/", json=create_body("original", ""), headers=headers)
        assert created.status_code == 200, created.text
        body = created.json()
        renamed = await c.put(
            f"/subject/{body['subject_id']}", json={"subject_name": "renamed"}, headers=headers
        )
        assert renamed.status_code == 200, renamed.text
        return body

    async def test_single_delete_after_a_rename(self, tag, broker):
        await seed_owner(tag)
        headers = identity_headers(f"own-{tag}")
        async with client_with(broker) as c:
            body = await self.create_and_rename(c, tag, headers)
            response = await c.delete(f"/subject/{body['subject_id']}", headers=headers)
        assert response.status_code == 200, response.text
        assert await subject_rows(body["subject_uuid"]) == []
        broker.delete_exchange.assert_called_once_with(body["backing_exchange_name"])

    async def test_bulk_delete_after_a_rename(self, tag, broker):
        await seed_owner(tag, admin=True)
        headers = identity_headers(f"own-{tag}")
        async with client_with(broker) as c:
            body = await self.create_and_rename(c, tag, headers)
            response = await c.post(
                "/subjects/bulk-operations",
                json={"subject_uuids": [body["subject_uuid"]], "operation": "delete"},
                headers=headers,
            )
        assert response.status_code == 200, response.text
        assert response.json()["successful"] == [body["subject_uuid"]]
        assert await subject_rows(body["subject_uuid"]) == []
        broker.delete_exchange.assert_called_once_with(body["backing_exchange_name"])
