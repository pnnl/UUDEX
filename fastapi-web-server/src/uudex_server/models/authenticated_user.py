from pydantic import BaseModel

from uudex_server.models.endpoint_models import EndPoint


class AuthenticatedUser(BaseModel):
    endpoint: EndPoint

    # TODO use SubjectAcl service to determine these
    def is_admin(self) -> bool:
        return self.endpoint.uudex_administrator_sw.upper() == "Y"

    def is_participant_admin(self) -> bool:
        return self.endpoint.participant_administrator_sw.upper() == "Y"

    def is_active(self) -> bool:
        return self.endpoint.active_sw.upper() == "Y"
