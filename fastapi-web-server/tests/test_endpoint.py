import uuid

import pytest

import uudex_server.models as m
from uudex_server.repos import EndpointRepository, ParticipantRepository


@pytest.mark.asyncio
async def setup_participant(participant_repo: ParticipantRepository) -> m.Participant:
    participant = m.ParticipantCreate(
        participant_uuid=str(uuid.uuid4()),
        participant_short_name="short1",
        participant_long_name="long1",
        description="desc1",
        root_org_sw="Y",
        active_sw="Y",
    )
    created_participant = await participant_repo.create(participant)
    return created_participant


@pytest.mark.asyncio
async def test_create_endpoint(
    endpoint_repo: EndpointRepository, participant_repo: ParticipantRepository
):
    participant_created = await setup_participant(participant_repo=participant_repo)
    endpoint = m.EndPointCreate(
        endpoint_uuid="uuid1",
        endpoint_user_name="user1",
        certificate_dn="dn1",
        description="desc1",
        uudex_administrator_sw="Y",
        participant_administrator_sw="Y",
        participant_id=participant_created.participant_id,
    )
    result = await endpoint_repo.create(endpoint)
    assert result.endpoint_uuid == "uuid1"
    assert result.endpoint_user_name == "user1"


@pytest.mark.asyncio
async def test_select_endpoint_by_id(
    endpoint_repo: EndpointRepository, participant_repo: ParticipantRepository
):
    participant_created = await setup_participant(participant_repo=participant_repo)
    endpoint = m.EndPointCreate(
        endpoint_uuid="uuid1",
        endpoint_user_name="user1",
        certificate_dn="dn1",
        description="desc1",
        uudex_administrator_sw="Y",
        participant_administrator_sw="Y",
        participant_id=participant_created.participant_id,
    )
    created_endpoint = await endpoint_repo.create(endpoint)
    result = await endpoint_repo.select_by_id(created_endpoint.endpoint_id)
    assert result is not None
    assert result.endpoint_uuid == "uuid1"


@pytest.mark.asyncio
async def test_update_endpoint(
    endpoint_repo: EndpointRepository, participant_repo: ParticipantRepository
):
    participant_created = await setup_participant(participant_repo=participant_repo)
    endpoint = m.EndPointCreate(
        endpoint_uuid="uuid1",
        endpoint_user_name="user1",
        certificate_dn="dn1",
        description="desc1",
        uudex_administrator_sw="Y",
        participant_administrator_sw="Y",
        participant_id=participant_created.participant_id,
    )
    created_endpoint = await endpoint_repo.create(endpoint)
    created_endpoint.endpoint_user_name = "updated_user"
    result = await endpoint_repo.update(created_endpoint)
    assert result.endpoint_user_name == "updated_user"


@pytest.mark.asyncio
async def test_delete_endpoint(
    endpoint_repo: EndpointRepository, participant_repo: ParticipantRepository
):
    participant_created = await setup_participant(participant_repo=participant_repo)
    endpoint = m.EndPointCreate(
        endpoint_uuid="uuid1",
        endpoint_user_name="user1",
        certificate_dn="dn1",
        description="desc1",
        uudex_administrator_sw="Y",
        participant_administrator_sw="Y",
        participant_id=participant_created.participant_id,
    )
    created_endpoint = await endpoint_repo.create(endpoint)
    endpoint_remove = m.EndPointDelete(endpoint_id=created_endpoint.endpoint_id)
    await endpoint_repo.delete(endpoint_remove)
    result = await endpoint_repo.select_by_id(created_endpoint.endpoint_id)
    assert result is None
