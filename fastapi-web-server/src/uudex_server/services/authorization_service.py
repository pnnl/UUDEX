from __future__ import annotations

from enum import Enum


##########################################################################################
# Well-known built-in UUIDs for roles and groups.  These are UUIDv5 type identifiers, so they're
# created from a seed UUID and a namespace/domain.
#
# The predefined input UUID for the UUIDv5 algo: 560face6-b1dc-4f41-a039-422779cf2330
#
class PermissionUUIDMap(Enum):
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


class AuthorizationService:
    pass

    @staticmethod
    def create(config: dict) -> AuthorizationService:
        return AuthorizationService()


# """

# UUDEX

# Copyright (c) 2021, Battelle Memorial Institute

# 1. Battelle Memorial Institute (hereinafter Battelle) hereby grants
# permission to any person or entity lawfully obtaining a copy of this
# software and associated documentation files (hereinafter "the Software")
# to redistribute and use the Software in source and binary forms, with or
# without modification.  Such person or entity may use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software, and
# may permit others to do so, subject to the following conditions:

#    - Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimers.
#    - Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    - Other than as used herein, neither the name Battelle Memorial Institute
#      or Battelle may be used in any form whatsoever without the express
#      written consent of Battelle.

# 2. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL BATTELLE OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# """


# #
# #
# from models import (AuthRole, DatasetDefinition, GrantScope, PrivilegeAllowed,
#                     SubjectPolicy, SubjectPolicyAclConstraint)

# ##########################################################################################


# ##########################################################################################
# # Well-known built-in UUIDs for roles and groups.  These are UUIDv5 type identifiers, so they're
# # created from a seed UUID and a namespace/domain.
# #
# # The predefined input UUID for the UUIDv5 algo: 560face6-b1dc-4f41-a039-422779cf2330
# #
# class BuiltInUUID:
#     # UUIDv5 namespace used -> g:public
#     # UUIDv5 namespace used -> r:uudex_admin
#     # UUIDv5 namespace used -> r:participant_admin
#     # UUIDv5 namespace used -> r:role_admin
#     # UUIDv5 namespace used -> r:subject_admin
# ##########################################################################################

# def has_role_by_name(endpoint_uuid, role_name) -> bool:
#     if role_uuid is None:

# def has_role(endpoint_uuid, role_uuid) -> bool:

# def is_group_manager(endpoint_uuid, group_uuid) -> bool:

# def uudex_admin_or_403():
#     if not g.uudex_admin:

# def uudex_admin_or_participant_admin_or_403():
#     if not g.uudex_admin and not g.participant_admin:

# def uudex_admin_or_role_admin_or_403():
#     if not g.uudex_admin and not g.role_admin and not g.participant_admin:  # ParticipantAdmin roles subsumes the RoleAdmin role

# def uudex_admin_or_part_admin_or_subj_admin_or_403():
#     if not g.uudex_admin and not g.subject_admin and not g.participant_admin:  # ParticipantAdmin roles subsumes the SubjectAdmin role

# def endpoint_in_participant_or_403(participant_id):
#     if participant_id != g.participant_id and not g.uudex_admin:

# def group_manager_or_403(endpoint_uuid, group_uuid):
#     if not g.uudex_admin and not is_group_manager(endpoint_uuid, group_uuid):

# def add_user_to_role(endpoint_uuid, role_uuid):

# def add_user_to_group(endpoint_uuid, group_uuid):

# def add_participant_to_group(participant_uuid, group_uuid):

# def add_user_to_public_group(endpoint_uuid):

# def add_user_to_participant(endpoint_uuid, participant_uuid):

# def add_group_manager(object_uuid, object_type, group_uuid):
#     if object_type not in ('e', 'p', 'g'):

# # conceptual syntax:  grant <privilege> on <subject> to <object> [with allow_except]
# def add_subject_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override: bool):

#     if except_modifier_override:   # also grant to public if allow_except is specified

# def add_subject_policy(privilege_allowed_name: str, subject_policy_acl_constraint_id: int, object_uuid: str, object_type: str):

#     e.add_policy(full_object_uuid, "y:" + str(subject_policy_acl_constraint_id), privilege_allowed_name,
#                  scope, action)

# # conceptual syntax:  revoke <privilege> on <subject> from <object> [with allow_except]
# def remove_subject_permission(privilege, subject_uuid, object_uuid, object_type, except_modifier_override: bool):

#     if except_modifier_override:   # also revoke from to public if allow_except is specified

# def remove_subject_policy(privilege_allowed_name: str, subject_policy_acl_constraint_id: int, object_uuid: str, object_type: str):


# def remove_group_manager(object_uuid, object_type, group_uuid):
#     if object_type not in ('e', 'p', 'g'):

# def remove_user_from_role(endpoint_uuid, role_uuid):

# def remove_user_from_group(endpoint_uuid, group_uuid):

# def remove_participant_from_group(participant_uuid, group_uuid):

# def remove_user_from_participant(endpoint_uuid, participant_uuid):

# def remove_user(endpoint_uuid):

# def remove_role(role_uuid):

# def remove_group(group_uuid):

# def remove_group_object(object_uuid):

# def get_roles_for_user(endpoint_uuid) -> list:

# def get_groups_for_participant(participant_uuid) -> list:

# def get_groups_for_user(endpoint_uuid) -> list:

# def get_users_for_role(role_uuid) -> list:
#     # roles can only be assigned to users (ie, endpoints)

# def get_users_for_group(group_uuid) -> list:

# def get_group_managers(group_uuid) -> list:

# def get_permissions(object_uuid, object_type) -> list:

#     if object_type != 's':

#     curated_permissions = [{"subject_uuid": x[1][2:],
#                             "except_modifier_override": "Y" if x[3] == "allow_except" else "N"
#                            for x in raw_permissions if x[3] != 'policy'] # filter out subject policy rules

# def get_discoverable_subjects(endpoint_uuid) -> set:

#     # First, get list of all the subjects the endpoint is allowed to access

#     # Then, run the list of subjects from above through the enforcer to determine final access.  This 2nd step is needed due
#     # to the "allow_except" modifier. ie, find if subject is truly allowed by fully evaluating against rules

# def get_subject_policy_attributes(participant_id, dataset_definition_id):


#     for policy in policies:
#         for attribute in available_attributes:
#             if attribute not in policy_attributes:
#                 if getattr(policy, attribute) is not None:


# def __curate_raw_objects_to_groups(raw_objects : list):
#     return [{"object_uuid": x[2:], "object_type": 'g'} for x in raw_objects
#             if x[0:2] == "g:" and x != "g:" + BuiltInUUID.WN_PUBLIC_GROUP_UUID]  # remove the internal public group

# #
# # Return decision:  True  = Allow access
# #                   False = Deny access
# #
# # True if:
# #   Privilege has been granted (explicitly or implicitly through a group/role or to invoker's participant)
# #   Invoker's Participant owns the Subject
# #   Invoker has the UUDEX admin role
# #
# def has_subject_access(requested_privilege, requested_subject_uuid, owner_participant_id) -> bool:

# #
# #            decision: True  - Allow ACL grant
# #                      False - Prevent ACL grant
# #            subject_policy_acl_constraint_id: The policy that prevented the ACL from being created.
# #                                              Only populated if decision is False.
# #            If no Subject Policies are found then returns True and 0 for subject_policy_acl_constraint_id
# #
# def apply_requested_acl_to_policies(participant_id, dataset_definition_id, requested_object_uuid, requested_object_type,
#                                     requested_privilege_name):

#     if requested_privilege_name == "PUBLISH":
#         if requested_privilege_name == "SUBSCRIBE":
#             if requested_privilege_name == "MANAGE":

#     if not policies:

#     acl_constraints = db.session.query(SubjectPolicy.subject_policy_type.label("subject_policy_type"), SubjectPolicy.action.label("action"),
#                               PrivilegeAllowed.privilege_allowed_name, GrantScope.grant_scope_name,
#                               SubjectPolicyAclConstraint.subject_policy_acl_constraint_id,

#     if not acl_constraints:


#     if grant_scope_name == "ALLOW_ALL":

#     if grant_scope_name == "ALLOW_NONE":

#     decision = e.enforce(f"{requested_object_type}:{requested_object_uuid}", f"y:{subject_policy_acl_constraint_id}",
#                          privilege_allowed_name)


# def get_subject_policies(participant_id, dataset_definition_id):

#     policy1 = db.session.query(policy_a.subject_policy_id.label("subject_policy_id"), policy_a.subject_policy_type.label("subject_policy_type"),
#         filter(policy_a.subject_policy_type == "PARTICIPANT_AND_DATASET", policy_a.target_participant_id == participant_id,
#                DatasetDefinition.dataset_definition_id == dataset_definition_id)

#     policy2 = db.session.query(policy_b.subject_policy_id.label("subject_policy_id"), policy_b.subject_policy_type.label("subject_policy_type"), policy_b.action.label("action"),

#     policy3 = db.session.query(policy_c.subject_policy_id.label("subject_policy_id"),policy_c.subject_policy_type.label("subject_policy_type"), policy_c.action.label("action"),

#     policy4 = db.session.query(policy_d.subject_policy_id.label("subject_policy_id"),policy_d.subject_policy_type.label("subject_policy_type"), policy_d.action.label("action"),

#     # union together
