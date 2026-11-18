"""Broker names are minted by the server and read back from the row, never rebuilt (#67)."""

import logging
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlmodel import select

import uudex_server.main as main_module
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


class TestTrustedExchangeName:
    """Rows written before the server minted names: the stored name is checked at use."""

    async def seed_rows(self, tag: str, *, admin: bool = False) -> dict[str, m.Subject]:
        participant = await seed_owner(tag, admin=admin)
        other = await seed_participant()
        other_uuid = new_uuid()
        other_subject = await seed_subject(other_uuid, other, name="feeder")
        shared_uuid, aliased_uuid, legacy_uuid = new_uuid(), new_uuid(), new_uuid()
        return {
            "other": other_subject,
            # Canonical uuid, but the stored name is another subject's exchange.
            "foreign": await seed_subject(
                shared_uuid,
                participant,
                name="foreign",
                exchange=other_subject.backing_exchange_name,
            ),
            # A uuid that is not canonical, so the name's tail is not tied to this row alone.
            "aliased": await seed_subject(
                f"7_{aliased_uuid}",
                participant,
                name="feeder",
                exchange=f"e_feeder_7_{aliased_uuid}",
            ),
            "legacy": await seed_subject(legacy_uuid, participant, name="feeder"),
        }

    @pytest.mark.parametrize("row", ["foreign", "aliased"])
    async def test_publish_to_a_bad_row_is_409_with_no_broker_call(self, tag, broker, row):
        rows = await self.seed_rows(tag)
        async with client_with(broker) as c:
            response = await c.post(
                f"/subjects/{rows[row].subject_uuid}/publish",
                json={"messages": ["a"]},
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 409, response.text
        assert response.json()["detail"] == "Subject broker name needs repair"
        broker.publish_message.assert_not_called()

    @pytest.mark.parametrize("row", ["foreign", "aliased"])
    async def test_queue_info_of_a_bad_row_is_409_with_no_broker_call(self, tag, broker, row):
        rows = await self.seed_rows(tag)
        async with client_with(broker) as c:
            response = await c.get(
                f"/subject/{rows[row].subject_uuid}/queue-info",
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 409, response.text
        assert broker.mock_calls == []

    async def test_a_non_owner_still_gets_403_not_409(self, tag, broker):
        rows = await self.seed_rows(tag)
        await seed_endpoint(await seed_participant(), f"other-{tag}")
        async with client_with(broker) as c:
            response = await c.post(
                f"/subjects/{rows['foreign'].subject_uuid}/publish",
                json={"messages": ["a"]},
                headers=identity_headers(f"other-{tag}"),
            )
        assert response.status_code == 403, response.text

    async def test_delete_of_a_bad_row_removes_it_and_skips_the_broker(self, tag, broker):
        rows = await self.seed_rows(tag)
        async with client_with(broker) as c:
            response = await c.delete(
                f"/subject/{rows['foreign'].subject_id}", headers=identity_headers(f"own-{tag}")
            )
        assert response.status_code == 200, response.text
        assert await subject_rows(rows["foreign"].subject_uuid) == []
        assert len(await subject_rows(rows["other"].subject_uuid)) == 1
        assert broker.mock_calls == []

    async def test_bulk_delete_of_a_bad_row_removes_it_and_skips_the_broker(self, tag, broker):
        rows = await self.seed_rows(tag, admin=True)
        async with client_with(broker) as c:
            response = await c.post(
                "/subjects/bulk-operations",
                json={"subject_uuids": [rows["aliased"].subject_uuid], "operation": "delete"},
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 200, response.text
        assert response.json()["successful"] == [rows["aliased"].subject_uuid]
        assert await subject_rows(rows["aliased"].subject_uuid) == []
        assert broker.mock_calls == []

    async def test_an_honest_legacy_row_still_publishes_to_its_own_exchange(self, tag, broker):
        rows = await self.seed_rows(tag)
        async with client_with(broker) as c:
            response = await c.post(
                f"/subjects/{rows['legacy'].subject_uuid}/publish",
                json={"messages": ["a"]},
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 200, response.text
        assert [c.kwargs["subject_exchange"] for c in broker.publish_message.call_args_list] == [
            rows["legacy"].backing_exchange_name
        ]

    async def test_startup_logs_the_bad_rows_and_not_the_good_ones(self, tag, caplog):
        rows = await self.seed_rows(tag)
        with caplog.at_level(logging.WARNING):
            async with main_module.lifespan(main_module.app):
                pass
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        text = "\n".join(warnings)
        assert rows["foreign"].subject_uuid in text
        assert rows["aliased"].subject_uuid in text
        assert rows["legacy"].subject_uuid not in text
        assert rows["other"].subject_uuid not in text

    async def test_a_failing_scan_does_not_stop_startup(self, tag):
        failing = AsyncMock(side_effect=RuntimeError("scan broke"))
        with patch.object(main_module, "warn_untrusted_exchange_names", failing):
            async with main_module.lifespan(main_module.app):
                pass
        failing.assert_awaited_once()
