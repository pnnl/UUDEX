"""POST /endpoint/ is for administrators only; nothing creates the first one through the API."""

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import delete, select

import uudex_server.models as m
from conftest import identity_headers
from uudex_server.main import app
from uudex_server.repos.endpoint_repository import EndpointRepository
from uudex_server.services.database_service import get_db_session

TRUSTED = "127.0.0.1"
NEW_CN = "newcomer"


@asynccontextmanager
async def trusted_client():
    transport = ASGITransport(app=app, client=(TRUSTED, 54321))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
async def empty_endpoint_table(setup_test_env):
    """The test database is shared and never reset, so these tests start and end with no endpoints."""
    async with get_db_session() as session:
        await session.execute(delete(m.EndPoint))
    yield
    async with get_db_session() as session:
        await session.execute(delete(m.EndPoint))


def name(prefix: str) -> str:
    """A fresh common name, so no test meets another test's cached identity."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def seed(cn: str, *, admin: bool, active: bool = True, participant_id: int | None = None):
    """Create an endpoint for `cn` (and a participant unless given); return its participant_id."""
    async with get_db_session() as session:
        if participant_id is None:
            participant = m.Participant(
                participant_uuid=str(uuid.uuid4()),
                participant_short_name="p",
                participant_long_name="p",
                root_org_sw="N",
                create_datetime=None,
            )
            session.add(participant)
            await session.flush()
            participant_id = participant.participant_id
        session.add(
            m.EndPoint(
                endpoint_uuid=str(uuid.uuid4()),
                endpoint_user_name=cn,
                certificate_dn=cn,
                description="seeded",
                uudex_administrator_sw="Y" if admin else "N",
                participant_administrator_sw="Y" if admin else "N",
                active_sw="Y" if active else "N",
                participant_id=participant_id,
                create_datetime=None,
            )
        )
    return participant_id


async def all_endpoints() -> list[m.EndPoint]:
    async with get_db_session() as session:
        return list((await session.execute(select(m.EndPoint))).scalars().all())


def body(participant_id: int, **overrides) -> dict:
    return {
        "endpoint_user_name": NEW_CN,
        "certificate_dn": NEW_CN,
        "description": "made by an admin",
        "uudex_administrator_sw": "N",
        "participant_administrator_sw": "N",
        "participant_id": participant_id,
    } | overrides


async def test_no_known_caller_cannot_create_the_first_admin(setup_test_env):
    payload = body(1, uudex_administrator_sw="Y", participant_administrator_sw="Y")
    async with trusted_client() as c:
        response = await c.post(
            "/endpoint/", json=payload, headers=identity_headers(name("nobody"))
        )
    assert response.status_code == 401
    assert await all_endpoints() == []


async def test_a_non_admin_cannot_create_an_admin(setup_test_env):
    admin_cn, user_cn = name("admin"), name("user")
    pid = await seed(admin_cn, admin=True)
    await seed(user_cn, admin=False, participant_id=pid)
    payload = body(pid, uudex_administrator_sw="Y", participant_administrator_sw="Y")
    async with trusted_client() as c:
        response = await c.post("/endpoint/", json=payload, headers=identity_headers(user_cn))
    assert response.status_code == 403
    assert sorted(e.certificate_dn for e in await all_endpoints()) == sorted([admin_cn, user_cn])


async def test_an_admin_creates_an_endpoint_when_two_admins_exist(setup_test_env):
    admin_cn = name("admin")
    pid = await seed(admin_cn, admin=True)
    await seed(name("admin"), admin=True, participant_id=pid)
    async with trusted_client() as c:
        response = await c.post(
            "/endpoint/", json=body(pid), headers=identity_headers(admin_cn)
        )
    assert response.status_code == 200
    rows = [e for e in await all_endpoints() if e.certificate_dn == NEW_CN]
    assert len(rows) == 1
    row = rows[0]
    assert row.endpoint_user_name == NEW_CN
    assert row.description == "made by an admin"
    assert row.uudex_administrator_sw == "N"
    assert row.participant_administrator_sw == "N"
    assert row.active_sw == "Y"
    assert row.participant_id == pid
    assert uuid.UUID(row.endpoint_uuid).version == 4
    assert response.json()["endpoint_id"] == row.endpoint_id


@pytest.mark.parametrize(
    ("admins", "inactive_admins", "expected"),
    [(0, 0, False), (1, 0, True), (2, 0, True), (0, 1, False), (1, 1, True)],
)
async def test_has_any_admin_endpoints_counts_active_admins(
    setup_test_env, admins, inactive_admins, expected
):
    pid = None
    for i in range(admins):
        pid = await seed(f"a{i}", admin=True, participant_id=pid)
    for i in range(inactive_admins):
        pid = await seed(f"x{i}", admin=True, active=False, participant_id=pid)
    await seed("plain", admin=False, participant_id=pid)
    async with get_db_session() as session:
        assert await EndpointRepository(session).has_any_admin_endpoints() is expected
