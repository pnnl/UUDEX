import uuid

import pytest

import uudex_server.models as m
from uudex_server.repos import DatasetRepository, ParticipantRepository, SubjectRepository


@pytest.mark.asyncio
async def setup_participant_and_subject(
    participant_repo: ParticipantRepository, subject_repo: SubjectRepository
):
    participant = m.ParticipantCreate(
        participant_uuid=str(uuid.uuid4()),
        participant_short_name="short1",
        participant_long_name="long1",
        description="desc1",
        root_org_sw="Y",
        active_sw="Y",
    )
    subject = m.SubjectCreate(
        subject_uuid=str(uuid.uuid4()),
        subject_name="name1",
        dataset_instance_key="key1",
        subscription_type="sub_type1",
        fulfillment_types_available="fulfillment1",
        full_queue_behavior="behavior1",
        max_queue_size_kb=1000,
        max_message_count=10,
        priority=1,
        backing_exchange_name="exchange1",
        owner_participant_id=1,
        dataset_definition_id=1,
    )
    created_participant = await participant_repo.create(participant)
    created_subject = await subject_repo.create(subject)
    return created_participant, created_subject


# Dataset Tests
@pytest.mark.asyncio
async def test_create_dataset(
    dataset_repo: DatasetRepository,
    participant_repo: ParticipantRepository,
    subject_repo: SubjectRepository,
):
    created_participant, created_subject = await setup_participant_and_subject(
        participant_repo, subject_repo
    )
    dataset_create = m.DatasetCreate(
        dataset_uuid=str(uuid.uuid4()),
        dataset_name="Test Dataset",
        description="This is a test description",
        properties="{}",
        payload=b"",
        payload_size=0,
        payload_md5_hash="md5hash",
        payload_compression_algorithm="algorithm",
        version_number=1,
        owner_participant_id=created_participant.participant_id,
        subject_id=created_subject.subject_id,
    )
    created_dataset = await dataset_repo.create(dataset_create)
    assert created_dataset.dataset_name == "Test Dataset"
    assert created_dataset.description == "This is a test description"


@pytest.mark.asyncio
async def test_select_all_datasets(dataset_repo: DatasetRepository):
    datasets = await dataset_repo.select_all()
    assert isinstance(datasets, list)


@pytest.mark.asyncio
async def test_select_dataset_by_id(
    dataset_repo: DatasetRepository,
    participant_repo: ParticipantRepository,
    subject_repo: SubjectRepository,
):
    created_participant, created_subject = await setup_participant_and_subject(
        participant_repo, subject_repo
    )
    dataset_create = m.DatasetCreate(
        dataset_uuid=str(uuid.uuid4()),
        dataset_name="Test Dataset for Select",
        description="This is a test for select",
        properties="{}",
        payload=b"",
        payload_size=0,
        payload_md5_hash="md5hash",
        payload_compression_algorithm="algorithm",
        version_number=1,
        owner_participant_id=created_participant.participant_id,
        subject_id=created_subject.subject_id,
    )
    created_dataset = await dataset_repo.create(dataset_create)
    selected_dataset = await dataset_repo.select_by_id(created_dataset.dataset_id)
    assert selected_dataset is not None
    assert selected_dataset.dataset_name == "Test Dataset for Select"
    assert created_dataset.owner.participant_id == created_participant.participant_id
    assert created_dataset.subject.subject_id == created_subject.subject_id


@pytest.mark.asyncio
async def test_update_dataset(
    dataset_repo: DatasetRepository,
    participant_repo: ParticipantRepository,
    subject_repo: SubjectRepository,
):
    created_participant, created_subject = await setup_participant_and_subject(
        participant_repo, subject_repo
    )
    dataset_create = m.DatasetCreate(
        dataset_uuid=str(uuid.uuid4()),
        dataset_name="Test Dataset for Update",
        description="This is a test for update",
        properties="{}",
        payload=b"",
        payload_size=0,
        payload_md5_hash="md5hash",
        payload_compression_algorithm="algorithm",
        version_number=1,
        owner_participant_id=created_participant.participant_id,
        subject_id=created_subject.subject_id,
    )
    created_dataset = await dataset_repo.create(dataset_create)
    created_dataset.dataset_name = "Updated Dataset"
    updated_dataset = await dataset_repo.update(created_dataset)
    assert updated_dataset.dataset_name == "Updated Dataset"


@pytest.mark.asyncio
async def test_delete_dataset(
    dataset_repo: DatasetRepository,
    participant_repo: ParticipantRepository,
    subject_repo: SubjectRepository,
):
    created_participant, created_subject = await setup_participant_and_subject(
        participant_repo, subject_repo
    )
    dataset_create = m.DatasetCreate(
        dataset_uuid=str(uuid.uuid4()),
        dataset_name="Test Dataset for Delete",
        description="This is a test for delete",
        properties="{}",
        payload=b"",
        payload_size=0,
        payload_md5_hash="md5hash",
        payload_compression_algorithm="algorithm",
        version_number=1,
        owner_participant_id=created_participant.participant_id,
        subject_id=created_subject.subject_id,
    )
    created_dataset = await dataset_repo.create(dataset_create)
    dataset_remove = m.DatasetDelete(dataset_id=created_dataset.dataset_id)
    await dataset_repo.delete(dataset_remove)
    result = await dataset_repo.select_by_id(created_dataset.dataset_id)
    assert result is None
