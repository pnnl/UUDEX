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


from flask_restful import abort
#
from flask import g
from sqlalchemy.orm import aliased
#
import common
from api import base
#
from api.permission_api import PermissionAPI
from models import db, SubjectPolicy, SubjectPolicyAclConstraint, SubjectPolicyGrantAllowed, PrivilegeAllowed, \
     GrantScope, Participant, DatasetDefinition
import views
from services import authorization_service
from views.subject_policy_acl_constraint_view import SubjectPolicyAclConstraintView
from views.subject_policy_view import SubjectPolicyView
from views.subject_policy_view_enriched import SubjectPolicyViewEnriched

# -----------------------------------------------------------------------------------------------------

class SubjectPolicyAPI(base.UUDEXResource):

    @staticmethod
    def derive_policy_type(dataset_definition_id, participant_type):

        # first element of 1st tuple is dataset, second is participant
        # second element of 2nd tuple is subject_policy_type_sort
        policy_type = {(True, True): ("GLOBAL_DEFAULT",4), (False, True): ("DATASET", 3),
                       (True, False): ("PARTICIPANT", 2), (False, False): ("PARTICIPANT_AND_DATASET", 1)}

        return policy_type[(dataset_definition_id is None, participant_type is None)]


    # get
    #
    # endpoint: /subject-policies
    # endpoint: /subject-policies/<uuid:subject_policy_uuid>
    #
    # Returns a single Subject Policy the calling Participant is attached to OR
    # Returns a collection of all Subject Policies the calling Participant is attached to
    #
    # get_all_subject_policies
    #
    def get_subject_policy(self, subject_policy_uuid):

        if g.uudex_admin:
            if subject_policy_uuid is None:
                filters = [1 == 1]
            else:
                uuid = str(subject_policy_uuid)
                filters = [SubjectPolicy.subject_policy_uuid == uuid]
        else:
            if subject_policy_uuid is None:
                filters = [SubjectPolicy.target_participant_id == g.participant_id]
            else:
                uuid = str(subject_policy_uuid)
                filters = [SubjectPolicy.target_participant_id == g.participant_id, SubjectPolicy.subject_policy_uuid == uuid]

        participant_a = aliased(Participant)
        sp = db.session.query(SubjectPolicy.subject_policy_uuid, SubjectPolicy.subject_policy_type,
                              SubjectPolicy.action,
                              DatasetDefinition.dataset_definition_uuid, participant_a.participant_uuid.label("target_participant_uuid"),
                              SubjectPolicy.max_queue_size_kb, SubjectPolicy.max_message_count,
                              SubjectPolicy.max_priority, SubjectPolicy.full_queue_behavior,
                              SubjectPolicyAclConstraint.subject_policy_acl_constraint_id,
                              PrivilegeAllowed.privilege_allowed_name, GrantScope.grant_scope_name,
                              SubjectPolicyGrantAllowed.object_uuid,
                              SubjectPolicyGrantAllowed.object_type).\
            select_from(SubjectPolicy). \
            outerjoin(DatasetDefinition). \
            outerjoin(participant_a, SubjectPolicy.target_participant_id == participant_a.participant_id).\
            outerjoin(SubjectPolicyAclConstraint, SubjectPolicy.subject_policy_id ==  SubjectPolicyAclConstraint.subject_policy_id).\
            outerjoin(PrivilegeAllowed, SubjectPolicyAclConstraint.privilege_allowed_id == PrivilegeAllowed.privilege_allowed_id).\
            outerjoin(GrantScope, SubjectPolicyAclConstraint.grant_scope_id == GrantScope.grant_scope_id).\
            outerjoin(SubjectPolicyGrantAllowed, SubjectPolicyAclConstraint.subject_policy_acl_constraint_id == SubjectPolicyGrantAllowed.subject_policy_acl_constraint_id).\
            filter(*filters).\
            order_by(SubjectPolicy.subject_policy_type_sort, SubjectPolicyAclConstraint.subject_policy_acl_constraint_id).all()

        if sp is None or len(sp) == 0:
            abort(404, code=404, message="SubjectPolicy not found")

        nested_sp = common.nest_flat_list(sp, [
                              {"key_name": "",                      "key_idx": 0, "start_idx": 0, "end_idx": 8},
                              {"key_name": "acl_constraints",       "key_idx": 9, "start_idx": 9, "end_idx": 11},
                              {"key_name": "object_list", "key_idx": 9, "start_idx": 12, "end_idx": 13}])

        if subject_policy_uuid is None and type(nested_sp) != list:
            nested_sp = [nested_sp]

        resp = SubjectPolicyViewEnriched.generate_resp(nested_sp)
        return views.generate_resp_envelope(resp), 200

    def get(self, subject_policy_uuid=None):
        return self.get_subject_policy(subject_policy_uuid)


    # post
    #
    # endpoint: /admin/subject-policies
    #
    # Creates a Subject Policy and attaches it to given Participant
    #
    def create_subject_policy(self):
        authorization_service.uudex_admin_or_403()
        args = SubjectPolicyView.parse_post_req()

        if args["target_participant_uuid"] is not None:
            uuid = args["target_participant_uuid"]
            participant = Participant.query.get_uuid_or_404(uuid)
            args['target_participant_id'] = participant.participant_id
        else:
            args['target_participant_id'] = None

        if args["dataset_definition_uuid"] is not None:
            uuid = args["dataset_definition_uuid"]
            dataset = DatasetDefinition.query.get_uuid_or_404(uuid)
            args['dataset_definition_id'] = dataset.dataset_definition_id
        else:
            args['dataset_definition_id'] = None

        policy_type = self.derive_policy_type(args['dataset_definition_id'], args['target_participant_id'])
        args['subject_policy_type'] = policy_type[0]
        args['subject_policy_type_sort'] = policy_type[1]

        sp = SubjectPolicy()
        sp.set_columns(**args)

        db.session.add(sp)
        db.session.commit()

        resp = SubjectPolicyView.generate_resp(sp)
        return views.generate_resp_envelope(resp), 200

    def post(self, ):
        return self.create_subject_policy()


    # patch
    #
    # endpoint: /admin/subject-policies/<uuid:subject_policy_uuid>
    #
    # Update a single Subject Policy
    #
    def update_subject_policy(self, subject_policy_uuid):
        authorization_service.uudex_admin_or_403()

        uuid = str(subject_policy_uuid)
        sp = SubjectPolicy.query.get_uuid_or_404(uuid)
        args = SubjectPolicyView.parse_patch_req()

        changes = sp.set_columns(**args)
        if len(changes):
            db.session.commit()

        resp = SubjectPolicyView.generate_resp(sp)
        return views.generate_put_resp_envelope(resp, changes), 200

    def patch(self, subject_policy_uuid):
        return self.update_subject_policy(subject_policy_uuid)


    # delete
    #
    # endpoint: /admin/subject-policies/<uuid:subject_policy_uuid>
    #
    # Delete a single Subject Policy
    #
    def delete_subject_policy(self, subject_policy_uuid):
        authorization_service.uudex_admin_or_403()

        uuid = str(subject_policy_uuid)
        sp = SubjectPolicy.query.get_uuid_or_404(uuid)
        db.session.delete(sp)
        db.session.commit()

    def delete(self, subject_policy_uuid):
        self.delete_subject_policy(subject_policy_uuid)
        return '', 204

# -----------------------------------------------------------------------------------------------------


class SubjectPolicyAclConstraintAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /subject-policies/<uuid:subject_policy_uuid>/acl-constraints/<int:acl_constraint_id>
    # endpoint: /subject-policies/<uuid:subject_policy_uuid>/acl-constraints
    #
    # Returns a collection of ACL Constraints for the given Subject Policy the calling Participant is attached to
    # Returns a single ACL Constraint for the given Subject Policy the calling Participant is attached to
    #
    # get_acl_constraint
    #
    def get_acl_constraints(self, subject_policy_uuid, acl_constraint_id, uudex_admin):
        uuid = str(subject_policy_uuid)
        if uudex_admin:
            if acl_constraint_id is None:
                filters = [SubjectPolicy.subject_policy_uuid == uuid]
            else:
                filters = [SubjectPolicy.subject_policy_uuid == uuid,
                           SubjectPolicyAclConstraint.subject_policy_acl_constraint_id == acl_constraint_id]
        else:
            if acl_constraint_id is None:
                filters = [SubjectPolicy.target_participant_id == g.participant_id, SubjectPolicy.subject_policy_uuid == uuid]
            else:
                filters = [SubjectPolicy.target_participant_id == g.participant_id, SubjectPolicy.subject_policy_uuid == uuid,
                           SubjectPolicyAclConstraint.subject_policy_acl_constraint_id == acl_constraint_id]

        sp = SubjectPolicyAclConstraint.query.get_uuid_or_404(uuid)

        spa = db.session.query(SubjectPolicyAclConstraint.subject_policy_acl_constraint_id,
                               PrivilegeAllowed.privilege_allowed_name, GrantScope.grant_scope_name,
                               SubjectPolicyGrantAllowed.object_uuid,
                               SubjectPolicyGrantAllowed.object_type). \
            select_from(SubjectPolicyAclConstraint). \
            outerjoin(SubjectPolicy). \
            outerjoin(PrivilegeAllowed, SubjectPolicyAclConstraint.privilege_allowed_id == PrivilegeAllowed.privilege_allowed_id). \
            outerjoin(GrantScope, SubjectPolicyAclConstraint.grant_scope_id == GrantScope.grant_scope_id). \
            outerjoin(SubjectPolicyGrantAllowed, SubjectPolicyAclConstraint.subject_policy_acl_constraint_id == SubjectPolicyGrantAllowed.subject_policy_acl_constraint_id). \
            filter(*filters).all()

        if spa is None or len(spa) == 0:
            abort(404, code=404, message="SubjectPolicyAclConstraint not found")

        nested_sp = common.nest_flat_list(spa, [
                                         {"key_name": "",                      "key_idx": 0, "start_idx": 0, "end_idx": 2},
                                         {"key_name": "object_list", "key_idx": 0, "start_idx": 3, "end_idx": 4}])

        if acl_constraint_id is None and type(nested_sp) != list:
            nested_sp = [nested_sp]

        resp = SubjectPolicyAclConstraintView.generate_resp(nested_sp)
        return views.generate_resp_envelope(resp), 200

    def get(self, subject_policy_uuid, acl_constraint_id=None):
        return self.get_acl_constraints(subject_policy_uuid, acl_constraint_id, g.uudex_admin)


    # delete
    #
    # endpoint: /admin/subject-policies/<uuid:subject_policy_uuid>/acl-constraints/<int:acl_constraint_id>
    #
    # Delete a single ACL Constraint for a given Subject Policy
    #
    def delete_acl_constraint(self, subject_policy_uuid, acl_constraint_id):
        authorization_service.uudex_admin_or_403()

        uuid = str(subject_policy_uuid)
        spa = db.session.query(SubjectPolicyAclConstraint).\
            join(SubjectPolicy).\
            filter(SubjectPolicy.subject_policy_uuid == uuid, SubjectPolicyAclConstraint.subject_policy_acl_constraint_id == acl_constraint_id).\
            one_or_none()

        if spa is None:
            abort(404, code=404, message="SubjectPolicyAclConstraint not found")

        spga = db.session.query(PrivilegeAllowed.privilege_allowed_name, SubjectPolicyGrantAllowed.object_uuid,
                                SubjectPolicyGrantAllowed.object_type). \
               select_from(SubjectPolicyGrantAllowed). \
               join(SubjectPolicyAclConstraint). \
               join(PrivilegeAllowed). \
               filter(SubjectPolicyGrantAllowed.subject_policy_acl_constraint_id == acl_constraint_id).\
               all()

        db.session.delete(spa)
        db.session.flush()

        for item in spga:
            authorization_service.remove_subject_policy(item.privilege_allowed_name, acl_constraint_id, item.object_uuid, item.object_type )

        db.session.commit()

    def delete(self, acl_constraint_id, subject_policy_uuid):
        self.delete_acl_constraint(subject_policy_uuid, acl_constraint_id)
        return '', 204


    # post
    #
    # endpoint: /admin/subject-policies/<uuid:subject_policy_uuid>/acl-constraints
    #
    # Create a ACL Constraint for a given Subject Policy
    #
    def create_acl_constraint(self, subject_policy_uuid):
        authorization_service.uudex_admin_or_403()

        args = SubjectPolicyAclConstraintView.parse_post_req()

        uuid = str(subject_policy_uuid)
        sp = SubjectPolicy.query.get_uuid_or_404(uuid)
        args['subject_policy_id'] = sp.subject_policy_id

        code_id = common.get_code_id_from_value(PrivilegeAllowed, "privilege_allowed_name",  args['privilege_allowed_name'])
        args[code_id[0]] = code_id[1]
        code_id = common.get_code_id_from_value(GrantScope, "grant_scope_name",  args['grant_scope_name'])
        args[code_id[0]] = code_id[1]

        spa = SubjectPolicyAclConstraint()
        spa.set_columns(**args)
        db.session.add(spa)
        db.session.flush()

        if args['grant_scope_name'] in ['ALLOW_ONLY', 'ALLOW_EXCEPT']:
            for auth_object in args['object_list']:
                PermissionAPI.validate_auth_object(auth_object['object_uuid'], auth_object['object_type'])
                spga = SubjectPolicyGrantAllowed(subject_policy_acl_constraint_id=spa.subject_policy_acl_constraint_id,
                                                 object_uuid=auth_object['object_uuid'], object_type=auth_object['object_type'])

                authorization_service.add_subject_policy(args['privilege_allowed_name'], spa.subject_policy_acl_constraint_id,
                                                         auth_object['object_uuid'], auth_object['object_type'])
                db.session.add(spga)

        db.session.commit()

        spa_api = SubjectPolicyAclConstraintAPI()
        return spa_api.get_acl_constraints(subject_policy_uuid=subject_policy_uuid, acl_constraint_id=spa.subject_policy_acl_constraint_id,
                                           uudex_admin=True)

    def post(self, subject_policy_uuid):
        return self.create_acl_constraint(subject_policy_uuid)
