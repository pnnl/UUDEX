"""The base repository works on the async session, against the real test database (#67)."""

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

import uudex_server.models as m
from conftest import identity_headers
from uudex_server.main import app
from uudex_server.repos import SubjectRepository
from uudex_server.services.database_service import get_db_session

TRUSTED = "127.0.0.1"


@asynccontextmanager
async def trusted_client():
    transport = ASGITransport(app=app, client=(TRUSTED, 54321))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def make_subject(subject_uuid: str, participant_id: int = 1, name: str = "s") -> m.Subject:
    return m.Subject(
        subject_uuid=subject_uuid,
        subject_name=name,
        dataset_instance_key="k",
        subscription_type="t",
        fulfillment_types_available="f",
        full_queue_behavior=None,
        max_queue_size_kb=None,
        max_message_count=None,
        priority=None,
        backing_exchange_name=f"e_{name}_{subject_uuid}",
        owner_participant_id=participant_id,
        dataset_definition_id=1,
        create_datetime=None,
    )


async def seed_participant() -> int:
    async with get_db_session() as session:
        participant = m.Participant(
            participant_uuid=str(uuid.uuid4()),
            participant_short_name="p",
            participant_long_name="p",
            root_org_sw="N",
            create_datetime=None,
        )
        session.add(participant)
        await session.flush()
        return participant.participant_id


async def seed_endpoint(participant_id: int, cn: str) -> int:
    async with get_db_session() as session:
        endpoint = m.EndPoint(
            endpoint_uuid=str(uuid.uuid4()),
            endpoint_user_name=cn,
            certificate_dn=cn,
            description="seeded for the repository tests",
            uudex_administrator_sw="N",
            participant_administrator_sw="N",
            participant_id=participant_id,
            create_datetime=None,
        )
        session.add(endpoint)
        await session.flush()
        return endpoint.endpoint_id


async def all_subjects() -> list[m.Subject]:
    async with get_db_session() as session:
        result = await session.execute(select(m.Subject))
        return list(result.scalars().all())


@pytest.fixture
def cn(setup_test_env):
    return f"repo-{uuid.uuid4().hex[:8]}"


class TestRepositoryMethods:
    async def test_select_by_ids_returns_the_matching_row(self, setup_test_env):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            await repo.create(make_subject("u-one", name="one"))
            two = await repo.create(make_subject("u-two", name="two"))

            found = await repo.select_by_ids(subject_id=two.subject_id)
            missing = await repo.select_by_ids(subject_id=9999)

        assert found is not None
        assert (found.subject_id, found.subject_uuid, found.subject_name) == (
            two.subject_id,
            "u-two",
            "two",
        )
        assert missing is None

    async def test_select_by_fields_filters_on_every_field_given(self, setup_test_env):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            await repo.create(make_subject("u-one", participant_id=1, name="one"))
            await repo.create(make_subject("u-two", participant_id=2, name="two"))

            found = await repo.select_by_fields(subject_name="two", owner_participant_id=2)
            mismatch = await repo.select_by_fields(subject_name="two", owner_participant_id=1)

        assert found is not None
        assert (found.subject_uuid, found.owner_participant_id) == ("u-two", 2)
        assert mismatch is None

    async def test_update_writes_the_new_values_and_leaves_other_rows(self, setup_test_env):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            one = await repo.create(make_subject("u-one", name="one"))
            two = await repo.create(make_subject("u-two", name="two"))

            one.subject_name = "renamed"
            returned = await repo.update(one)
            assert returned.subject_name == "renamed"

        by_uuid = {s.subject_uuid: s.subject_name for s in await all_subjects()}
        assert by_uuid == {"u-one": "renamed", "u-two": "two"}
        assert two.subject_id is not None

    async def test_delete_removes_only_the_given_row(self, setup_test_env):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            one = await repo.create(make_subject("u-one", name="one"))
            await repo.create(make_subject("u-two", name="two"))

            await repo.delete(one)

        assert [s.subject_uuid for s in await all_subjects()] == ["u-two"]

    async def test_select_by_field_finds_a_row_by_a_named_column(self, setup_test_env):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            await repo.create(make_subject("u-one", name="one"))
            await repo.create(make_subject("u-two", name="two"))

            found = await repo.select_by_field("subject_uuid", "u-two")
            missing = await repo.select_by_field("subject_uuid", "nope")

        assert found is not None
        assert (found.subject_uuid, found.subject_name) == ("u-two", "two")
        assert missing is None

    async def test_select_by_field_refuses_an_unknown_column(self, setup_test_env):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            with pytest.raises(ValueError, match="not_a_column"):
                await repo.select_by_field("not_a_column", "x")


class TestSubjectByUuidRoute:
    async def test_owner_reads_their_subject_by_uuid(self, cn):
        mine = await seed_participant()
        other = await seed_participant()
        await seed_endpoint(mine, cn)
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            wanted = await repo.create(make_subject("uuid-mine", mine, "mine"))
            await repo.create(make_subject("uuid-other", other, "other"))

        async with trusted_client() as c:
            response = await c.get("/subjects/uuid/uuid-mine", headers=identity_headers(cn))

        assert response.status_code == 200
        body = response.json()
        assert body["subject_id"] == wanted.subject_id
        assert body["subject_uuid"] == "uuid-mine"
        assert body["subject_name"] == "mine"
        assert body["owner_participant_id"] == mine

    async def test_unknown_uuid_is_404(self, cn):
        await seed_endpoint(await seed_participant(), cn)
        async with trusted_client() as c:
            response = await c.get("/subjects/uuid/missing", headers=identity_headers(cn))
        assert response.status_code == 404


class TestCreateSubscriptionRoute:
    async def test_post_creates_a_subscription_owned_by_the_caller(self, cn):
        endpoint_id = await seed_endpoint(await seed_participant(), cn)
        payload = {
            "subscription_uuid": "sub-uuid-1",
            "subscription_name": "my subscription",
            "subscription_state": "active",
            "owner_endpoint_id": endpoint_id + 1000,
        }
        async with trusted_client() as c:
            response = await c.post("/subscription/", json=payload, headers=identity_headers(cn))

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["subscription_uuid"] == "sub-uuid-1"
        assert body["subscription_name"] == "my subscription"
        assert body["subscription_state"] == "active"
        assert body["owner_endpoint_id"] == endpoint_id

        async with get_db_session() as session:
            rows = list((await session.execute(select(m.Subscription))).scalars().all())
        assert [(r.subscription_uuid, r.owner_endpoint_id) for r in rows] == [
            ("sub-uuid-1", endpoint_id)
        ]
