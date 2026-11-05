import pytest

import uudex_server.models as m
from uudex_server.repos import SubjectRepository


# Subject Tests
@pytest.mark.asyncio
async def test_create_subject(subject_repo: SubjectRepository):
    subject = m.SubjectCreate(
        subject_uuid="uuid1",
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
    result = await subject_repo.create(subject)
    assert result.subject_uuid == "uuid1"
    assert result.subject_name == "name1"


@pytest.mark.asyncio
async def test_select_subject_by_id(subject_repo: SubjectRepository):
    subject = m.SubjectCreate(
        subject_uuid="uuid1",
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
    await subject_repo.create(subject)
    result = await subject_repo.select_by_id(1)
    assert result is not None
    assert result.subject_uuid == "uuid1"


@pytest.mark.asyncio
async def test_update_subject(subject_repo: SubjectRepository):
    subject = m.SubjectCreate(
        subject_uuid="uuid1",
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
    created_subject = await subject_repo.create(subject)
    created_subject.subject_name = "updated_name"
    result = await subject_repo.update(created_subject)
    assert result.subject_name == "updated_name"


@pytest.mark.asyncio
async def test_delete_subject(subject_repo: SubjectRepository):
    subject = m.SubjectCreate(
        subject_uuid="uuid1",
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
    created_subject = await subject_repo.create(subject)
    subject_remove = m.SubjectDelete(subject_id=created_subject.subject_id)
    await subject_repo.delete(subject_remove)
    result = await subject_repo.select_by_id(created_subject.subject_id)
    assert result is None
