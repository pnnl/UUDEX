import uuid

import pytest
from httpx import AsyncClient

from conftest import identity_headers
from test_caller import seed_endpoint, seed_participant, seed_subject, trusted_client

XFAIL_18_MESSAGE = pytest.mark.xfail(
    strict=True,
    reason="#18: discovery returns a different no-certificate message; fits no listed class",
)


@pytest.mark.asyncio
async def test_discover_subjects_no_auth(client: AsyncClient):
    """Test discover subjects endpoint without authentication returns 401"""
    response = await client.get("/subjects/discover")
    assert response.status_code == 401
    assert response.json() == "No certificate detected."


@pytest.mark.asyncio
async def test_discover_subjects_v1_no_auth(client: AsyncClient):
    """Test v1 discover subjects endpoint without authentication returns 401"""
    response = await client.get("/v1/subjects/discover")
    assert response.status_code == 401
    assert response.json() == "No certificate detected."


@pytest.mark.asyncio
async def test_discover_subjects_non_admin_sees_only_own_participant(setup_test_env):
    cn = f"discover-{uuid.uuid4().hex[:8]}"
    mine, other = await seed_participant(), await seed_participant()
    await seed_endpoint(mine, cn)
    mine_id, other_id = await seed_subject(mine), await seed_subject(other)

    async with trusted_client() as c:
        response = await c.get("/subjects/discover", headers=identity_headers(cn))

    assert response.status_code == 200
    assert {s["subject_id"] for s in response.json()} == {mine_id}
    assert other_id not in {s["subject_id"] for s in response.json()}


@pytest.mark.asyncio
async def test_discover_subjects_admin_sees_every_participant(setup_test_env):
    cn = f"discover-{uuid.uuid4().hex[:8]}"
    mine, other = await seed_participant(), await seed_participant()
    await seed_endpoint(mine, cn, admin=True)
    mine_id, other_id = await seed_subject(mine), await seed_subject(other)

    async with trusted_client() as c:
        response = await c.get("/subjects/discover", headers=identity_headers(cn))

    assert response.status_code == 200
    assert {mine_id, other_id} <= {s["subject_id"] for s in response.json()}


@XFAIL_18_MESSAGE
@pytest.mark.asyncio
async def test_discover_subjects_invalid_cert(client: AsyncClient):
    """Test discover subjects endpoint with invalid certificate"""
    headers = identity_headers(subject="")

    response = await client.get("/subjects/discover", headers=headers)
    assert response.status_code == 401
    assert response.json() == "No Common Name found in certificate."


@pytest.mark.asyncio
async def test_discover_subjects_missing_cn(client: AsyncClient):
    """Test discover subjects endpoint with certificate missing CN"""
    headers = identity_headers(subject="O=Test Org,C=US")

    response = await client.get("/subjects/discover", headers=headers)
    assert response.status_code == 401
    assert response.json() == "No Common Name found in certificate."
