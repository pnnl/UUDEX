"""Routes that take UserDep get the real caller, read fresh on every request."""

import uuid
from contextlib import asynccontextmanager

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from sqlmodel import select

import uudex_server.models as m
from conftest import identity_headers
from uudex_server.core.dependencies import get_current_user
from uudex_server.main import app
from uudex_server.services.database_service import get_db_session

TRUSTED = "127.0.0.1"


@asynccontextmanager
async def trusted_client():
    transport = ASGITransport(app=app, client=(TRUSTED, 54321))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


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


async def seed_endpoint(participant_id: int, cn: str, *, admin: bool = False) -> str:
    endpoint_uuid = str(uuid.uuid4())
    async with get_db_session() as session:
        session.add(
            m.EndPoint(
                endpoint_uuid=endpoint_uuid,
                endpoint_user_name=cn,
                certificate_dn=cn,
                description="seeded for the caller tests",
                uudex_administrator_sw="Y" if admin else "N",
                participant_administrator_sw="N",
                participant_id=participant_id,
                create_datetime=None,
            )
        )
    return endpoint_uuid


async def seed_subject(participant_id: int) -> int:
    async with get_db_session() as session:
        subject = m.Subject(
            subject_uuid=str(uuid.uuid4()),
            subject_name="s",
            dataset_instance_key="k",
            subscription_type="t",
            fulfillment_types_available="f",
            full_queue_behavior=None,
            max_queue_size_kb=None,
            max_message_count=None,
            priority=None,
            backing_exchange_name="x",
            owner_participant_id=participant_id,
            dataset_definition_id=1,
            create_datetime=None,
        )
        session.add(subject)
        await session.flush()
        return subject.subject_id


async def set_switch(model, key_field: str, key, field: str, value: str) -> None:
    async with get_db_session() as session:
        result = await session.execute(select(model).where(getattr(model, key_field) == key))
        row = result.scalar_one()
        setattr(row, field, value)


@pytest.fixture
def cn(setup_test_env):
    return f"caller-{uuid.uuid4().hex[:8]}"


async def test_known_user_sees_only_their_participants_subjects(cn):
    mine, other = await seed_participant(), await seed_participant()
    await seed_endpoint(mine, cn)
    mine_id, other_id = await seed_subject(mine), await seed_subject(other)
    async with trusted_client() as c:
        response = await c.get("/subjects/", headers=identity_headers(cn))
    assert response.status_code == 200
    ids = {s["subject_id"] for s in response.json()}
    assert ids == {mine_id}
    assert other_id not in ids


async def test_unknown_caller_is_401_on_subjects_and_subscriptions(cn):
    async with trusted_client() as c:
        subjects = await c.get("/subjects/", headers=identity_headers(cn))
        subscriptions = await c.get("/subscriptions/", headers=identity_headers(cn))
    assert subjects.status_code == 401
    assert subscriptions.status_code == 401
    assert subjects.json()["detail"] == "Unauthorized: Invalid certificate"


async def test_admin_lists_every_endpoint(cn):
    mine, other = await seed_participant(), await seed_participant()
    admin_uuid = await seed_endpoint(mine, cn, admin=True)
    other_uuid = await seed_endpoint(other, f"{cn}-other")
    async with trusted_client() as c:
        response = await c.get("/endpoint/", headers=identity_headers(cn))
    assert response.status_code == 200
    assert {admin_uuid, other_uuid} <= {e["endpoint_uuid"] for e in response.json()}


async def test_deactivated_endpoint_loses_access_on_the_next_request(cn):
    participant = await seed_participant()
    await seed_endpoint(participant, cn)
    async with trusted_client() as c:
        first = await c.get("/subjects/", headers=identity_headers(cn))
        await set_switch(m.EndPoint, "certificate_dn", cn, "active_sw", "N")
        second = await c.get("/subjects/", headers=identity_headers(cn))
    assert first.status_code == 200
    assert second.status_code == 401


async def test_inactive_participant_loses_access_on_the_next_request(cn):
    participant = await seed_participant()
    await seed_endpoint(participant, cn)
    async with trusted_client() as c:
        first = await c.get("/subjects/", headers=identity_headers(cn))
        await set_switch(m.Participant, "participant_id", participant, "active_sw", "N")
        second = await c.get("/subjects/", headers=identity_headers(cn))
    assert first.status_code == 200
    assert second.status_code == 401


async def test_demoted_admin_loses_the_admin_view_on_the_next_request(cn):
    mine, other = await seed_participant(), await seed_participant()
    await seed_endpoint(mine, cn, admin=True)
    other_uuid = await seed_endpoint(other, f"{cn}-other")
    async with trusted_client() as c:
        before = await c.get("/endpoint/", headers=identity_headers(cn))
        await set_switch(m.EndPoint, "certificate_dn", cn, "uudex_administrator_sw", "N")
        after = await c.get("/endpoint/", headers=identity_headers(cn))
    assert other_uuid in {e["endpoint_uuid"] for e in before.json()}
    assert after.status_code == 200
    assert other_uuid not in {e["endpoint_uuid"] for e in after.json()}


def _uses_current_user(dependant) -> bool:
    return any(d.call is get_current_user or _uses_current_user(d) for d in dependant.dependencies)


def _mounted_api_routes(routes) -> list[APIRoute]:
    """Flatten the routers app.include_router mounted; they carry no extra prefix here."""
    found = []
    for route in routes:
        if isinstance(route, APIRoute):
            found.append(route)
        elif hasattr(route, "original_router"):
            found.extend(_mounted_api_routes(route.original_router.routes))
    return found


def _route_pairs(routes) -> set[tuple[str, str]]:
    return {(method, route.path) for route in routes for method in route.methods}


def _caller_routes() -> list[tuple[str, str]]:
    return sorted(
        _route_pairs(r for r in _mounted_api_routes(app.routes) if _uses_current_user(r.dependant))
    )


# Mounted routes that do not take a caller. Every other mounted route must.
_NO_CALLER = {
    ("GET", "/"): "public root page",
    ("GET", "/docs"): "framework API docs",
    ("GET", "/openapi.json"): "framework API schema",
    ("POST", "/endpoint/"): "takes an optional caller so the first endpoint can bootstrap",
    ("GET", "/participants/"): "known gap, tracked in #48",
    ("POST", "/participants/"): "known gap, tracked in #48",
    ("GET", "/subscription/{subscription_uuid}"): "known gap, tracked in #48",
}


def test_every_mounted_route_takes_a_caller_unless_allowlisted():
    mounted = _route_pairs(_mounted_api_routes(app.routes))
    stale = set(_NO_CALLER) - mounted
    assert not stale, f"allowlisted routes that are no longer mounted: {sorted(stale)}"
    assert set(_caller_routes()) == mounted - set(_NO_CALLER), (
        "mounted routes that lost their caller: "
        f"{sorted(mounted - set(_NO_CALLER) - set(_caller_routes()))}; "
        "allowlisted routes that now take one: "
        f"{sorted(set(_NO_CALLER) & set(_caller_routes()))}"
    )


@pytest.mark.parametrize(("method", "path"), _caller_routes())
async def test_unknown_caller_is_401_on_every_route_that_takes_a_caller(cn, method, path):
    concrete = path.replace("{subject_uuid}", "x").replace("{subscription_uuid}", "x")
    for name in ("endpoint_id", "subject_id", "dataset_id", "participant_id"):
        concrete = concrete.replace("{" + name + "}", "1")
    async with trusted_client() as c:
        response = await c.request(method, concrete, headers=identity_headers(cn), json={})
    assert response.status_code == 401, (method, path, response.text)
