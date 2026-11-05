from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

import uudex_server.models as m
from uudex_server.models import Participant, ParticipantCreate
from uudex_server.repos import Repository


class ParticipantRepository(Repository[m.Participant]):
    def __init__(self, session: Session):
        super().__init__(m.Participant, session=session, id_field="participant_id")


class ParticipantVisibilityRepository(Repository[m.ParticipantVisibility]):
    def __init__(self, session: Session):
        super().__init__(m.Participant, session=session, id_field="exposed_by_id")


async def select_all_participants(session: AsyncSession) -> list[Participant]:
    stmt = select(Participant)
    result = await session.execute(stmt)
    return result.scalars().all()


async def select_participant_by_id(
    session: AsyncSession, participant_id: int
) -> Participant | None:
    stmt = select(Participant).where(Participant.participant_id == participant_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_participant(session: AsyncSession, participant: ParticipantCreate) -> Participant:
    db_participant = Participant(**participant.model_dump())
    session.add(db_participant)
    await session.commit()
    await session.refresh(db_participant)
    return db_participant
