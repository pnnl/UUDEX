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
from .participant_routes import participant_router, participants_router
from .subject_routes import subject_router, subjects_router
from .subscription_routes import subscription_router, subscriptions_router
from .uudex_routes import endpoint_router

tags_metadata = [
    {"name": "participants", "description": "Participants API"},
    {"name": "endpoints", "description": "Endpoints API"},
    {"name": "certificates", "description": "Certificates/Admin API"},
    {"name": "subjects", "description": "Subjects API"},
    {"name": "datasets", "description": "Datasets API"},
    {"name": "subscriptions", "description": "Subscriptions API"},
]


def route_name_as_operation_id(route: APIRoute) -> str:
    """Use the endpoint name as the operation ID so generated clients get short method names."""
    return route.name


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

    routers = [
        (participant_router, "participants"),
        (participants_router, "participants"),
        (endpoint_router, "endpoints"),
        (subject_router, "subjects"),
        (subjects_router, "subjects"),
        (dataset_router, "datasets"),
        (datasets_router, "datasets"),
        (subscription_router, "subscriptions"),
        (subscriptions_router, "subscriptions"),
    ]
    for router, tag in routers:
        app.include_router(
            router, tags=[tag], generate_unique_id_function=route_name_as_operation_id
        )
