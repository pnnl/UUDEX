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

from http import HTTPStatus

from flask_restful import abort
from flask import g, request
#
from api import base
#
from models import Endpoint, AuthRole, Participant, AuthGroup, Subject
import views
from services import authorization_service

# -----------------------------------------------------------------------------------------------------
from views.permission_view import PermissionView


class PermissionAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /auth/permissions
    #
    # Creates a permission by granting a privilege to a Subject
    #
    # auth_grant_permission
    #
    def create_permission(self):
        authorization_service.uudex_admin_or_part_admin_or_subj_admin_or_403()

        args = PermissionView.parse_post_req()
        subject_uuid = args['subject_uuid']
        object_uuid = args['object_uuid']
        object_type = args['object_type']
        privilege = args['privilege']
        except_modifier_override = args['except_modifier_override']

        subject = self.__validate_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override)

        # skip subject policy evaluation if DISCOVER privilege or an admin
        if privilege != "DISCOVER" and g.uudex_admin != 'Y':
            policy_decision, subject_policy_uuid = authorization_service.apply_requested_acl_to_policies(g.participant_id,
                                                                  subject.dataset_definition_id, object_uuid,
                                                                  object_type, privilege)
            if not policy_decision:
                abort(HTTPStatus.UNAUTHORIZED,
                      message=f"Subject Policy ({subject_policy_uuid}) prevents granting the {privilege} privilege "\
                              f"on subject ({subject_uuid}) to object ({object_type}:{object_uuid})")

        authorization_service.add_subject_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override == "Y")

        resp = PermissionView.generate_resp(args)
        return views.generate_resp_envelope(resp), 200

    def post(self):
        return self.create_permission()

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
    def get_permissions(self, object_uuid):

        object_uuid = str(object_uuid)
        object_type = request.args.get('object_type')

        if object_type == 's':
            authorization_service.uudex_admin_or_part_admin_or_subj_admin_or_403()
            Subject.query.get_uuid_or_404(object_uuid)
        elif object_type == 'g':
            authorization_service.group_manager_or_403(g.endpoint_uuid, object_uuid)
            AuthGroup.query.get_uuid_or_404(object_uuid)
        elif object_type == 'r':
            authorization_service.uudex_admin_or_role_admin_or_403()
            AuthRole.query.get_uuid_or_404(object_uuid)
        elif object_type == 'e':
            authorization_service.uudex_admin_or_participant_admin_or_403()
            Endpoint.query.get_uuid_or_404(object_uuid)
        elif object_type == 'p':
            authorization_service.uudex_admin_or_participant_admin_or_403()
            Participant.query.get_uuid_or_404(object_uuid)
        else:
            abort(HTTPStatus.BAD_REQUEST, message="Invalid object_type.  Must be 's', 'g', r', 'e' or 'p'")

        permissions = authorization_service.get_permissions(object_uuid, object_type)

        resp = PermissionView.generate_resp(permissions)
        return views.generate_resp_envelope(resp), 200

    def get(self, object_uuid):
        return self.get_permissions(object_uuid)


    # delete
    #
    # endpoint: /auth/permissions/{privilege}/subject/{subject_uuid}/target/{object_uuid}
    #
    # Remove a permission by revoking a privilege on a Subject from an object
    #
    # auth_revoke_permission
    #
    def delete_permission(self, privilege, subject_uuid, object_uuid):
        authorization_service.uudex_admin_or_part_admin_or_subj_admin_or_403()

        subject_uuid = str(subject_uuid)
        object_uuid = str(object_uuid)
        object_type = request.args.get('object_type')
        except_modifier_override = request.args.get('except_modifier_override')

        self.__validate_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override)

        authorization_service.remove_subject_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override == "Y")


    def delete(self, privilege, subject_uuid, object_uuid):
        self.delete_permission(privilege, subject_uuid, object_uuid)
        return '', 204


    @staticmethod
    def __validate_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override) -> Subject:
        if privilege not in authorization_service.uudex_privileges:
            abort(HTTPStatus.BAD_REQUEST, message="Invalid privilege:  Must be one of 'SUBSCRIBE', 'PUBLISH', 'MANAGE', 'DISCOVER'")

        if except_modifier_override not in ['Y', 'N']:
            abort(HTTPStatus.BAD_REQUEST, message="Invalid except_modifier_override:  Must be 'Y' or 'N'")

        subject = Subject.query.get_uuid_or_404(subject_uuid)

        PermissionAPI.validate_auth_object(object_uuid, object_type)

        return subject


    @staticmethod
    def validate_auth_object(object_uuid, object_type):
        if object_type == 'e':
            Endpoint.query.get_uuid_or_404(object_uuid)
        elif object_type == 'p':
            Participant.query.get_uuid_or_404(object_uuid)
        elif object_type == 'r':
            AuthRole.query.get_uuid_or_404(object_uuid)
        elif object_type == 'g':
            AuthGroup.query.get_uuid_or_404(object_uuid)
        else:
            abort(HTTPStatus.BAD_REQUEST, message="Invalid object_type, must be 'e', 'p', 'r' or 'g'")
