"""

UUDEX

Copyright © 2021, Battelle Memorial Institute

1. Battelle Memorial Institute (hereinafter Battelle) hereby grants
permission to any person or entity lawfully obtaining a copy of this
software and associated documentation files (hereinafter “the Software”)
to redistribute and use the Software in source and binary forms, with or
without modification.  Such person or entity may use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software, and
may permit others to do so, subject to the following conditions:

   - Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimers.
   - Redistributions in binary form must reproduce the above copyright notice,
     this list of conditions and the following disclaimer in the documentation
     and/or other materials provided with the distribution.
   - Other than as used herein, neither the name Battelle Memorial Institute
     or Battelle may be used in any form whatsoever without the express
     written consent of Battelle.

2. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

from uuid import uuid4

from flask_restful import abort
from flask import g
#
from api import base
#
from models import db, Endpoint, Participant
import views
from services import authentication_service, authorization_service
from views.endpoint_view import EndpointView

# -----------------------------------------------------------------------------------------------------
from views.generic_auth_obj_view import GenericAuthObjView


class EndpointPeerAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /endpoints
    #
    # Returns a collection of peer Endpoints in the calling enpoint's organization
    #
    def get_peer_endpoints(self, ):
        endpoints = Endpoint.query.filter(Endpoint.participant_id == g.participant_id).filter(
            Endpoint.endpoint_id != g.endpoint_id).all()
        if endpoints is None or len(endpoints) == 0:
            abort(404, message=f"No peers exist for calling endpoint")

        resp = EndpointView.generate_resp(endpoints)
        return views.generate_resp_envelope(resp), 200

    def get(self, ):
        return self.get_peer_endpoints()

# -----------------------------------------------------------------------------------------------------


class EndpointAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /auth/endpoints
    #
    # Create a single Endpoint
    #
    def create_endpoint(self):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        args = EndpointView.parse_post_req()
        uuid_participant = args["participant_uuid"]
        participant = Participant.query.get_uuid_or_404(uuid_participant)

        authorization_service.endpoint_in_participant_or_403(participant.participant_id)

        args['participant_id'] = participant.participant_id
        del args['participant_uuid']
        endpoint = Endpoint(**args)
        endpoint.endpoint_uuid = str(uuid4())
        db.session.add(endpoint)
        authorization_service.add_user_to_public_group(endpoint.endpoint_uuid) # everyone is in public group
        authorization_service.add_user_to_participant(endpoint.endpoint_uuid, participant.participant_uuid)  # add to the particpant group
        db.session.commit()

        resp = EndpointView.generate_resp(endpoint)
        return views.generate_resp_envelope(resp), 200

    def post(self):
        return self.create_endpoint()

    # get
    #
    # endpoint: /auth/endpoints AND
    # endpoint: /auth/endpoints/<uuid:endpoint_uuid>
    #
    # Get a single Endpoint AND
    # Return a collection of all Endpoints in the system
    #
    # auth_get_all_endpoints
    #
    def get_endpoint(self, endpoint_uuid):

        if endpoint_uuid is None:
            authorization_service.uudex_admin_or_403()
            endpoints = Endpoint.query.all()
        else:
            uuid = str(endpoint_uuid)
            endpoints = Endpoint.query.get_uuid_or_404(uuid)
            authorization_service.endpoint_in_participant_or_403(endpoints.participant_uuid)

        resp = EndpointView.generate_resp(endpoints)
        return views.generate_resp_envelope(resp), 200

    def get(self, endpoint_uuid=None):
        return self.get_endpoint(endpoint_uuid)

    # patch
    #
    # endpoint: /auth/endpoints/<uuid:endpoint_uuid>
    #
    # Update a single Endpoint
    #
    def update_endpoint(self, endpoint_uuid):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        uuid = str(endpoint_uuid)
        endpoint = Endpoint.query.get_uuid_or_404(uuid)

        authorization_service.endpoint_in_participant_or_403(endpoint.participant_id)

        args = EndpointView.parse_patch_req()

        changes = endpoint.set_columns(**args)
        if len(changes):
            authentication_service.invalidate_endpoint_cache_entry(endpoint.certificate_dn)
            db.session.commit()

        resp = EndpointView.generate_resp(endpoint)
        return views.generate_put_resp_envelope(resp, changes), 200


    def patch(self, endpoint_uuid):
        return self.update_endpoint(endpoint_uuid)


    # delete
    #
    # endpoint: /auth/endpoints/<uuid:endpoint_uuid>
    #
    # Delete an Endpoint
    #
    def delete_endpoint(self, endpoint_uuid):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        uuid = str(endpoint_uuid)
        endpoint = Endpoint.query.get_uuid_or_404(uuid)

        authorization_service.endpoint_in_participant_or_403(endpoint.participant_id)

        db.session.delete(endpoint)
        authentication_service.invalidate_endpoint_cache_entry(endpoint.certificate_dn)
        authorization_service.remove_user(endpoint.endpoint_uuid)
        db.session.commit()


    def delete(self, endpoint_uuid):
        self.delete_endpoint(endpoint_uuid)
        return '', 204



class EndpointGroupAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /auth/endpoints/{endpoint_uuid}/groups
    #
    # Returns a collection of groups the Endpoint is a member of
    #
    def get_endpoint_groups(self, endpoint_uuid):
        authorization_service.uudex_admin_or_participant_admin_or_403()

        uuid = str(endpoint_uuid)
        endpoint = Endpoint.query.get_uuid_or_404(uuid)
        authorization_service.endpoint_in_participant_or_403(endpoint.participant_id)

        groups = authorization_service.get_groups_for_user(uuid)

        resp = GenericAuthObjView.generate_resp(groups)
        return views.generate_resp_envelope(resp), 200

    def get(self, endpoint_uuid):
        return self.get_endpoint_groups(endpoint_uuid)


class EndpointRoleAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /auth/endpoints/{endpoint_uuid}/roles
    #
    # Returns a collection of Roles the Endpoint is a member of
    #
    def get_endpoint_groups(self, endpoint_uuid):
        authorization_service.uudex_admin_or_role_admin_or_403()

        uuid = str(endpoint_uuid)
        endpoint = Endpoint.query.get_uuid_or_404(uuid)
        authorization_service.endpoint_in_participant_or_403(endpoint.participant_id)

        roles = authorization_service.get_roles_for_user(uuid)

        resp = GenericAuthObjView.generate_resp(roles)
        return views.generate_resp_envelope(resp), 200

    def get(self, endpoint_uuid):
        return self.get_endpoint_groups(endpoint_uuid)