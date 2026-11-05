from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship

from .base import BaseModel


class SubscriptionSubjectBase(BaseModel):
    preferred_fulfillment_type: str
    backing_queue_name: str
    subject_id: int
    subscription_id: int


class SubscriptionSubject(SubscriptionSubjectBase, table=True):
    __tablename__ = "subscription_subject"
    __table_args__ = (
        UniqueConstraint("subject_id", "subscription_id", name="uix_subject_subscription"),
    )

    subscription_subject_id: int | None = Field(default=None, primary_key=True)
    subject_id: int = Field(foreign_key="subject.subject_id")
    subscription_id: int = Field(foreign_key="subscription.subscription_id")

    subject: "Subject" = Relationship(back_populates="subscription_links")  # type: ignore
    subscription: "Subscription" = Relationship(back_populates="subject_links")  # type: ignore


class SubscriptionSubjectCreate(SubscriptionSubjectBase):
    pass


class SubscriptionSubjectDelete(BaseModel):
    subscription_subject_id: int
