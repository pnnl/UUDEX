from fastapi import APIRouter

from uudex_server.core.dependencies import SessionDep
from uudex_server.models.participant_models import Participant, ParticipantCreate
from uudex_server.repos import participant_repositories as pr

participants_router = APIRouter(prefix="/participants")
participant_router = APIRouter(prefix="/participant")

# Create v1 parent router
v1_router = APIRouter(prefix="/v1", tags=["v1"])
v1_router.include_router(participants_router, tags=["v1", "participants"])
v1_router.include_router(participant_router, tags=["v1", "participants"])


@participants_router.get("/")
async def get_all_participants(session: SessionDep) -> list[Participant]:
    # Use the standalone function for async operations
    participants = await pr.select_all_participants(session=session)
    return list(participants)


@participants_router.post("/", operation_id="create_participant")
async def create_participant(
    participant_create: ParticipantCreate, session: SessionDep
) -> Participant:
    # Use the standalone function for async operations
    created_participant = await pr.create_participant(
        session=session, participant=participant_create
    )
    return created_participant
