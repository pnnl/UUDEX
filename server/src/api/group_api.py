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
from models import db, AuthGroup, Endpoint, Participant
import views
from services import authorization_service


# -----------------------------------------------------------------------------------------------------
from views.generic_auth_obj_view import GenericAuthObjView
from views.group_view import GroupView


class GroupAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /auth/groups
    #
    # Create a single Group
    #
    def create_group(self):
        authorization_service.uudex_admin_or_403()

        args = GroupView.parse_post_req()

        group = AuthGroup(**args)
        db.session.add(group)
        db.session.commit()

        resp = GroupView.generate_resp(group)
        return views.generate_resp_envelope(resp), 200

    def post(self):
        return self.create_group()

    # get
    #
    # endpoint: /auth/groups AND
    # endpoint: /auth/groups/<uuid:group_uuid>
    #
    # Get a single Group AND
    # Return a collection of all Groups in the system
    #
    # auth_get_all_groups
    #
    def get_group(self, group_uuid):

        if group_uuid is None:
            # raw_groups = AuthGroup.query.filter(AuthGroup.group_name != 'public').all() # public is internal and so hidden from end-user
            raw_groups = AuthGroup.query.all() # public is internal and so hidden from end-user
        else:
            uuid = str(group_uuid)
            raw_groups = AuthGroup.query.get_uuid_or_404(uuid)

        if g.uudex_admin:
            curated_groups = raw_groups
        else:
            # check if user has permission to manage the group
            curated_groups = [x for x in raw_groups if authorization_service.is_group_manager(g.endpoint_uuid, x.group_uuid)]

        resp = GroupView.generate_resp(curated_groups)
        return views.generate_resp_envelope(resp), 200

    def get(self, group_uuid=None):
        return self.get_group(group_uuid)

    # patch
    #
    # endpoint: /auth/groups/<uuid:group_uuid>
    #
    # Update a single Group
    #
    def update_group(self, group_uuid):
        authorization_service.uudex_admin_or_403()

        uuid = str(group_uuid)
        group = AuthGroup.query.get_uuid_or_404(uuid)

        args = GroupView.parse_patch_req()

        changes = group.set_columns(**args)
        if len(changes):
            db.session.commit()

        resp = GroupView.generate_resp(group)
        return views.generate_put_resp_envelope(resp, changes), 200


    def patch(self, group_uuid):
        return self.update_group(group_uuid)


    # delete
    #
    # endpoint: /auth/groups/<uuid:group_uuid>
    #
    # Delete an Group
    #
    def delete_group(self, group_uuid):
        authorization_service.uudex_admin_or_403()

        uuid = str(group_uuid)
        group = AuthGroup.query.get_uuid_or_404(uuid)

        db.session.delete(group)
        authorization_service.remove_group(uuid)
        authorization_service.remove_group_object(uuid)
        db.session.commit()


    def delete(self, group_uuid):
        self.delete_group(group_uuid)
        return '', 204


#########################################################################################


class GroupMemberAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /auth/groups/{group_uuid}/members
    #
    # Add a member to a group
    #
    def create_group_member(self, group_uuid):
        uuid = str(group_uuid)
        authorization_service.group_manager_or_403(g.endpoint_uuid, uuid)
        group  = AuthGroup.query.get_uuid_or_404(uuid)

        args = GenericAuthObjView.parse_post_req()
        object_uuid = args['object_uuid']
        object_type = args['object_type']

        if object_type == 'e':
            Endpoint.query.get_uuid_or_404(object_uuid)
        elif object_type == 'p':
            Participant.query.get_uuid_or_404(object_uuid)
        else:
            abort(HTTPStatus.BAD_REQUEST, message="Invalid object_type for group membership.  Must be 'e' or 'p'")

        authorization_service.add_user_to_group(object_uuid, group.group_uuid)

        resp = GenericAuthObjView.generate_resp(args)
        return views.generate_resp_envelope(resp), 200

    def post(self, group_uuid):
        return self.create_group_member(group_uuid)

    # get
    #
    # endpoint: /auth/groups/{group_uuid}/members
    #
    # Return a collection of Group Members for the given Group
    #
    # auth_get_all_group_members
    #
    def get_group_member(self, group_uuid):
        uuid = str(group_uuid)
        authorization_service.group_manager_or_403(g.endpoint_uuid, uuid)
        AuthGroup.query.get_uuid_or_404(uuid)

        group_members = authorization_service.get_users_for_group(uuid)

        resp = GenericAuthObjView.generate_resp(group_members)
        return views.generate_resp_envelope(resp), 200

    def get(self, group_uuid):
        return self.get_group_member(group_uuid)

    # delete
    #
    # endpoint: /auth/groups/{group_uuid}/members/{object_uuid}
    #
    # Remove a Group Member from a Group
    #
    # auth_remove_group_member
    #
    def delete_group_member(self, group_uuid, object_uuid):
        group_uuid = str(group_uuid)
        authorization_service.group_manager_or_403(g.endpoint_uuid, group_uuid)
        AuthGroup.query.get_uuid_or_404(group_uuid)

        object_uuid = str(object_uuid)
        object_type = request.args.get('object_type')

        if object_type == 'e':
            Endpoint.query.get_uuid_or_404(object_uuid)
        elif object_type == 'p':
            Participant.query.get_uuid_or_404(object_uuid)
        else:
            abort(HTTPStatus.BAD_REQUEST, message="Invalid object_type for group membership.  Must be 'e' or 'p'")

        authorization_service.remove_user_from_group(object_uuid, group_uuid)

    def delete(self, group_uuid, object_uuid):
         self.delete_group_member(group_uuid, object_uuid)
         return '', 204


#########################################################################################


class GroupManagerAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /auth/groups/{group_uuid}/managers
    #
    # Add a manager to a group
    #
    def create_group_manager(self, group_uuid):
        uuid = str(group_uuid)
        authorization_service.group_manager_or_403(g.endpoint_uuid, uuid)
        group  = AuthGroup.query.get_uuid_or_404(uuid)

        args = GenericAuthObjView.parse_post_req()
        object_uuid = args['object_uuid']
        object_type = args['object_type']

        if object_type == 'e':
            Endpoint.query.get_uuid_or_404(object_uuid)
        elif object_type == 'p':
            Participant.query.get_uuid_or_404(object_uuid)
        elif object_type == 'g':
            Participant.query.get_uuid_or_404(object_uuid)
        else:
            abort(HTTPStatus.BAD_REQUEST, message="Invalid object_type for group manager.  Must be 'e', 'p' or 'g'")

        authorization_service.add_group_manager(object_uuid, object_type, group.group_uuid)

        resp = GenericAuthObjView.generate_resp(args)
        return views.generate_resp_envelope(resp), 200

    def post(self, group_uuid):
        return self.create_group_manager(group_uuid)

    # get
    #
    # endpoint: /auth/groups/{group_uuid}/managers
    #
    # Return a collection of Group Managers for the given Group
    #
    # auth_get_all_group_managers
    #
    def get_group_manager(self, group_uuid):
        uuid = str(group_uuid)
        authorization_service.group_manager_or_403(g.endpoint_uuid, uuid)
        AuthGroup.query.get_uuid_or_404(uuid)

        group_managers = authorization_service.get_group_managers(uuid)

        resp = GenericAuthObjView.generate_resp(group_managers)
        return views.generate_resp_envelope(resp), 200

    def get(self, group_uuid):
        return self.get_group_manager(group_uuid)

    # delete
    #
    # endpoint: /auth/groups/{group_uuid}/managers/{object_uuid}
    #
    # Remove a Group Manager from a Group
    #
    # auth_remove_group_manager
    #
    def delete_group_manager(self, group_uuid, object_uuid):
        group_uuid = str(group_uuid)
        authorization_service.group_manager_or_403(g.endpoint_uuid, group_uuid)
        group = AuthGroup.query.get_uuid_or_404(group_uuid)

        object_uuid = str(object_uuid)
        object_type = request.args.get('object_type')

        if object_type == 'e':
            Endpoint.query.get_uuid_or_404(object_uuid)
        elif object_type == 'p':
            Participant.query.get_uuid_or_404(object_uuid)
        elif object_type == 'g':
            Participant.query.get_uuid_or_404(object_uuid)
        else:
            abort(HTTPStatus.BAD_REQUEST, message="Invalid object_type for group managership.  Must be 'e' or 'p'")

        authorization_service.remove_group_manager(object_uuid, object_type, group.group_uuid)

    def delete(self, group_uuid, object_uuid):
         self.delete_group_manager(group_uuid, object_uuid)
         return '', 204
