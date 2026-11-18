"""Queue routes act on the queue names stored on a subject's links, never rebuilt ones (#69)."""

import uuid
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import MissingGreenlet
from sqlmodel import select

import uudex_server.models as m
from conftest import identity_headers
from test_repository_async import seed_endpoint, seed_participant
from test_subject_subscription_hardening import client_with, seed_subject
from uudex_server.repos import SubjectRepository
from uudex_server.services.database_service import get_db_session
from uudex_server.services.message_services.base import queue_name


@pytest.fixture
def broker():
    fake = Mock()
    fake.delete_queue.return_value = 0
    return fake


@pytest.fixture
def tag(setup_test_env):
    return f"n{uuid.uuid4().hex[:8]}"


def new_uuid() -> str:
    return str(uuid.uuid4())


async def seed_owner(cn: str, *, admin: bool = False) -> tuple[int, int]:
    """A participant with one endpoint named `cn`; returns (participant_id, endpoint_id)."""
    participant = await seed_participant()
    endpoint_id = await seed_endpoint(participant, cn)
    if admin:
        async with get_db_session() as session:
            endpoint = await session.get(m.EndPoint, endpoint_id)
            assert endpoint is not None
            endpoint.uudex_administrator_sw = "Y"
    return participant, endpoint_id


async def seed_subscription(endpoint_id: int, subscription_uuid: str) -> int:
    async with get_db_session() as session:
        subscription = m.Subscription(
            subscription_uuid=subscription_uuid,
            subscription_name="n",
            subscription_state="ACTIVE",
            owner_endpoint_id=endpoint_id,
            create_datetime=None,
        )
        session.add(subscription)
        await session.flush()
        return subscription.subscription_id


async def seed_link(subject_id: int, subscription_id: int, stored_queue: str) -> None:
    async with get_db_session() as session:
        session.add(
            m.SubscriptionSubject(
                preferred_fulfillment_type="f",
                backing_queue_name=stored_queue,
                subject_id=subject_id,
                subscription_id=subscription_id,
            )
        )


async def seed_linked_subject(
    participant: int, endpoint_id: int, name: str, stored_queue: str | None = None
) -> tuple[m.Subject, str]:
    """A subject with one link to a fresh subscription; returns it and the stored queue name."""
    subject_uuid = new_uuid()
    subscription_uuid = new_uuid()
    subject = await seed_subject(subject_uuid, participant, name=name)
    subscription_id = await seed_subscription(endpoint_id, subscription_uuid)
    stored = stored_queue or queue_name(subject_uuid, subscription_uuid)
    await seed_link(subject.subject_id, subscription_id, stored)
    return subject, stored


async def manage(c, cn: str, subject_uuid: str, **body):
    return await c.post(
        f"/subject/{subject_uuid}/queue-management", json=body, headers=identity_headers(cn)
    )


async def link_rows(subject_id: int) -> list[m.SubscriptionSubject]:
    async with get_db_session() as session:
        result = await session.execute(
            select(m.SubscriptionSubject).where(m.SubscriptionSubject.subject_id == subject_id)
        )
        return list(result.scalars().all())


class TestLoader:
    async def test_links_and_their_stored_names_are_loaded(self, tag):
        participant, endpoint_id = await seed_owner(f"own-{tag}")
        subject, stored = await seed_linked_subject(participant, endpoint_id, "feeder")
        async with get_db_session() as session:
            loaded = await SubjectRepository(session).select_by_uuid_with_links(
                subject.subject_uuid
            )
            assert loaded is not None
            assert [link.backing_queue_name for link in loaded.subscription_links] == [stored]

    async def test_a_missing_subject_is_none(self, tag):
        async with get_db_session() as session:
            assert await SubjectRepository(session).select_by_uuid_with_links(new_uuid()) is None

    async def test_the_plain_lookup_does_not_load_links(self, tag):
        """Control: without the loader the same read fails on the async session."""
        participant, endpoint_id = await seed_owner(f"own-{tag}")
        subject, _ = await seed_linked_subject(participant, endpoint_id, "feeder")
        async with get_db_session() as session:
            plain = await SubjectRepository(session).select_by_field(
                "subject_uuid", subject.subject_uuid
            )
            assert plain is not None
            with pytest.raises(MissingGreenlet):
                _ = plain.subscription_links


class TestRenameDoesNotWidenOwnership:
    async def test_a_rename_to_another_subjects_name_does_not_reach_its_queue(self, tag, broker):
        p1, e1 = await seed_owner(f"p1-{tag}")
        p2, _ = await seed_owner(f"p2-{tag}")
        subscription_uuid = new_uuid()
        subscription_id = await seed_subscription(e1, subscription_uuid)
        a = await seed_subject(new_uuid(), p1, name="feeder")
        b = await seed_subject(new_uuid(), p2, name="grid")
        # B's stored name has the old name-based shape, which a renamed A would rebuild.
        b_queue = f"q_uudex_grid_{subscription_uuid}"
        await seed_link(
            a.subject_id, subscription_id, queue_name(a.subject_uuid, subscription_uuid)
        )
        await seed_link(b.subject_id, subscription_id, b_queue)
        async with client_with(broker) as c:
            renamed = await c.put(
                f"/subject/{a.subject_id}",
                json={"subject_name": "grid"},
                headers=identity_headers(f"p1-{tag}"),
            )
            assert renamed.status_code == 200, renamed.text
            response = await manage(
                c, f"p1-{tag}", a.subject_uuid, action="delete", queue_name=b_queue
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Subject not found"
        broker.delete_queue.assert_not_called()

    async def test_the_renamed_subjects_own_queue_is_still_deletable(self, tag, broker):
        p1, e1 = await seed_owner(f"p1-{tag}")
        a, a_queue = await seed_linked_subject(p1, e1, "feeder")
        async with client_with(broker) as c:
            await c.put(
                f"/subject/{a.subject_id}",
                json={"subject_name": "grid"},
                headers=identity_headers(f"p1-{tag}"),
            )
            response = await manage(
                c, f"p1-{tag}", a.subject_uuid, action="delete", queue_name=a_queue
            )
        assert response.status_code == 200, response.text
        broker.delete_queue.assert_called_once_with(a_queue)


class TestSharedStoredName:
    @pytest.mark.parametrize("deleter", ["p1", "p2"])
    async def test_a_name_stored_on_two_subjects_is_409_with_no_broker_call(
        self, tag, broker, deleter
    ):
        p1, e1 = await seed_owner(f"p1-{tag}")
        p2, e2 = await seed_owner(f"p2-{tag}")
        shared = f"q_legacy_{tag}"
        a, _ = await seed_linked_subject(p1, e1, "feeder", shared)
        b, _ = await seed_linked_subject(p2, e2, "feeder", shared)
        subject = a if deleter == "p1" else b
        async with client_with(broker) as c:
            response = await manage(
                c, f"{deleter}-{tag}", subject.subject_uuid, action="delete", queue_name=shared
            )
        assert response.status_code == 409
        assert response.json()["detail"] == "Queue is shared with another subject"
        broker.delete_queue.assert_not_called()


class TestPurgeUsesStoredNames:
    async def seed_two_links(self, tag: str, participant: int, endpoint_id: int):
        subject = await seed_subject(new_uuid(), participant, name="feeder")
        stored = [f"q_legacy_{tag}_{i}" for i in range(2)]
        for name in stored:
            await seed_link(
                subject.subject_id, await seed_subscription(endpoint_id, new_uuid()), name
            )
        return subject, stored

    async def test_single_purge_deletes_each_stored_name(self, tag, broker):
        participant, endpoint_id = await seed_owner(f"own-{tag}")
        subject, stored = await self.seed_two_links(tag, participant, endpoint_id)
        async with client_with(broker) as c:
            response = await manage(c, f"own-{tag}", subject.subject_uuid, action="purge")
        assert response.status_code == 200, response.text
        assert sorted(response.json()["queue_info"]["purged_queues"]) == sorted(stored)
        assert sorted(call.args[0] for call in broker.delete_queue.call_args_list) == sorted(stored)

    async def test_bulk_purge_deletes_each_stored_name(self, tag, broker):
        participant, endpoint_id = await seed_owner(f"adm-{tag}", admin=True)
        subject, stored = await self.seed_two_links(tag, participant, endpoint_id)
        async with client_with(broker) as c:
            response = await c.post(
                "/subjects/bulk-operations",
                json={"subject_uuids": [subject.subject_uuid], "operation": "purge_queues"},
                headers=identity_headers(f"adm-{tag}"),
            )
        assert response.status_code == 200, response.text
        assert response.json()["successful"] == [subject.subject_uuid]
        assert sorted(call.args[0] for call in broker.delete_queue.call_args_list) == sorted(stored)
