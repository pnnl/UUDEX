"""
FastAPI Dependencies for authentication and authorization
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from uudex_server.models import Subscription
from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.repos.subscription_and_subject_repositories import SubscriptionRepository
from uudex_server.services.authentication_service import AuthenticationService
from uudex_server.services.database_service import get_db


async def get_current_user(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> AuthenticatedUser:
    """
    Get the currently authenticated user from the certificate CN stored in request.state.
    """
    cert_cn = getattr(request.state, "cert_cn", None)

    if not cert_cn:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Unauthorized: No certificate found"
        )

    endpoint = await AuthenticationService().get_endpoint_by_certificate_dn(cert_cn, db)

    if not endpoint:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Unauthorized: Invalid certificate"
        )

    return AuthenticatedUser(endpoint=endpoint)


async def get_admin_user(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """
    Dependency that ensures the user is a UUDEX administrator.
    """
    if not current_user.is_admin():
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Administrator access required")
    return current_user


async def get_participant_admin_user(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    """
    Dependency that ensures the user is a participant administrator.
    """
    if not current_user.is_participant_admin():
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Participant administrator access required"
        )
    return current_user


async def get_visible_subscription(
    subscription_uuid: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Subscription:
    """
    The subscription if the caller owns it or is an administrator.

    Every other case raises the one 404 a missing uuid gets, so a caller cannot tell a
    subscription they may not see from one that does not exist.
    """
    owner_endpoint_id = None
    if not user.is_admin():
        # Read the id from this session's own copy, so the filter does not depend on which
        # session loaded user.endpoint.
        owner_endpoint_id = (await session.merge(user.endpoint)).endpoint_id
    subscription = await SubscriptionRepository(session).select_visible_by_uuid(
        subscription_uuid, owner_endpoint_id
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return subscription


# Type aliases for cleaner endpoint signatures - these are annotated dependencies
SessionDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
AdminUserDep = Annotated[AuthenticatedUser, Depends(get_admin_user)]
ParticipantAdminUserDep = Annotated[AuthenticatedUser, Depends(get_participant_admin_user)]
VisibleSubscriptionDep = Annotated[Subscription, Depends(get_visible_subscription)]
