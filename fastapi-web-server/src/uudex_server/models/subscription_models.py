from sqlmodel import Field, Relationship

from uudex_server.models.subscription_subject_models import SubscriptionSubject

from .base import BaseModel, TimeStampMixin


class SubscriptionBase(BaseModel):
    subscription_uuid: str
    subscription_name: str
    subscription_state: str
    owner_endpoint_id: int


class Subscription(SubscriptionBase, TimeStampMixin, table=True):
    subscription_id: int | None = Field(default=None, primary_key=True)
    owner_endpoint_id: int = Field(foreign_key="endpoint.endpoint_id")

    subject_links: list[SubscriptionSubject] = Relationship(back_populates="subscription")  # type: ignore


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionDelete(BaseModel):
    subscription_id: int
