import uuid

import pytest

from uudex_server.models import ParticipantCreate, ParticipantDelete
from uudex_server.repos import ParticipantRepository


@pytest.mark.asyncio
async def test_create_participant(participant_repo: ParticipantRepository):
    participant_create = ParticipantCreate(
        participant_uuid=str(uuid.uuid4()),
        participant_short_name="Test Participant",
        participant_long_name="Test Participant Long",
        description="This is a test participant",
        root_org_sw="Y",
        active_sw="Y",
    )
    created_participant = await participant_repo.create(participant_create)
    assert created_participant.participant_short_name == "Test Participant"
    assert created_participant.participant_long_name == "Test Participant Long"
    assert created_participant.description == "This is a test participant"
    assert created_participant.root_org_sw == "Y"
    assert created_participant.active_sw == "Y"


@pytest.mark.asyncio
async def test_select_all_participants(participant_repo: ParticipantRepository):
    participants = await participant_repo.select_all()
    assert isinstance(participants, list)


@pytest.mark.asyncio
async def test_select_by_id(participant_repo: ParticipantRepository):
    participant_create = ParticipantCreate(
        participant_uuid=str(uuid.uuid4()),
        participant_short_name="Test Participant for Select",
        participant_long_name="Test Participant Long for Select",
        description="This is a test participant for select",
        root_org_sw="Y",
        active_sw="Y",
    )
    created_participant = await participant_repo.create(participant_create)
    selected_participant = await participant_repo.select_by_id(created_participant.participant_id)
    assert selected_participant is not None
    assert selected_participant.participant_short_name == "Test Participant for Select"


@pytest.mark.asyncio
async def test_update_participant(participant_repo: ParticipantRepository):
    participant_create = ParticipantCreate(
        participant_uuid=str(uuid.uuid4()),
        participant_short_name="Test Participant for Update",
        participant_long_name="Test Participant Long for Update",
        description="This is a test participant for update",
        root_org_sw="Y",
        active_sw="Y",
    )
    created_participant = await participant_repo.create(participant_create)
    created_participant.participant_short_name = "Updated Participant"
    updated_participant = await participant_repo.update(created_participant)
    assert updated_participant.participant_short_name == "Updated Participant"


@pytest.mark.asyncio
async def test_delete_participant(participant_repo: ParticipantRepository):
    participant_create = ParticipantCreate(
        participant_uuid=str(uuid.uuid4()),
        participant_short_name="Test Participant for Delete",
        participant_long_name="Test Participant Long for Delete",
        description="This is a test participant for delete",
        root_org_sw="Y",
        active_sw="Y",
    )
    created_participant = await participant_repo.create(participant_create)
    participant_remove = ParticipantDelete(participant_id=created_participant.participant_id)
    await participant_repo.delete(participant_remove)
    deleted_participant = await participant_repo.select_by_id(created_participant.participant_id)
    assert deleted_participant is None
