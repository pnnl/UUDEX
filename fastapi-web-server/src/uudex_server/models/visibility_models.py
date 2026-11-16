from sqlalchemy import Column, ForeignKey
from sqlmodel import Field

from .base import BaseModel


class ParticipantVisibilityBase(BaseModel):
    pass


class ParticipantVisibility(ParticipantVisibilityBase, table=True):
    __tablename__ = "participant_visibility"

    exposed_by_participant_id: int = Field(
        sa_column=Column(ForeignKey("participant.participant_id"), primary_key=True)
    )
    exposed_to_participant_id: int = Field(
        sa_column=Column(ForeignKey("participant.participant_id"), primary_key=True)
    )

    # exposed_by_participant: Optional[Participant] = Relationship(


class ParticipantVisibilityCreate(ParticipantVisibilityBase):
    pass


class ParticipantVisibilityDelete(BaseModel):
    exposed_by_participant_id: int
    exposed_to_participant_id: int
