"""Participant routes: listing needs a known caller, creating needs a UUDEX administrator."""

import uuid

import pytest
from sqlmodel import select

import uudex_server.models as m
from conftest import identity_headers
from test_caller import seed_endpoint, seed_participant, trusted_client
from uudex_server.services.database_service import get_db_session


@pytest.fixture
def cn(setup_test_env):
    return f"caller-{uuid.uuid4().hex[:8]}"


def _body() -> dict:
    return {
        "participant_uuid": str(uuid.uuid4()),
        "participant_short_name": "new",
        "participant_long_name": "new participant",
        "description": "created by the access tests",
        "root_org_sw": "Y",
        "active_sw": "Y",
    }


async def _rows_with_uuid(participant_uuid: str) -> list[m.Participant]:
    async with get_db_session() as session:
        result = await session.execute(
            select(m.Participant).where(m.Participant.participant_uuid == participant_uuid)
        )
        return list(result.scalars())


async def test_unknown_caller_cannot_list_participants(cn):
    async with trusted_client() as c:
        response = await c.get("/participants/", headers=identity_headers(cn))
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized: Invalid certificate"}


async def test_unknown_caller_cannot_create_participant(cn):
    body = _body()
    async with trusted_client() as c:
        response = await c.post("/participants/", json=body, headers=identity_headers(cn))
    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized: Invalid certificate"}
    assert await _rows_with_uuid(body["participant_uuid"]) == []


async def test_non_admin_cannot_create_participant(cn):
    await seed_endpoint(await seed_participant(), cn)
    body = _body()
    async with trusted_client() as c:
        response = await c.post("/participants/", json=body, headers=identity_headers(cn))
    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator access required"}
    assert await _rows_with_uuid(body["participant_uuid"]) == []


async def test_admin_creates_participant(cn):
    await seed_endpoint(await seed_participant(), cn, admin=True)
    body = _body()
    async with trusted_client() as c:
        response = await c.post("/participants/", json=body, headers=identity_headers(cn))
    assert response.status_code == 200
    rows = await _rows_with_uuid(body["participant_uuid"])
    assert len(rows) == 1
    for field, value in body.items():
        assert getattr(rows[0], field) == value


async def test_known_non_admin_lists_participants(cn):
    participant_id = await seed_participant()
    await seed_endpoint(participant_id, cn)
    async with get_db_session() as session:
        seeded = await session.get(m.Participant, participant_id)
        seeded_uuid = seeded.participant_uuid
    async with trusted_client() as c:
        response = await c.get("/participants/", headers=identity_headers(cn))
    assert response.status_code == 200
    assert seeded_uuid in {p["participant_uuid"] for p in response.json()}
