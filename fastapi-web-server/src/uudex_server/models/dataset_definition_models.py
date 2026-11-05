from sqlmodel import Field, Relationship

from uudex_server.models.attached_data_type_models import AttachedDataType

from .base import BaseModel, TimeStampMixin


class DatasetDefinitionBase(BaseModel):
    dataset_definition_uuid: str
    dataset_definition_name: str
    description: str


class DatasetDefinition(DatasetDefinitionBase, TimeStampMixin, table=True):
    __tablename__ = "dataset_definition"

    dataset_definition_id: int | None = Field(default=None, primary_key=True)
    data_types: list["DataType"] = Relationship(  # type: ignore
        back_populates="dataset_definitions", link_model=AttachedDataType
    )


class DatasetDefinitionCreate(DatasetDefinitionBase):
    pass


class DatasetDefinitionDelete(BaseModel):
    dataset_definition_id: int
