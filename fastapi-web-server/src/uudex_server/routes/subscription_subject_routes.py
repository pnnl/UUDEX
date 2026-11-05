from fastapi import APIRouter

from uudex_server.core.dependencies import SessionDep, UserDep
from uudex_server.models.subscription_subject_models import SubscriptionSubject
from uudex_server.repos import subscription_and_subject_repositories as pr

# Create router for subscription subjects
subscription_subject_router = APIRouter(prefix="/subscription-subjects")

# Create v1 parent router
v1_router = APIRouter(prefix="/v1", tags=["v1"])
v1_router.include_router(subscription_subject_router, tags=["v1", "subscription-subjects"])


@subscription_subject_router.get("/{subscription_uuid}/subjects")
async def get_subscription_subjects(
    subscription_uuid: str, session: SessionDep, user: UserDep
) -> list[SubscriptionSubject]:
    subscription_subjects: list[
        SubscriptionSubject
    ] = await pr.select_subscription_subjects_by_uuid(
        session=session, subscription_uuid=subscription_uuid
    )
    return subscription_subjects
