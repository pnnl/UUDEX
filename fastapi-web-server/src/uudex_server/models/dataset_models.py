import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Field

from .base import BaseModel, TimeStampMixin


class DatasetBase(BaseModel):
    dataset_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()), nullable=False)
    dataset_name: str
    description: str
    properties: str
    payload: str  # Base64 encoded string for API compatibility
    payload_size: int
    payload_md5_hash: str
    payload_compression_algorithm: str
    version_number: int


# class Dataset(DatasetBase, TimeStampMixin, table=True):
#     __tablename__ = "dataset"
#
#     dataset_id: Optional[int] = Field(default=None, primary_key=True)
#     owner_participant_id: int = Field(foreign_key="participant.participant_id", primary_key=True)
#     subject_id: int = Field(foreign_key="subject.subject_id", primary_key=True)
#
#
class DatasetCreate(DatasetBase):
    owner_participant_id: int | None = None
    subject_id: int


class DatasetRead(BaseModel):
    """Dataset metadata without payload for efficient listing/browsing"""

    dataset_id: int
    dataset_uuid: str
    dataset_name: str
    description: str
    properties: str | None = None
    payload_size: int
    payload_md5_hash: str
    payload_compression_algorithm: str
    version_number: int
    owner_participant_id: int
    subject_id: int
    create_datetime: datetime


class DatasetDelete(BaseModel):
    dataset_id: int


from sqlmodel import Field, Relationship


class Dataset(TimeStampMixin, table=True):
    __tablename__ = "dataset"
    __table_args__ = {"extend_existing": True}

    dataset_id: int | None = Field(default=None, primary_key=True)
    dataset_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()), nullable=False)
    dataset_name: str
    description: str
    properties: str
    payload: bytes
    payload_size: int
    payload_md5_hash: str
    payload_compression_algorithm: str
    version_number: int
    owner_participant_id: int = Field(foreign_key="participant.participant_id")
    subject_id: int = Field(foreign_key="subject.subject_id")

    owner: Optional["Participant"] = Relationship(back_populates="datasets")
    subject: Optional["Subject"] = Relationship(back_populates="datasets")
