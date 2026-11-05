import pytest

from uudex_server.models.data_type_models import DataTypeCreate, DataTypeDelete
from uudex_server.repos import DataTypeRepository


@pytest.mark.asyncio
async def test_create_data_type(data_type_repo: DataTypeRepository):
    data_type_create = DataTypeCreate(
        data_type_uuid="Myuuid1",
        data_type_name="Test DataType",
        description="This is a test description",
        schema_definition="{}",
        specification_reference="http://example.com",
    )
    created_data_type = await data_type_repo.create(data_type_create)
    assert created_data_type.data_type_name == "Test DataType"
    assert created_data_type.description == "This is a test description"
    assert created_data_type.schema_definition == "{}"
    assert created_data_type.specification_reference == "http://example.com"


@pytest.mark.asyncio
async def test_select_all_data_types(data_type_repo: DataTypeRepository):
    data_types = await data_type_repo.select_all()
    assert isinstance(data_types, list)


@pytest.mark.asyncio
async def test_select_by_id(data_type_repo: DataTypeRepository):
    data_type_create = DataTypeCreate(
        data_type_uuid="Myuuid2",
        data_type_name="Test DataType for Select",
        description="This is a test for select",
        schema_definition="{}",
        specification_reference="http://example.com",
    )
    created_data_type = await data_type_repo.create(data_type_create)
    selected_data_type = await data_type_repo.select_by_id(created_data_type.data_type_id)
    assert selected_data_type is not None
    assert selected_data_type.data_type_name == "Test DataType for Select"


@pytest.mark.asyncio
async def test_update_data_type(data_type_repo: DataTypeRepository):
    data_type_create = DataTypeCreate(
        data_type_uuid="Myuuid3",
        data_type_name="Test DataType for Update",
        description="This is a test for update",
        schema_definition="{}",
        specification_reference="http://example.com",
    )
    created_data_type = await data_type_repo.create(data_type_create)
    created_data_type.data_type_name = "Updated DataType"
    updated_data_type = await data_type_repo.update(created_data_type)
    assert updated_data_type.data_type_name == "Updated DataType"


@pytest.mark.asyncio
async def test_delete_data_type(data_type_repo: DataTypeRepository):
    data_type_create = DataTypeCreate(
        data_type_uuid="Myuuid4",
        data_type_name="Test DataType for Delete",
        description="This is a test for delete",
        schema_definition="{}",
        specification_reference="http://example.com",
    )
    created_data_type = await data_type_repo.create(data_type_create)
    data_type_remove = DataTypeDelete(data_type_id=created_data_type.data_type_id)
    await data_type_repo.delete(data_type_remove)
    deleted_data_type = await data_type_repo.select_by_id(created_data_type.data_type_id)
    assert deleted_data_type is None
