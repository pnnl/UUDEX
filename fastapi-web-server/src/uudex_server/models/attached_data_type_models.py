from sqlmodel import Field

from .base import BaseModel


class AttachedDataTypeBase(BaseModel):
    pass


class AttachedDataType(AttachedDataTypeBase, table=True):
    __tablename__ = "attached_data_type"

    dataset_definition_id: int = Field(
        foreign_key="dataset_definition.dataset_definition_id", primary_key=True
    )

    data_type_id: int = Field(foreign_key="data_type.data_type_id", primary_key=True)


class AttachedDataTypeCreate(AttachedDataType):
    pass
    # dataset_definition_id: int
    # data_type_id: int


class AttachedDataTypeDelete(AttachedDataType):
    pass
    # dataset_definition_id: int
    # data_type_id = int
