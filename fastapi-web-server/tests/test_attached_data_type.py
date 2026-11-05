import pytest

import uudex_server.models as m
from uudex_server.repos import (
    AttachedDataTypeRepository,
    DatasetDefinitionRepository,
    DataTypeRepository,
)


@pytest.mark.asyncio
async def setup_data_type_and_dataset_definition(
    data_type_repo: DataTypeRepository, dataset_definition_repo: DatasetDefinitionRepository
):
    data_type = m.DataTypeCreate(
        data_type_uuid="uuid1",
        data_type_name="type1",
        description="desc1",
        schema_definition="schema1",
        specification_reference="spec1",
    )
    dataset_definition = m.DatasetDefinitionCreate(
        dataset_definition_uuid="uuid2", dataset_definition_name="definition1", description="desc2"
    )
    created_data_type = await data_type_repo.create(data_type)
    created_dataset_definition = await dataset_definition_repo.create(dataset_definition)
    return created_data_type, created_dataset_definition


# Tests for AttachedDataType
@pytest.mark.asyncio
async def test_create_attached_data_type(
    attached_data_type_repo: AttachedDataTypeRepository,
    data_type_repo: DataTypeRepository,
    dataset_definition_repo: DatasetDefinitionRepository,
):
    created_data_type, created_dataset_definition = await setup_data_type_and_dataset_definition(
        data_type_repo, dataset_definition_repo
    )

    attached_data_type = m.AttachedDataTypeCreate(
        dataset_definition_id=created_dataset_definition.dataset_definition_id,
        data_type_id=created_data_type.data_type_id,
    )
    result = await attached_data_type_repo.create(attached_data_type)
    assert result.dataset_definition_id == created_dataset_definition.dataset_definition_id
    assert result.data_type_id == created_data_type.data_type_id


@pytest.mark.asyncio
async def test_select_attached_data_type_by_ids(
    attached_data_type_repo: AttachedDataTypeRepository,
    data_type_repo: DataTypeRepository,
    dataset_definition_repo: DatasetDefinitionRepository,
):
    created_data_type, created_dataset_definition = await setup_data_type_and_dataset_definition(
        data_type_repo, dataset_definition_repo
    )

    attached_data_type = m.AttachedDataTypeCreate(
        dataset_definition_id=created_dataset_definition.dataset_definition_id,
        data_type_id=created_data_type.data_type_id,
    )
    await attached_data_type_repo.create(attached_data_type)
    result = await attached_data_type_repo.select_by_ids(
        dataset_definition_id=created_dataset_definition.dataset_definition_id,
        data_type_id=created_data_type.data_type_id,
    )
    assert result is not None
    assert result.dataset_definition_id == created_dataset_definition.dataset_definition_id
    assert result.data_type_id == created_data_type.data_type_id


@pytest.mark.asyncio
async def test_update_attached_data_type(
    attached_data_type_repo: AttachedDataTypeRepository,
    data_type_repo: DataTypeRepository,
    dataset_definition_repo: DatasetDefinitionRepository,
):
    created_data_type, created_dataset_definition = await setup_data_type_and_dataset_definition(
        data_type_repo, dataset_definition_repo
    )

    attached_data_type = m.AttachedDataTypeCreate(
        dataset_definition_id=created_dataset_definition.dataset_definition_id,
        data_type_id=created_data_type.data_type_id,
    )
    await attached_data_type_repo.create(attached_data_type)
    result = await attached_data_type_repo.select_by_ids(
        dataset_definition_id=created_dataset_definition.dataset_definition_id,
        data_type_id=created_data_type.data_type_id,
    )
    result.dataset_definition_id = 2
    updated_result = await attached_data_type_repo.update(result)
    assert updated_result.dataset_definition_id == 2


@pytest.mark.asyncio
async def test_delete_attached_data_type(
    attached_data_type_repo: AttachedDataTypeRepository,
    data_type_repo: DataTypeRepository,
    dataset_definition_repo: DatasetDefinitionRepository,
):
    created_data_type, created_dataset_definition = await setup_data_type_and_dataset_definition(
        data_type_repo, dataset_definition_repo
    )

    attached_data_type = m.AttachedDataTypeCreate(
        dataset_definition_id=created_dataset_definition.dataset_definition_id,
        data_type_id=created_data_type.data_type_id,
    )
    await attached_data_type_repo.create(attached_data_type)
    attached_data_type_remove = m.AttachedDataTypeDelete(
        dataset_definition_id=created_dataset_definition.dataset_definition_id,
        data_type_id=created_data_type.data_type_id,
    )
    await attached_data_type_repo.delete(attached_data_type_remove)
    result = await attached_data_type_repo.select_by_ids(
        dataset_definition_id=created_dataset_definition.dataset_definition_id,
        data_type_id=created_data_type.data_type_id,
    )
    assert result is None
