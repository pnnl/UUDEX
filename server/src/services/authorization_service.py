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

import os
from http import HTTPStatus
#
import casbin
import casbin_sqlalchemy_adapter
from flask import g
from flask_restful import abort
from sqlalchemy.orm import aliased
#
import config
from models import AuthRole, GrantScope, SubjectPolicy, \
     DatasetDefinition, PrivilegeAllowed, SubjectPolicyAclConstraint
from uudex_model_base import db


##########################################################################################

adapter = casbin_sqlalchemy_adapter.Adapter(config.SQLALCHEMY_DATABASE_URI)
e = casbin.Enforcer(os.path.join("services","auth_model.conf"), adapter)

uudex_privileges = ('PUBLISH', 'SUBSCRIBE', 'MANAGE', 'DISCOVER')

##########################################################################################
# Well-known built-in UUIDs for roles and groups.  These are UUIDv5 type identifiers, so they're
# created from a seed UUID and a namespace/domain.
#
# The predefined input UUID for the UUIDv5 algo: 560face6-b1dc-4f41-a039-422779cf2330
#
class BuiltInUUID:
    # UUIDv5 namespace used -> g:public
    WN_PUBLIC_GROUP_UUID = "61c080e5-c998-5dd9-bcc0-10062607650d"
    # UUIDv5 namespace used -> r:uudex_admin
    WN_UUDEX_ADMIN_ROLE_UUID = "7a0b552e-dd92-5f80-ac60-0d65392ab8d4"
    # UUIDv5 namespace used -> r:participant_admin
    WN_PARTICIPANT_ADMIN_ROLE_UUID = "7ade620d-ab36-549a-8e7d-12ffcfee4900"
    # UUIDv5 namespace used -> r:role_admin
    WN_ROLE_ADMIN_UUID = "cec211fc-6730-55cd-bda8-eb9d97049456"
    # UUIDv5 namespace used -> r:subject_admin
    WN_SUBJECT_ADMIN_UUID = "f0192468-419b-56cf-ae1f-c95a4149a393"
##########################################################################################


def has_role_by_name(endpoint_uuid, role_name) -> bool:
    role_uuid = AuthRole.query.filter(AuthRole.role_name == role_name).one_or_none()
    if role_uuid is None:
        return False
    return e.has_role_for_user("e:" + endpoint_uuid, "r:" + role_uuid)


def has_role(endpoint_uuid, role_uuid) -> bool:
    return e.has_role_for_user("e:" + endpoint_uuid, "r:" + role_uuid)


def is_group_manager(endpoint_uuid, group_uuid) -> bool:
    return e.enforce('e:' + endpoint_uuid, 'g:' + group_uuid, 'MANAGE')


def uudex_admin_or_403():
    if not g.uudex_admin:
        abort(HTTPStatus.FORBIDDEN, message="UUDEXAdmin role required")


def uudex_admin_or_participant_admin_or_403():
    if not g.uudex_admin and not g.participant_admin:
        abort(HTTPStatus.FORBIDDEN, message="Must be have either the UUDEXAdmin role or the ParticipantAdmin role")

def uudex_admin_or_role_admin_or_403():
    if not g.uudex_admin and not g.role_admin and not g.participant_admin:  # ParticipantAdmin roles subsumes the RoleAdmin role
        abort(HTTPStatus.FORBIDDEN, message="Must be have either the UUDEXAdmin role, the ParticipantAdmin role or the RoleAdmin role")


def uudex_admin_or_part_admin_or_subj_admin_or_403():
    if not g.uudex_admin and not g.subject_admin and not g.participant_admin:  # ParticipantAdmin roles subsumes the SubjectAdmin role
        abort(HTTPStatus.FORBIDDEN, message="Must be have either the UUDEXAdmin role, the ParticipantAdmin role or the SubjectAdmin role")


def endpoint_in_participant_or_403(participant_id):
    if participant_id != g.participant_id and not g.uudex_admin:
        abort(HTTPStatus.FORBIDDEN, message="You are not part of the participant")


def group_manager_or_403(endpoint_uuid, group_uuid):
    if not g.uudex_admin and not is_group_manager(endpoint_uuid, group_uuid):
        abort(HTTPStatus.FORBIDDEN, message="Must be a group manager")


def add_user_to_role(endpoint_uuid, role_uuid):
    e.add_role_for_user('e:' + endpoint_uuid, 'r:' + role_uuid)


def add_user_to_group(endpoint_uuid, group_uuid):
    e.add_role_for_user('e:' + endpoint_uuid, 'g:' + group_uuid)


def add_participant_to_group(participant_uuid, group_uuid):
    e.add_role_for_user('p:' + participant_uuid, 'g:' + group_uuid)


def add_user_to_public_group(endpoint_uuid):
    e.add_role_for_user('e:' + endpoint_uuid, 'g:' + BuiltInUUID.WN_PUBLIC_GROUP_UUID)  # add to well-known public group


def add_user_to_participant(endpoint_uuid, participant_uuid):
    e.add_role_for_user('e:' + endpoint_uuid, 'p:' + participant_uuid)


def add_group_manager(object_uuid, object_type, group_uuid):
    if object_type not in ('e', 'p', 'g'):
        raise Exception("invalid object_type for group manager")
    full_object_uuid = object_type + ":" + object_uuid
    e.add_policy(full_object_uuid, "g:" + group_uuid, 'MANAGE', 'std', 'allow')


# conceptual syntax:  grant <privilege> on <subject> to <object> [with allow_except]
def add_subject_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override: bool):
    scope = "std" if not except_modifier_override else "allow_except"
    action = "allow" if not except_modifier_override else "deny"
    full_object_uuid = object_type + ":" + object_uuid

    e.add_policy(full_object_uuid, "s:" + subject_uuid, privilege, scope, action)  # do grant
    if except_modifier_override:   # also grant to public if allow_except is specified
        e.add_policy("g:" + BuiltInUUID.WN_PUBLIC_GROUP_UUID, "s:" + subject_uuid, privilege, "std", "allow")


def add_subject_policy(privilege_allowed_name: str, subject_policy_acl_constraint_id: int, object_uuid: str, object_type: str):
    scope = "policy"
    action = "allow"
    full_object_uuid = object_type + ":" + object_uuid

    e.add_policy(full_object_uuid, "y:" + str(subject_policy_acl_constraint_id), privilege_allowed_name,
                 scope, action)


# conceptual syntax:  revoke <privilege> on <subject> from <object> [with allow_except]
def remove_subject_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override: bool):
    scope = "std" if not except_modifier_override else "allow_except"
    action = "allow" if not except_modifier_override else "deny"
    full_object_uuid = object_type + ":" + object_uuid

    e.remove_policy(full_object_uuid, "s:" + subject_uuid, privilege, scope, action) # do revoke
    if except_modifier_override:   # also revoke from to public if allow_except is specified
        e.remove_policy("g:" + BuiltInUUID.WN_PUBLIC_GROUP_UUID, "s:" + subject_uuid, privilege, "std", "allow")


def remove_subject_policy(privilege_allowed_name: str, subject_policy_acl_constraint_id: int, object_uuid: str, object_type: str):
    scope = "policy"
    action = "allow"
    full_object_uuid = object_type + ":" + object_uuid

    e.remove_policy(full_object_uuid, "y:" + str(subject_policy_acl_constraint_id), privilege_allowed_name, scope, action)


def remove_group_manager(object_uuid, object_type, group_uuid):
    if object_type not in ('e', 'p', 'g'):
        raise Exception("invalid object_type for group manager")
    full_object_uuid = object_type + ":" + object_uuid
    e.remove_policy(full_object_uuid, "g:" + group_uuid, 'MANAGE', 'std', 'allow')


def remove_user_from_role(endpoint_uuid, role_uuid):
    e.delete_role_for_user('e:' + endpoint_uuid, 'r:' + role_uuid)


def remove_user_from_group(endpoint_uuid, group_uuid):
    e.delete_role_for_user('e:' + endpoint_uuid, 'g:' + group_uuid)


def remove_participant_from_group(participant_uuid, group_uuid):
    e.delete_role_for_user('p:' + participant_uuid, 'g:' + group_uuid)


def remove_user_from_participant(endpoint_uuid, participant_uuid):
    e.delete_role_for_user('e:' + endpoint_uuid, 'p:' + participant_uuid)


def remove_user(endpoint_uuid):
    e.delete_user('e:' + endpoint_uuid)


def remove_role(role_uuid):
    e.delete_role('r:' + role_uuid)


def remove_group(group_uuid):
    e.delete_role('g:' + group_uuid)


def remove_group_object(object_uuid):
    return e.delete_permission("g:" + object_uuid)


def get_roles_for_user(endpoint_uuid) -> list:
    raw_objects = e.get_roles_for_user('e:' + endpoint_uuid)
    return [{"object_uuid": x[2:], "object_type": 'r'} for x in raw_objects if x[0:2] == "r:"]


def get_groups_for_participant(participant_uuid) -> list:
    raw_objects = e.get_roles_for_user('p:' + participant_uuid)
    return __curate_raw_objects_to_groups(raw_objects)


def get_groups_for_user(endpoint_uuid) -> list:
    raw_objects = e.get_roles_for_user('e:' + endpoint_uuid)
    return __curate_raw_objects_to_groups(raw_objects)


def get_users_for_role(role_uuid) -> list:
    # roles can only be assigned to users (ie, endpoints)
    return e.get_users_for_role('r:' + role_uuid)


def get_users_for_group(group_uuid) -> list:
    z = e.get_users_for_role('g:' + group_uuid)
    group_members = [{"object_uuid": x[2:], "object_type": x[0:1]} for x in z]
    return group_members


def get_group_managers(group_uuid) -> list:
    z = e.get_filtered_named_policy('p', 1, 'g:' + group_uuid)
    group_managers = [{"object_uuid": x[0][2:], "object_type": x[0][0:1]} for x in z if x[2] == 'MANAGE']
    return group_managers


def get_permissions(object_uuid, object_type) -> list:
    full_object_uuid = object_type + ":" + object_uuid

    if object_type != 's':
      raw_permissions = e.get_implicit_permissions_for_user(full_object_uuid)
    else:
      raw_permissions = []

    curated_permissions = [{"subject_uuid": x[1][2:],
                            "object_uuid": x[0][2:],
                            "object_type": x[0][:1],
                            "privilege": x[2],
                            "except_modifier_override": "Y" if x[3] == "allow_except" else "N"
                           }
                           for x in raw_permissions if x[3] != 'policy'] # filter out subject policy rules
    return curated_permissions


def get_discoverable_subjects(endpoint_uuid) -> set:
    raw_permissions = e.get_implicit_permissions_for_user('e:' + endpoint_uuid)

    # First, get list of all the subjects the endpoint is allowed to access
    subjects = {x[1] for x in raw_permissions if x[1][0:2] == 's:' and x[2] == "DISCOVER" and x[4] == "allow"}

    # Then, run the list of subjects from above through the enforcer to determine final access.  This 2nd step is needed due
    # to the "allow_except" modifier. ie, find if subject is truly allowed by fully evaluating against rules
    final_subjects = {x[2:] for x in subjects if e.enforce('e:' + endpoint_uuid, x, "DISCOVER")}
    return final_subjects


def get_subject_policy_attributes(participant_id, dataset_definition_id):

    policies = get_subject_policies(participant_id, dataset_definition_id)

    policy_attributes = dict()
    available_attributes = ["action", "full_queue_behavior", "max_queue_size_kb", "max_message_count", "max_priority"]

    for policy in policies:
        for attribute in available_attributes:
            if attribute not in policy_attributes:
                if getattr(policy, attribute) is not None:
                    policy_attributes[attribute] = (policy.subject_policy_type, getattr(policy, attribute))

    return policy_attributes


def __curate_raw_objects_to_groups(raw_objects : list):
    return [{"object_uuid": x[2:], "object_type": 'g'} for x in raw_objects
            if x[0:2] == "g:" and x != "g:" + BuiltInUUID.WN_PUBLIC_GROUP_UUID]  # remove the internal public group


#
# Return decision:  True  = Allow access
#                   False = Deny access
#
# True if:
#   Privilege has been granted (explicitly or implicitly through a group/role or to invoker's participant)
#   Invoker's Participant owns the Subject
#   Invoker has the UUDEX admin role
#
def has_subject_access(requested_privilege, requested_subject_uuid, owner_participant_id) -> bool:
    full_subject_uuid = 's:' + requested_subject_uuid
    return g.uudex_admin or \
           owner_participant_id == g.particpnat_id or \
           e.enforce('e:' + g.endpoint_uuid, full_subject_uuid, requested_privilege)


#
# Return:    (decision, subject_policy_acl_constraint_id)
#            decision: True  - Allow ACL grant
#                      False - Prevent ACL grant
#            subject_policy_acl_constraint_id: The policy that prevented the ACL from being created.
#                                              Only populated if decision is False.
#            If no Subject Policies are found then returns True and 0 for subject_policy_acl_constraint_id
#
def apply_requested_acl_to_policies(participant_id, dataset_definition_id, requested_object_uuid, requested_object_type,
                                    requested_privilege_name):

    if requested_privilege_name == "PUBLISH":
        privilege_allowed_name = 'BROADEST_ALLOWED_PUBLISHER_ACCESS'
    else:
        if requested_privilege_name == "SUBSCRIBE":
            privilege_allowed_name = 'BROADEST_ALLOWED_SUBSCRIBER_ACCESS'
        else:
            if requested_privilege_name == "MANAGE":
                privilege_allowed_name = 'BROADEST_ALLOWED_MANAGER_ACCESS'
            else:
                raise AssertionError("Invalid requested_privilege_name")

    policies = get_subject_policies(participant_id, dataset_definition_id)
    if not policies:
        return True, 0

    policy_ids = [x[0] for x in policies]
    acl_constraints = db.session.query(SubjectPolicy.subject_policy_type.label("subject_policy_type"), SubjectPolicy.action.label("action"),
                              PrivilegeAllowed.privilege_allowed_name, GrantScope.grant_scope_name,
                              SubjectPolicyAclConstraint.subject_policy_acl_constraint_id,
                              SubjectPolicy.subject_policy_uuid). \
        select_from(SubjectPolicy). \
        outerjoin(SubjectPolicyAclConstraint). \
        outerjoin(PrivilegeAllowed). \
        outerjoin(GrantScope). \
        filter(SubjectPolicy.subject_policy_id.in_(policy_ids), PrivilegeAllowed.privilege_allowed_name == privilege_allowed_name). \
        order_by(SubjectPolicy.subject_policy_type_sort).all()

    if not acl_constraints:
        return True, 0

    grant_scope_name = acl_constraints[0].grant_scope_name
    subject_policy_acl_constraint_id = acl_constraints[0].subject_policy_acl_constraint_id
    subject_policy_uuid = acl_constraints[0].subject_policy_uuid

    if grant_scope_name == "ALLOW_ALL":
        return True, subject_policy_uuid

    if grant_scope_name == "ALLOW_NONE":
        return False, subject_policy_uuid

    decision = e.enforce(f"{requested_object_type}:{requested_object_uuid}", f"y:{subject_policy_acl_constraint_id}",
                         privilege_allowed_name)

    return (decision, subject_policy_uuid) if grant_scope_name == "ALLOW_ONLY" else (not decision, subject_policy_uuid)


def get_subject_policies(participant_id, dataset_definition_id):

    policy_a = aliased(SubjectPolicy)
    policy1 = db.session.query(policy_a.subject_policy_id.label("subject_policy_id"), policy_a.subject_policy_type.label("subject_policy_type"),
                               policy_a.action.label("action"),
                               policy_a.full_queue_behavior.label("full_queue_behavior"), policy_a.max_queue_size_kb.label("max_queue_size_kb"),
                               policy_a.max_message_count.label("max_message_count"), policy_a.max_priority.label("max_priority"),
                               policy_a.subject_policy_type_sort.label("subject_policy_type_sort")). \
        join(DatasetDefinition).\
        filter(policy_a.subject_policy_type == "PARTICIPANT_AND_DATASET", policy_a.target_participant_id == participant_id,
               DatasetDefinition.dataset_definition_id == dataset_definition_id)

    policy_b = aliased(SubjectPolicy)
    policy2 = db.session.query(policy_b.subject_policy_id.label("subject_policy_id"), policy_b.subject_policy_type.label("subject_policy_type"), policy_b.action.label("action"),
                               policy_b.full_queue_behavior.label("full_queue_behavior"), policy_b.max_queue_size_kb.label("max_queue_size_kb"),
                               policy_b.max_message_count.label("max_message_count"), policy_b.max_priority.label("max_priority"),
                               policy_b.subject_policy_type_sort.label("subject_policy_type_sort")). \
        filter(policy_b.subject_policy_type == "PARTICIPANT", policy_b.target_participant_id == participant_id)

    policy_c = aliased(SubjectPolicy)
    policy3 = db.session.query(policy_c.subject_policy_id.label("subject_policy_id"),policy_c.subject_policy_type.label("subject_policy_type"), policy_c.action.label("action"),
                               policy_c.full_queue_behavior.label("full_queue_behavior"), policy_c.max_queue_size_kb.label("max_queue_size_kb"),
                               policy_c.max_message_count.label("max_message_count"), policy_c.max_priority.label("max_priority"),
                               policy_c.subject_policy_type_sort.label("subject_policy_type_sort")). \
        join(DatasetDefinition). \
        filter(policy_c.subject_policy_type == "DATASET", DatasetDefinition.dataset_definition_id == dataset_definition_id)

    policy_d = aliased(SubjectPolicy)
    policy4 = db.session.query(policy_d.subject_policy_id.label("subject_policy_id"),policy_d.subject_policy_type.label("subject_policy_type"), policy_d.action.label("action"),
                               policy_d.full_queue_behavior.label("full_queue_behavior"), policy_d.max_queue_size_kb.label("max_queue_size_kb"),
                               policy_d.max_message_count.label("max_message_count"), policy_d.max_priority.label("max_priority"),
                               policy_d.subject_policy_type_sort.label("subject_policy_type_sort")). \
        filter(policy_d.subject_policy_type == "GLOBAL_DEFAULT")

    # union together
    policies = policy1.union_all(policy2, policy3, policy4).order_by("subject_policy_type_sort").all()

    return policies
