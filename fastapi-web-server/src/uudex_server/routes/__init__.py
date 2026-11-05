from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from sqlmodel import Session

from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.services.authentication_service import get_request_user
from uudex_server.services.database_service import get_db_session

from ..core import get_settings
from ..services.message_services import UUDEXBrokerService, create_broker_service


class SessionAndUser:
    def __init__(
        self,
        session: Annotated[Session, Depends(get_db_session)],
        user: Annotated[AuthenticatedUser, Depends(get_request_user)],
    ):
        self.session = session
        self.user = user


import uudex_server.repos as r

from .dataset_routes import dataset_router, datasets_router
from .dataset_routes import v1_router as dataset_v1_router
from .participant_routes import participant_router, participants_router
from .participant_routes import v1_router as participant_v1_router
from .subject_routes import subject_router, subjects_router
from .subject_routes import v1_router as subject_v1_router
from .subscription_routes import subscription_router, subscriptions_router
from .subscription_routes import v1_router as subscription_v1_router
from .uudex_routes import endpoint_router
from .uudex_routes import v1_router as endpoint_v1_router

tags_metadata = [
    {"name": "v1", "description": "API Version 1"},
    {"name": "participants", "description": "Participants API"},
    {"name": "endpoints", "description": "Endpoints API"},
    {"name": "certificates", "description": "Certificates/Admin API"},
    {"name": "subjects", "description": "Subjects API"},
    {"name": "datasets", "description": "Datasets API"},
    {"name": "subscriptions", "description": "Subscriptions API"},
]


def use_route_names_as_operation_ids(app: FastAPI) -> None:
    """
    Simplify operation IDs so that generated API clients have simpler function
    names.

    Should be called only after all routes have been added.
    """
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name


class BaseAPI:
    def __init__(self, session: Session = Depends(get_db_session), user=Depends(get_request_user)):
        self.session = session
        self.user = user

    @property
    def subject_repo(self):
        return r.SubjectRepository(self.session)

    @property
    def broker_service(self) -> UUDEXBrokerService:
        return create_broker_service(get_settings().messagebus_connection)


def add_routers(app: FastAPI):
    if app.openapi_tags is None:
        app.openapi_tags = tags_metadata
    else:
        app.openapi_tags.extend(tags_metadata)

    # Add v1 versioned routers
    app.include_router(participant_v1_router)
    app.include_router(subject_v1_router)
    app.include_router(dataset_v1_router)
    app.include_router(endpoint_v1_router)
    app.include_router(subscription_v1_router)

    # Keep original routers for backward compatibility (optional)
    app.include_router(participant_router, tags=["participants"])
    app.include_router(participants_router, tags=["participants"])
    app.include_router(endpoint_router, tags=["endpoints"])
    app.include_router(subject_router, tags=["subjects"])
    app.include_router(subjects_router, tags=["subjects"])
    app.include_router(dataset_router, tags=["datasets"])
    app.include_router(datasets_router, tags=["datasets"])
    app.include_router(subscription_router, tags=["subscriptions"])
    app.include_router(subscriptions_router, tags=["subscriptions"])

    # Simplify to the endpoint name rather than the whole trace of the
    # function using methods etc.
    use_route_names_as_operation_ids(app)
