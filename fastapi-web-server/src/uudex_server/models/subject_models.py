from datetime import datetime

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field as PydanticField
from sqlmodel import Field, Relationship

from uudex_server.models.subscription_subject_models import SubscriptionSubject

from .base import BaseModel, TimeStampMixin


class SubjectBase(BaseModel):
    subject_uuid: str = Field(unique=True)
    subject_name: str
    dataset_instance_key: str
    subscription_type: str
    fulfillment_types_available: str
    full_queue_behavior: str | None
    max_queue_size_kb: int | None
    max_message_count: int | None
    priority: int | None
    backing_exchange_name: str
    owner_participant_id: int
    dataset_definition_id: int


class Subject(SubjectBase, TimeStampMixin, table=True):
    subject_id: int | None = Field(default=None, primary_key=True)
    owner_participant_id: int = Field(foreign_key="participant.participant_id", index=True)
    dataset_definition_id: int = Field(
        foreign_key="dataset_definition.dataset_definition_id", index=True
    )

    subscription_links: list[SubscriptionSubject] = Relationship(back_populates="subject")  # type: ignore

    # Relationship to datasets
    datasets: list["Dataset"] = Relationship(back_populates="subject")  # type: ignore


class SubjectCreate(SubjectBase):
    """Model for creating a new subject"""
    # Make some fields optional for creation
    subject_uuid: str | None = None  # Auto-generate if not provided
    owner_participant_id: int | None = None  # Set from user context
    dataset_definition_id: int | None = None  # Set from context or default


class SubjectUpdate(PydanticBaseModel):
    """Model for updating an existing subject"""
    subject_name: str | None = None
    dataset_instance_key: str | None = None
    subscription_type: str | None = None
    fulfillment_types_available: str | None = None
    full_queue_behavior: str | None = None
    max_queue_size_kb: int | None = None
    max_message_count: int | None = None
    priority: int | None = None
    backing_exchange_name: str | None = None


class SubjectDelete(BaseModel):
    subject_id: int


class SubjectQueueInfo(PydanticBaseModel):
    """Information about a subject's message queue"""
    subject_uuid: str = PydanticField(description="Subject UUID")
    subject_name: str = PydanticField(description="Subject name")
    exchange_name: str = PydanticField(description="Message broker exchange name")
    queue_count: int = PydanticField(description="Number of queues associated with this subject")
    total_messages: int = PydanticField(description="Total messages across all queues")
    total_consumers: int = PydanticField(description="Total consumers across all queues")


class QueueManagementRequest(PydanticBaseModel):
    """Request model for queue management operations"""
    action: str = PydanticField(description="Queue action: create, delete, purge, or info")
    queue_name: str | None = PydanticField(default=None, description="Specific queue name (optional)")


class QueueManagementResponse(PydanticBaseModel):
    """Response model for queue management operations"""
    success: bool = PydanticField(description="Whether the operation succeeded")
    message: str = PydanticField(description="Operation result message")
    queue_info: dict | None = PydanticField(default=None, description="Queue information if applicable")
    timestamp: datetime = PydanticField(default_factory=datetime.utcnow, description="Operation timestamp")


class SubjectWithMetrics(PydanticBaseModel):
    """Subject with additional metrics and queue information"""
    subject: Subject = PydanticField(description="Subject data")
    queue_info: SubjectQueueInfo = PydanticField(description="Queue metrics")
    subscriptions_count: int = PydanticField(description="Number of subscriptions attached")
    last_activity: datetime | None = PydanticField(default=None, description="Last message activity")


class BulkSubjectOperation(PydanticBaseModel):
    """Model for bulk operations on multiple subjects"""
    subject_uuids: list[str] = PydanticField(min_length=1, description="List of subject UUIDs to operate on")
    operation: str = PydanticField(description="Operation to perform: delete, activate, deactivate, purge_queues")


class BulkOperationResult(PydanticBaseModel):
    """Result of bulk operations"""
    successful: list[str] = PydanticField(description="Successfully processed subject UUIDs")
    failed: list[dict] = PydanticField(description="Failed operations with error details")
    total_processed: int = PydanticField(description="Total number of subjects processed")
    timestamp: datetime = PydanticField(default_factory=datetime.utcnow, description="Operation timestamp")
