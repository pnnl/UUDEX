from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MessageContent(BaseModel):
    """Individual message from the message broker."""

    payload: str = Field(description="The message content/payload")
    message_id: str | None = Field(default=None, description="Unique message identifier")
    timestamp: datetime | None = Field(default=None, description="Message timestamp")
    properties: dict[str, Any] | None = Field(default=None, description="Additional message properties")


class MessageConsumeRequest(BaseModel):
    """Request model for consuming messages from a subscription."""

    count: int = Field(default=1, ge=1, le=100, description="Number of messages to consume (1-100)")
    timeout: int | None = Field(default=30, ge=1, le=300, description="Timeout in seconds (1-300)")


class MessageConsumeResponse(BaseModel):
    """Response model for message consumption."""

    messages: list[MessageContent] = Field(description="List of consumed messages")
    total_consumed: int = Field(description="Total number of messages consumed")
    subscription_uuid: str = Field(description="UUID of the subscription")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class MessagePublishRequest(BaseModel):
    """Request model for publishing messages to a subject."""

    messages: list[str] = Field(min_length=1, max_length=50, description="List of message payloads to publish")
    payload_encoding: str = Field(default="string", description="Encoding type for payloads")


class MessagePublishResponse(BaseModel):
    """Response model for message publishing."""

    published_count: int = Field(description="Number of messages successfully published")
    subject_uuid: str = Field(description="UUID of the subject")
    message_ids: list[str] = Field(description="List of message IDs for published messages")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
