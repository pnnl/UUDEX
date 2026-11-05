from pydantic import BaseModel

from uudex_server.models.endpoint_models import EndPoint


class AuthenticatedUser(BaseModel):
    endpoint: EndPoint

    # TODO use SubjectAcl service to determine these
    def is_admin(self) -> bool:
        return self.endpoint.uudex_administrator_sw.upper() == 'Y'

    def is_participant_admin(self) -> bool:
        return self.endpoint.participant_administrator_sw.upper() == 'Y'

    def is_active(self) -> bool:
        return self.endpoint.active_sw.upper() == 'Y'


#             g.endpoint_id = endpoint_cached.endpoint_id
#             g.endpoint_uuid = endpoint_cached.endpoint_uuid
#             g.endpoint_user_name = endpoint_cached.endpoint_user_name
#             g.participant_id = endpoint_cached.participant_id
#             g.participant_uuid = endpoint_cached.participant_uuid
