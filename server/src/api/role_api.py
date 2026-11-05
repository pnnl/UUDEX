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

from api import base
#
from models import db, Endpoint, AuthRole
import views
from services import authorization_service
from views.endpoint_view import EndpointView
#
from views.role_endpoint_view import RoleEndpointView
from views.role_view import RoleView


class RoleAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /auth/roles
    #
    # Create a single Role
    #
    def create_role(self):
        authorization_service.uudex_admin_or_403()

        args = RoleView.parse_post_req()

        role = AuthRole(**args)
        db.session.add(role)
        db.session.commit()

        resp = RoleView.generate_resp(role)
        return views.generate_resp_envelope(resp), 200

    def post(self):
        return self.create_role()

    # get
    #
    # endpoint: /auth/roles AND
    # endpoint: /auth/roles/<uuid:role_uuid>
    #
    # Get a single Role AND
    # Return a collection of all Roles in the system
    #
    # auth_get_all_roles
    #
    def get_role(self, role_uuid):

        if role_uuid is None:
            roles = AuthRole.query.all()
        else:
            uuid = str(role_uuid)
            roles = AuthRole.query.get_uuid_or_404(uuid)

        resp = RoleView.generate_resp(roles)
        return views.generate_resp_envelope(resp), 200

    def get(self, role_uuid=None):
        return self.get_role(role_uuid)

    # patch
    #
    # endpoint: /auth/roles/<uuid:role_uuid>
    #
    # Update a single Role
    #
    def update_role(self, role_uuid):
        authorization_service.uudex_admin_or_403()

        uuid = str(role_uuid)
        role = AuthRole.query.get_uuid_or_404(uuid)

        args = RoleView.parse_patch_req()

        changes = role.set_columns(**args)
        if len(changes):
            db.session.commit()

        resp = RoleView.generate_resp(role)
        return views.generate_put_resp_envelope(resp, changes), 200


    def patch(self, role_uuid):
        return self.update_role(role_uuid)


    # delete
    #
    # endpoint: /auth/roles/<uuid:role_uuid>
    #
    # Delete an Role
    #
    def delete_role(self, role_uuid):
        authorization_service.uudex_admin_or_403()

        uuid = str(role_uuid)
        role = AuthRole.query.get_uuid_or_404(uuid)

        db.session.delete(role)
        authorization_service.remove_role(role_uuid)
        db.session.commit()


    def delete(self, role_uuid):
        self.delete_role(role_uuid)
        return '', 204


#########################################################################################


class RoleEndpointAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /auth/roles/{role_uuid}/endpoints
    #
    # Grant role to the given Endpoint
    #
    def create_role_endpoint(self, role_uuid):
        authorization_service.uudex_admin_or_role_admin_or_403()

        uuid = str(role_uuid)
        role = AuthRole.query.get_uuid_or_404(uuid)

        args = RoleEndpointView.parse_post_req()
        endpoint = Endpoint.query.get_uuid_or_404(args['endpoint_uuid'])

        authorization_service.add_user_to_role(endpoint.endpoint_uuid, uuid)

        resp = RoleEndpointView.generate_resp(args)
        return views.generate_resp_envelope(resp), 200

    def post(self, role_uuid):
        return self.create_role_endpoint(role_uuid)

    # get
    #
    # endpoint: /auth/roles/{role_uuid}/endpoints
    #
    # Returns all Endpoints that have been granted the given Role
    #
    # auth_get_role_endpoints
    #
    def get_role_endpoint(self, role_uuid):
        authorization_service.uudex_admin_or_role_admin_or_403()

        uuid = str(role_uuid)
        role = AuthRole.query.get_uuid_or_404(uuid)

        ep_list = [x[2:] for x in authorization_service.get_users_for_role(uuid)]
        endpoints = Endpoint.query.filter(Endpoint.endpoint_uuid.in_(ep_list)).all()

        resp = EndpointView.generate_resp(endpoints)
        return views.generate_resp_envelope(resp), 200

    def get(self, role_uuid):
        return self.get_role_endpoint(role_uuid)

