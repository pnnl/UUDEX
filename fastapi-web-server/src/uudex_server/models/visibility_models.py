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
    #     back_populates="participant_visibility_exposed_by",
    #     sa_relationship_kwargs={"foreign_keys": "ParticipantVisibility.exposed_by_participant_id"}
    # )


class ParticipantVisibilityCreate(ParticipantVisibilityBase):
    pass


class ParticipantVisibilityDelete(BaseModel):
    exposed_by_participant_id: int
    exposed_to_participant_id: int
