from __future__ import annotations
import uuid
from datetime import datetime

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field as PydanticField
from sqlmodel import Field, Relationship

from .base import ActiveSwitchMixin, BaseModel, TimeStampMixin
from .common_types import YNSwitch
from .participant_models import Participant


class EndPointBase(BaseModel):
    endpoint_uuid: str
    endpoint_user_name: str
    certificate_dn: str
    description: str
    uudex_administrator_sw: YNSwitch = Field(max_length=1)  # 'Y' or 'N'
    participant_administrator_sw: YNSwitch = Field(max_length=1)  # 'Y' or 'N'
    participant_id: int


EndpointJwt = str


class EndPoint(EndPointBase, TimeStampMixin, ActiveSwitchMixin, table=True):
    __tablename__ = "endpoint"

    endpoint_id: int | None = Field(default=None, primary_key=True)
    participant_id: int = Field(foreign_key="participant.participant_id")

    # Use a direct string for the relationship
    participant: Participant = Relationship(back_populates="endpoints")


class EndPointCreate(EndPointBase):
    """Model for creating a new endpoint/certificate"""
    # Make UUID optional for auto-generation
    endpoint_uuid: str | None = None
    

class EndPointUpdate(PydanticBaseModel):
    """Model for updating an existing endpoint"""
    endpoint_user_name: str | None = None
    certificate_dn: str | None = None
    description: str | None = None
    uudex_administrator_sw: YNSwitch | None = None
    participant_administrator_sw: YNSwitch | None = None
    participant_id: int | None = None


class EndPointDelete(BaseModel):
    endpoint_id: int


class CertificateCreateRequest(PydanticBaseModel):
    """Admin request to create a new certificate/endpoint"""
    certificate_dn: str = PydanticField(description="Certificate Distinguished Name (CN=...)")
    endpoint_user_name: str = PydanticField(description="Human-readable username")
    description: str = PydanticField(description="Description of the endpoint/certificate")
    participant_id: int = PydanticField(description="Participant ID this endpoint belongs to")
    uudex_administrator_sw: YNSwitch = PydanticField(default="N", description="UUDEX admin privileges (Y/N)")
    participant_administrator_sw: YNSwitch = PydanticField(default="N", description="Participant admin privileges (Y/N)")


class CertificateResponse(PydanticBaseModel):
    """Response for certificate operations"""
    success: bool = PydanticField(description="Whether the operation succeeded")
    message: str = PydanticField(description="Operation result message")
    endpoint: EndPoint | None = PydanticField(default=None, description="Created/updated endpoint data")
    timestamp: datetime = PydanticField(default_factory=datetime.utcnow, description="Operation timestamp")


class BulkCertificateOperation(PydanticBaseModel):
    """Model for bulk operations on multiple certificates/endpoints"""
    endpoint_ids: list[int] = PydanticField(min_length=1, description="List of endpoint IDs to operate on")
    operation: str = PydanticField(description="Operation to perform: activate, deactivate, delete, grant_admin, revoke_admin")


class BulkCertificateResult(PydanticBaseModel):
    """Result of bulk certificate operations"""
    successful: list[int] = PydanticField(description="Successfully processed endpoint IDs")
    failed: list[dict] = PydanticField(description="Failed operations with error details")
    total_processed: int = PydanticField(description="Total number of endpoints processed")
    timestamp: datetime = PydanticField(default_factory=datetime.utcnow, description="Operation timestamp")


class CertificateDownloadRequest(PydanticBaseModel):
    """Request for downloading certificate files"""
    format: str = PydanticField(default="p12", description="Certificate format: p12, crt, or pem")
    include_private_key: bool = PydanticField(default=False, description="Include private key in download (for PEM format)")


class CertificateFileInfo(PydanticBaseModel):
    """Information about available certificate files"""
    endpoint_id: int = PydanticField(description="Endpoint ID")
    certificate_dn: str = PydanticField(description="Certificate Distinguished Name")
    client_name: str = PydanticField(description="Client name extracted from DN")
    available_formats: list[str] = PydanticField(description="Available certificate formats")
    files: dict[str, str] = PydanticField(description="Available files and their paths")
    created_date: datetime | None = PydanticField(default=None, description="Certificate creation date")
