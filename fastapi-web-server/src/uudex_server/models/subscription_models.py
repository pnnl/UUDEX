from pydantic import field_validator
from sqlmodel import Field, Relationship

from uudex_server.models.subscription_subject_models import SubscriptionSubject

from .base import BaseModel, TimeStampMixin


class SubscriptionBase(BaseModel):
    subscription_uuid: str = Field(unique=True)
    subscription_name: str
    subscription_state: str
    owner_endpoint_id: int


class Subscription(SubscriptionBase, TimeStampMixin, table=True):
    subscription_id: int | None = Field(default=None, primary_key=True)
    owner_endpoint_id: int = Field(foreign_key="endpoint.endpoint_id")

    subject_links: list[SubscriptionSubject] = Relationship(back_populates="subscription")  # type: ignore


SUBSCRIPTION_STATES = ("ACTIVE", "PAUSED")


class SubscriptionCreate(SubscriptionBase):
    # Accepted for older clients and ignored: the server picks the uuid, so a caller cannot
    # claim one that another endpoint's subscription already uses.
    subscription_uuid: str | None = None  # type: ignore[assignment]

    @field_validator("subscription_state")
    @classmethod
    def _known_state(cls, value: str) -> str:
        state = value.upper()
        if state not in SUBSCRIPTION_STATES:
            raise ValueError(f"must be one of {', '.join(SUBSCRIPTION_STATES)}")
        return state


class SubscriptionDelete(BaseModel):
    subscription_id: int
