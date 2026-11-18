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


async def subjects_tagged(tag: str) -> list[m.Subject]:
    """The rows this test made; the test database keeps rows across tests."""
    async with get_db_session() as session:
        result = await session.execute(
            select(m.Subject).where(m.Subject.subject_uuid.startswith(tag))  # type: ignore[attr-defined]
        )
        return list(result.scalars().all())


@pytest.fixture
def tag(setup_test_env):
    return f"t{uuid.uuid4().hex[:8]}"


@pytest.fixture
def cn(tag):
    return f"repo-{tag}"


class TestRepositoryMethods:
    async def test_select_by_ids_returns_the_matching_row(self, tag):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            await repo.create(make_subject(f"{tag}-one", name="one"))
            two = await repo.create(make_subject(f"{tag}-two", name="two"))

            found = await repo.select_by_ids(subject_id=two.subject_id)
            missing = await repo.select_by_ids(subject_id=999999)

        assert found is not None
        assert (found.subject_id, found.subject_uuid, found.subject_name) == (
            two.subject_id,
            f"{tag}-two",
            "two",
        )
        assert missing is None

    async def test_select_by_fields_filters_on_every_field_given(self, tag):
        first, second = await seed_participant(), await seed_participant()
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            await repo.create(make_subject(f"{tag}-one", first, f"{tag}-one"))
            await repo.create(make_subject(f"{tag}-two", second, f"{tag}-two"))

            found = await repo.select_by_fields(
                subject_name=f"{tag}-two", owner_participant_id=second
            )
            mismatch = await repo.select_by_fields(
                subject_name=f"{tag}-two", owner_participant_id=first
            )

        assert found is not None
        assert (found.subject_uuid, found.owner_participant_id) == (f"{tag}-two", second)
        assert mismatch is None

    async def test_update_writes_the_new_values_and_leaves_other_rows(self, tag):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            one = await repo.create(make_subject(f"{tag}-one", name="one"))
            await repo.create(make_subject(f"{tag}-two", name="two"))

            one.subject_name = "renamed"
            returned = await repo.update(one)
            assert returned.subject_name == "renamed"

        by_uuid = {s.subject_uuid: s.subject_name for s in await subjects_tagged(tag)}
        assert by_uuid == {f"{tag}-one": "renamed", f"{tag}-two": "two"}

    async def test_delete_removes_only_the_given_row(self, tag):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            one = await repo.create(make_subject(f"{tag}-one", name="one"))
            await repo.create(make_subject(f"{tag}-two", name="two"))

            await repo.delete(one)

        assert [s.subject_uuid for s in await subjects_tagged(tag)] == [f"{tag}-two"]

    async def test_select_by_field_finds_a_row_by_a_named_column(self, tag):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            await repo.create(make_subject(f"{tag}-one", name="one"))
            await repo.create(make_subject(f"{tag}-two", name="two"))

            found = await repo.select_by_field("subject_uuid", f"{tag}-two")
            missing = await repo.select_by_field("subject_uuid", f"{tag}-nope")

        assert found is not None
        assert (found.subject_uuid, found.subject_name) == (f"{tag}-two", "two")
        assert missing is None

    async def test_select_by_field_refuses_an_unknown_column(self, setup_test_env):
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            with pytest.raises(ValueError, match="not_a_column"):
                await repo.select_by_field("not_a_column", "x")


class TestSubjectByUuidRoute:
    async def test_owner_reads_their_subject_by_uuid(self, cn, tag):
        mine = await seed_participant()
        other = await seed_participant()
        await seed_endpoint(mine, cn)
        async with get_db_session() as session:
            repo = SubjectRepository(session)
            wanted = await repo.create(make_subject(f"{tag}-mine", mine, "mine"))
            await repo.create(make_subject(f"{tag}-other", other, "other"))

        async with trusted_client() as c:
            response = await c.get(f"/subjects/uuid/{tag}-mine", headers=identity_headers(cn))

        assert response.status_code == 200
        body = response.json()
        assert body["subject_id"] == wanted.subject_id
        assert body["subject_uuid"] == f"{tag}-mine"
        assert body["subject_name"] == "mine"
        assert body["owner_participant_id"] == mine

    async def test_unknown_uuid_is_404(self, cn, tag):
        await seed_endpoint(await seed_participant(), cn)
        async with trusted_client() as c:
            response = await c.get(f"/subjects/uuid/{tag}-missing", headers=identity_headers(cn))
        assert response.status_code == 404


class TestCreateSubscriptionRoute:
    async def test_post_creates_a_subscription_owned_by_the_caller(self, cn, tag):
        endpoint_id = await seed_endpoint(await seed_participant(), cn)
        payload = {
            "subscription_uuid": f"{tag}-sub",
            "subscription_name": "my subscription",
            "subscription_state": "active",
            "owner_endpoint_id": endpoint_id + 1000,
        }
        async with trusted_client() as c:
            response = await c.post("/subscription/", json=payload, headers=identity_headers(cn))

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["subscription_uuid"] == f"{tag}-sub"
        assert body["subscription_name"] == "my subscription"
        assert body["subscription_state"] == "active"
        assert body["owner_endpoint_id"] == endpoint_id

        async with get_db_session() as session:
            result = await session.execute(
                select(m.Subscription).where(m.Subscription.subscription_uuid == f"{tag}-sub")
            )
            rows = list(result.scalars().all())
        assert [(r.subscription_uuid, r.owner_endpoint_id) for r in rows] == [
            (f"{tag}-sub", endpoint_id)
        ]
