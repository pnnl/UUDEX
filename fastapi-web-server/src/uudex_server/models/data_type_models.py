from datetime import datetime

from sqlmodel import Field, Relationship

from uudex_server.models.attached_data_type_models import AttachedDataType

from .base import BaseModel, TimeStampMixin


class DataTypeBase(BaseModel):
    data_type_uuid: str
    data_type_name: str
    description: str
    schema_definition: str
    specification_reference: str


class DataType(DataTypeBase, TimeStampMixin, table=True):
    __tablename__ = "data_type"

    data_type_id: int | None = Field(default=None, primary_key=True)
    dataset_definitions: list["DatasetDefinition"] = Relationship(  # type: ignore
        back_populates="data_types", link_model=AttachedDataType
    )
    # subject_uuid: str = Field(unique=True)
    # subject_short_name: str
    # subject_long_name: str
    # description: str
    # root_org_sw: bool
    # active_sw: bool
    # create_datetime: datetime = Field(default_factory=lambda: datetime.utcnow())


class DataTypeCreate(DataTypeBase):
    pass


class DataTypeDelete(BaseModel):
    data_type_id: int


class DataTypeHistoryBase(BaseModel):
    description: str
    schema_definition: str
    specification_reference: str | None = None
    version_number: int


class DataTypeHistory(DataTypeHistoryBase, TimeStampMixin, table=True):
    __tablename__ = "data_type_history"

    data_type_id: int = Field(foreign_key="data_type.data_type_id", primary_key=True)


class DataTypeHistoryCreate(DataTypeHistoryBase):
    data_type_id: int


class DataTypeHistoryDelete(BaseModel):
    data_type_id: int
    # Assuming timestamp is part of the PK in deletion
    created_datetime: datetime
