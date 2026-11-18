"""Subject and subscription routes against the real repository: server-owned fields (#67)."""

import uuid
from contextlib import asynccontextmanager
from unittest.mock import Mock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

import uudex_server.models as m
from conftest import identity_headers
from test_repository_async import seed_endpoint, seed_participant
from uudex_server.main import app
from uudex_server.repos import SubjectRepository, SubscriptionRepository
from uudex_server.routes import subject_routes
from uudex_server.services.database_service import get_db_session, get_engine

TRUSTED = "127.0.0.1"


def exchange_for(name: str, subject_uuid: str) -> str:
    return f"e_{name}_{subject_uuid}"


@asynccontextmanager
async def client_with(broker: Mock):
    app.dependency_overrides[subject_routes.get_broker_service] = lambda: broker
    transport = ASGITransport(app=app, client=(TRUSTED, 54321))
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(subject_routes.get_broker_service, None)


@pytest.fixture
def broker():
    fake = Mock()
    fake.publish_message.return_value = 0
    return fake


@pytest.fixture
def tag(setup_test_env):
    return f"h{uuid.uuid4().hex[:8]}"


async def seed_definition() -> int:
    async with get_db_session() as session:
        definition = m.DatasetDefinition(
            dataset_definition_uuid=str(uuid.uuid4()),
            dataset_definition_name="d",
            description="d",
            create_datetime=None,
        )
        session.add(definition)
        await session.flush()
        return definition.dataset_definition_id


async def seed_subject(
    subject_uuid: str, participant_id: int, definition_id: int = 1, name: str = "s"
) -> m.Subject:
    async with get_db_session() as session:
        return await SubjectRepository(session).create(
            m.Subject(
                subject_uuid=subject_uuid,
                subject_name=name,
                dataset_instance_key="k",
                subscription_type="t",
                fulfillment_types_available="f",
                full_queue_behavior=None,
                max_queue_size_kb=None,
                max_message_count=None,
                priority=None,
                backing_exchange_name=exchange_for(name, subject_uuid),
                owner_participant_id=participant_id,
                dataset_definition_id=definition_id,
                create_datetime=None,
            )
        )


async def stored_subject(subject_uuid: str) -> m.Subject | None:
    async with get_db_session() as session:
        return await SubjectRepository(session).select_by_field("subject_uuid", subject_uuid)


def create_body(name: str, subject_uuid: str, **extra: object) -> dict[str, object]:
    return {
        "subject_uuid": subject_uuid,
        "subject_name": name,
        "dataset_instance_key": "k",
        "subscription_type": "t",
        "fulfillment_types_available": "f",
        "full_queue_behavior": None,
        "max_queue_size_kb": None,
        "max_message_count": None,
        "priority": None,
        **extra,
    }


class TestExchangeNameIsServerOwned:
    async def test_create_ignores_a_client_chosen_exchange(self, tag, broker):
        mine = await seed_participant()
        await seed_endpoint(mine, f"own-{tag}")
        victim = await seed_subject(f"{tag}-victim", await seed_participant(), name="victim")

        async with client_with(broker) as c:
            response = await c.post(
                "/subjects/",
                json=create_body(
                    "mine", f"{tag}-mine", backing_exchange_name=victim.backing_exchange_name
                ),
                headers=identity_headers(f"own-{tag}"),
            )

        assert response.status_code == 200, response.text
        assert response.json()["backing_exchange_name"] == exchange_for("mine", f"{tag}-mine")
        stored = await stored_subject(f"{tag}-mine")
        assert stored is not None
        assert stored.backing_exchange_name == exchange_for("mine", f"{tag}-mine")

    async def test_put_cannot_change_the_exchange_and_publish_stays_on_it(self, tag, broker):
        mine = await seed_participant()
        await seed_endpoint(mine, f"own-{tag}")
        victim = await seed_subject(f"{tag}-victim", await seed_participant(), name="victim")
        own = await seed_subject(f"{tag}-mine", mine, name="mine")
        headers = identity_headers(f"own-{tag}")

        async with client_with(broker) as c:
            put = await c.put(
                f"/subject/{own.subject_id}",
                json={"backing_exchange_name": victim.backing_exchange_name},
                headers=headers,
            )
            published = await c.post(
                f"/subjects/{tag}-mine/publish", json={"messages": ["a", "b"]}, headers=headers
            )

        assert put.status_code == 200, put.text
        stored = await stored_subject(f"{tag}-mine")
        assert stored is not None
        assert stored.backing_exchange_name == exchange_for("mine", f"{tag}-mine")
        assert published.status_code == 200, published.text
        assert [c.kwargs["subject_exchange"] for c in broker.publish_message.call_args_list] == [
            exchange_for("mine", f"{tag}-mine")
        ] * 2


class TestSubscriptionUuidIsServerOwned:
    async def post_subscription(self, c: AsyncClient, cn: str, **fields: object):
        body = {"subscription_name": "n", "subscription_state": "ACTIVE", "owner_endpoint_id": 0}
        return await c.post("/subscription/", json={**body, **fields}, headers=identity_headers(cn))

    async def test_a_second_caller_reusing_a_uuid_cannot_break_the_first(self, tag, broker):
        first_endpoint = await seed_endpoint(await seed_participant(), f"first-{tag}")
        await seed_endpoint(await seed_participant(), f"second-{tag}")

        async with client_with(broker) as c:
            created = await self.post_subscription(c, f"first-{tag}", subscription_uuid=f"{tag}-u")
            taken = created.json()["subscription_uuid"]
            squat = await self.post_subscription(c, f"second-{tag}", subscription_uuid=taken)
            got = await c.get(f"/subscription/{taken}", headers=identity_headers(f"first-{tag}"))
            consumed = await c.post(
                f"/subscription/{taken}/consume",
                json={"count": 1},
                headers=identity_headers(f"first-{tag}"),
            )

        assert squat.status_code == 200, squat.text
        assert squat.json()["subscription_uuid"] != taken
        assert got.status_code == 200, got.text
        assert got.json()["owner_endpoint_id"] == first_endpoint
        assert consumed.status_code == 200, consumed.text

    async def test_the_server_chooses_the_uuid(self, tag, broker):
        await seed_endpoint(await seed_participant(), f"first-{tag}")
        async with client_with(broker) as c:
            response = await self.post_subscription(
                c, f"first-{tag}", subscription_uuid=f"{tag}-chosen"
            )
        assert response.status_code == 200, response.text
        assert response.json()["subscription_uuid"] != f"{tag}-chosen"
        assert uuid.UUID(response.json()["subscription_uuid"])

    async def test_the_column_refuses_a_duplicate_uuid(self, tag):
        endpoint_id = await seed_endpoint(await seed_participant(), f"first-{tag}")

        def row() -> m.Subscription:
            return m.Subscription(
                subscription_uuid=f"{tag}-dup",
                subscription_name="n",
                subscription_state="ACTIVE",
                owner_endpoint_id=endpoint_id,
                create_datetime=None,
            )

        async with get_db_session() as session:
            await SubscriptionRepository(session).create(row())
        with pytest.raises(IntegrityError):
            async with get_db_session() as session:
                await SubscriptionRepository(session).create(row())

    @pytest.mark.parametrize("state", ["ACTIVE", "PAUSED"])
    async def test_an_allowed_state_is_stored_upper_case(self, tag, broker, state):
        await seed_endpoint(await seed_participant(), f"first-{tag}")
        async with client_with(broker) as c:
            response = await self.post_subscription(
                c, f"first-{tag}", subscription_state=state.lower()
            )
        assert response.status_code == 200, response.text
        assert response.json()["subscription_state"] == state

    async def test_any_other_state_is_422_and_stores_nothing(self, tag, broker):
        await seed_endpoint(await seed_participant(), f"first-{tag}")
        async with client_with(broker) as c:
            response = await self.post_subscription(
                c, f"first-{tag}", subscription_name=f"{tag}-bad", subscription_state="whatever"
            )
        assert response.status_code == 422
        async with get_db_session() as session:
            rows = (
                (
                    await session.execute(
                        select(m.Subscription).where(
                            m.Subscription.subscription_name == f"{tag}-bad"
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert list(rows) == []


class TestUpdateAndDeleteAsOwner:
    async def test_update_with_no_field_is_a_no_op_that_returns_the_row(self, tag):
        participant = await seed_participant()
        seeded = await seed_subject(f"{tag}-one", participant, name="one")
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            row = await repo.select_by_field("subject_uuid", f"{tag}-one")
            assert row is not None
            returned = await repo.update(row)
        assert returned.subject_id == seeded.subject_id
        stored = await stored_subject(f"{tag}-one")
        assert stored is not None
        assert (stored.subject_name, stored.backing_exchange_name) == (
            "one",
            exchange_for("one", f"{tag}-one"),
        )

    async def test_owner_put_with_an_empty_body_is_200_and_changes_nothing(self, tag, broker):
        participant = await seed_participant()
        await seed_endpoint(participant, f"own-{tag}")
        own = await seed_subject(f"{tag}-one", participant, name="one")
        async with client_with(broker) as c:
            response = await c.put(
                f"/subject/{own.subject_id}", json={}, headers=identity_headers(f"own-{tag}")
            )
        assert response.status_code == 200, response.text
        assert response.json()["subject_name"] == "one"
        stored = await stored_subject(f"{tag}-one")
        assert stored is not None and stored.subject_name == "one"

    async def test_owner_put_writes_only_the_given_field(self, tag, broker):
        participant = await seed_participant()
        await seed_endpoint(participant, f"own-{tag}")
        own = await seed_subject(f"{tag}-one", participant, name="one")
        async with client_with(broker) as c:
            response = await c.put(
                f"/subject/{own.subject_id}",
                json={"priority": 7},
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 200, response.text
        stored = await stored_subject(f"{tag}-one")
        assert stored is not None
        assert (stored.priority, stored.subject_name) == (7, "one")

    @pytest.mark.parametrize("field", ["subject_name", "dataset_instance_key", "subscription_type"])
    async def test_put_with_a_null_for_a_required_column_is_422(self, tag, broker, field):
        participant = await seed_participant()
        await seed_endpoint(participant, f"own-{tag}")
        own = await seed_subject(f"{tag}-one", participant, name="one")
        async with client_with(broker) as c:
            response = await c.put(
                f"/subject/{own.subject_id}",
                json={field: None},
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 422
        stored = await stored_subject(f"{tag}-one")
        assert stored is not None and stored.subject_name == "one"

    async def test_non_owner_put_is_403_and_changes_nothing(self, tag, broker):
        await seed_endpoint(await seed_participant(), f"other-{tag}")
        victim = await seed_subject(f"{tag}-one", await seed_participant(), name="one")
        async with client_with(broker) as c:
            response = await c.put(
                f"/subject/{victim.subject_id}",
                json={"subject_name": "taken"},
                headers=identity_headers(f"other-{tag}"),
            )
        assert response.status_code == 403
        stored = await stored_subject(f"{tag}-one")
        assert stored is not None and stored.subject_name == "one"

    async def test_owner_delete_removes_the_row_and_the_exchange(self, tag, broker):
        participant = await seed_participant()
        await seed_endpoint(participant, f"own-{tag}")
        own = await seed_subject(f"{tag}-one", participant, name="one")
        async with client_with(broker) as c:
            response = await c.delete(
                f"/subject/{own.subject_id}", headers=identity_headers(f"own-{tag}")
            )
        assert response.status_code == 200, response.text
        assert await stored_subject(f"{tag}-one") is None
        broker.delete_subject.assert_called_once_with(subject_name="one", subject_uuid=f"{tag}-one")

    async def test_non_owner_delete_is_403_and_touches_nothing(self, tag, broker):
        await seed_endpoint(await seed_participant(), f"other-{tag}")
        victim = await seed_subject(f"{tag}-one", await seed_participant(), name="one")
        async with client_with(broker) as c:
            response = await c.delete(
                f"/subject/{victim.subject_id}", headers=identity_headers(f"other-{tag}")
            )
        assert response.status_code == 403
        assert await stored_subject(f"{tag}-one") is not None
        broker.delete_subject.assert_not_called()


@pytest.fixture
async def foreign_keys_on(setup_test_env):
    """SQLite ignores foreign keys unless each new connection turns them on."""
    engine = get_engine()

    def enable(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine.sync_engine, "connect", enable)
    await engine.dispose()
    yield
    event.remove(engine.sync_engine, "connect", enable)
    await engine.dispose()


async def seed_link(subject_id: int, endpoint_id: int, tag: str) -> None:
    async with get_db_session() as session:
        subscription = m.Subscription(
            subscription_uuid=f"{tag}-sub",
            subscription_name="n",
            subscription_state="ACTIVE",
            owner_endpoint_id=endpoint_id,
            create_datetime=None,
        )
        session.add(subscription)
        await session.flush()
        session.add(
            m.SubscriptionSubject(
                preferred_fulfillment_type="f",
                backing_queue_name="q",
                subject_id=subject_id,
                subscription_id=subscription.subscription_id,
            )
        )


async def link_count(subject_id: int) -> int:
    async with get_db_session() as session:
        rows = await session.execute(
            select(m.SubscriptionSubject).where(m.SubscriptionSubject.subject_id == subject_id)
        )
        return len(list(rows.scalars().all()))


class TestDeleteWithForeignKeysEnforced:
    async def seed(self, tag: str, admin: bool):
        participant = await seed_participant()
        endpoint_id = await seed_endpoint(participant, f"own-{tag}")
        if admin:
            async with get_db_session() as session:
                endpoint = await session.get(m.EndPoint, endpoint_id)
                assert endpoint is not None
                endpoint.uudex_administrator_sw = "Y"
        definition = await seed_definition()
        linked = await seed_subject(f"{tag}-linked", participant, definition, "linked")
        free = await seed_subject(f"{tag}-free", participant, definition, "free")
        await seed_link(linked.subject_id, endpoint_id, tag)
        return linked, free

    async def test_single_delete_of_a_linked_subject_is_409_and_calls_no_broker(
        self, foreign_keys_on, tag, broker
    ):
        linked, _ = await self.seed(tag, admin=False)
        async with client_with(broker) as c:
            response = await c.delete(
                f"/subject/{linked.subject_id}", headers=identity_headers(f"own-{tag}")
            )
        assert response.status_code == 409, response.text
        broker.delete_subject.assert_not_called()
        assert await stored_subject(f"{tag}-linked") is not None
        assert await link_count(linked.subject_id) == 1

    async def test_single_delete_of_an_unlinked_subject_still_works(
        self, foreign_keys_on, tag, broker
    ):
        _, free = await self.seed(tag, admin=False)
        async with client_with(broker) as c:
            response = await c.delete(
                f"/subject/{free.subject_id}", headers=identity_headers(f"own-{tag}")
            )
        assert response.status_code == 200, response.text
        assert await stored_subject(f"{tag}-free") is None
        broker.delete_subject.assert_called_once_with(
            subject_name="free", subject_uuid=f"{tag}-free"
        )

    async def test_bulk_delete_skips_the_linked_subject_and_deletes_the_rest(
        self, foreign_keys_on, tag, broker
    ):
        linked, _ = await self.seed(tag, admin=True)
        async with client_with(broker) as c:
            response = await c.post(
                "/subjects/bulk-operations",
                json={"subject_uuids": [f"{tag}-linked", f"{tag}-free"], "operation": "delete"},
                headers=identity_headers(f"own-{tag}"),
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["successful"] == [f"{tag}-free"]
        assert [f["subject_uuid"] for f in body["failed"]] == [f"{tag}-linked"]
        assert "linked" in body["failed"][0]["error"]
        broker.delete_subject.assert_called_once_with(
            subject_name="free", subject_uuid=f"{tag}-free"
        )
        assert await stored_subject(f"{tag}-linked") is not None
        assert await stored_subject(f"{tag}-free") is None
        assert await link_count(linked.subject_id) == 1
