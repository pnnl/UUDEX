import uuid

import pytest
from sqlmodel import Session

from uudex_server.models.dataset_definition_models import (
    DatasetDefinitionCreate,
    DatasetDefinitionDelete,
)
from uudex_server.repos.dataset_definition_repository import DatasetDefinitionRepository


@pytest.mark.asyncio
async def test_create_dataset_definition(dataset_definition_repo: DatasetDefinitionRepository):
    dataset_definition_create = DatasetDefinitionCreate(
        dataset_definition_uuid=str(uuid.uuid4()),
        dataset_definition_name="Test Dataset Definition",
        description="This is a test description",
    )
    created_dataset_definition = await dataset_definition_repo.create(dataset_definition_create)
    assert created_dataset_definition.dataset_definition_name == "Test Dataset Definition"
    assert created_dataset_definition.description == "This is a test description"


@pytest.mark.asyncio
async def test_select_all_dataset_definitions(
    dataset_definition_repo: DatasetDefinitionRepository, session: Session
):
    dataset_definitions = await dataset_definition_repo.select_all()
    assert isinstance(dataset_definitions, list)


@pytest.mark.asyncio
async def test_select_by_id(dataset_definition_repo: DatasetDefinitionRepository):
    dataset_definition_create = DatasetDefinitionCreate(
        dataset_definition_uuid=str(uuid.uuid4()),
        dataset_definition_name="Test Dataset Definition for Select",
        description="This is a test for select",
    )
    created_dataset_definition = await dataset_definition_repo.create(dataset_definition_create)
    selected_dataset_definition = await dataset_definition_repo.select_by_id(
        created_dataset_definition.dataset_definition_id
    )
    assert selected_dataset_definition is not None
    assert (
        selected_dataset_definition.dataset_definition_name == "Test Dataset Definition for Select"
    )


@pytest.mark.asyncio
async def test_update_dataset_definition(dataset_definition_repo: DatasetDefinitionRepository):
    dataset_definition_create = DatasetDefinitionCreate(
        dataset_definition_uuid=str(uuid.uuid4()),
        dataset_definition_name="Test Dataset Definition for Update",
        description="This is a test for update",
    )
    created_dataset_definition = await dataset_definition_repo.create(dataset_definition_create)
    created_dataset_definition.dataset_definition_name = "Updated Dataset Definition"
    updated_dataset_definition = await dataset_definition_repo.update(created_dataset_definition)
    assert updated_dataset_definition.dataset_definition_name == "Updated Dataset Definition"


@pytest.mark.asyncio
async def test_delete_dataset_definition(dataset_definition_repo: DatasetDefinitionRepository):
    dataset_definition_create = DatasetDefinitionCreate(
        dataset_definition_uuid=str(uuid.uuid4()),
        dataset_definition_name="Test Dataset Definition for Delete",
        description="This is a test for delete",
    )
    created_dataset_definition = await dataset_definition_repo.create(dataset_definition_create)
    dataset_definition_remove = DatasetDefinitionDelete(
        dataset_definition_id=created_dataset_definition.dataset_definition_id
    )
    await dataset_definition_repo.delete(dataset_definition_remove)
    deleted_dataset_definition = await dataset_definition_repo.select_by_id(
        created_dataset_definition.dataset_definition_id
    )
    assert deleted_dataset_definition is None
