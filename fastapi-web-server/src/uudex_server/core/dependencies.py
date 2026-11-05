"""
FastAPI Dependencies for authentication and authorization
"""
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.services.authentication_service import AuthenticationService, get_request_user
from uudex_server.services.database_service import get_db

_log = logging.getLogger(__name__)


async def get_current_user(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> AuthenticatedUser:
    """
    Get the currently authenticated user from the certificate CN stored in request.state.
    Uses the authentication service cache for performance.
    """
    cert_cn = getattr(request.state, "cert_cn", None)

    if not cert_cn:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, detail="Unauthorized: No certificate found"
        )

    # Use the authentication service to get the endpoint (with caching)
    from uudex_server.core.settings import get_settings

    settings = get_settings()
    auth_service = AuthenticationService.create(settings)
    endpoint = await auth_service.get_endpoint_by_certificate_dn(cert_cn, db)

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


# Type aliases for cleaner endpoint signatures - these are annotated dependencies
SessionDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[AuthenticatedUser, Depends(get_request_user)]
CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]
AdminUserDep = Annotated[AuthenticatedUser, Depends(get_admin_user)]
ParticipantAdminUserDep = Annotated[AuthenticatedUser, Depends(get_participant_admin_user)]
