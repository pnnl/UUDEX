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

from api import subject_policy_api, subject_api, subscription_api, uudex_api, dataset_definition_api, \
     dataset_api
from api.endpoint_api import EndpointAPI, EndpointPeerAPI, EndpointGroupAPI, EndpointRoleAPI
from api.group_api import GroupAPI, GroupMemberAPI, GroupManagerAPI
from api.object_type_api import ObjectTypeAPI
from api.participant_api import ParticipantParentAPI, ParticipantAPI, ParticipantContactAPI, ParticipantGroupAPI
from api.permission_api import PermissionAPI
from api.role_api import RoleAPI, RoleEndpointAPI


def add_routes():

    # Dataset
    uudex_api.add_resource(dataset_api.DatasetAPI, "/datasets", endpoint="datasets")
    uudex_api.add_resource(dataset_api.DatasetAPI, "/datasets/<uuid:dataset_uuid>", endpoint="dataset")

    # Dataset Definition
    uudex_api.add_resource(dataset_definition_api.DatasetDefinitionAPI, "/dataset-definitions",
                           endpoint="dataset-definitions")
    uudex_api.add_resource(dataset_definition_api.DatasetDefinitionAPI, "/dataset-definitions/<uuid:dataset_definition_uuid>",
                           endpoint="dataset-definition")

    # Endpoint
    uudex_api.add_resource(EndpointPeerAPI, "/auth/endpoints/peers", endpoint='endpoints-peers')
    uudex_api.add_resource(EndpointAPI, "/auth/endpoints/<uuid:endpoint_uuid>", endpoint='endpoint')
    uudex_api.add_resource(EndpointAPI, "/auth/endpoints", endpoint='endpoints')
    uudex_api.add_resource(EndpointGroupAPI, "/auth/endpoints/<uuid:endpoint_uuid>/groups", endpoint='endpoint-groups')
    uudex_api.add_resource(EndpointRoleAPI, "/auth/endpoints/<uuid:endpoint_uuid>/roles", endpoint='endpoint-roles')

    # Participant
    uudex_api.add_resource(ParticipantParentAPI, "/auth/participants/parent", endpoint="parent-participant")
    uudex_api.add_resource(ParticipantAPI, "/auth/participants/<uuid:participant_uuid>", endpoint="participant")
    uudex_api.add_resource(ParticipantAPI, "/auth/participants", endpoint="auth-participants")
    uudex_api.add_resource(ParticipantContactAPI, "/auth/participants/<uuid:participant_uuid>/contacts",
                           endpoint="participants-contacts")
    uudex_api.add_resource(ParticipantContactAPI,
                     "/auth/participants/<uuid:participant_uuid>/contacts/<int:contact_id>", endpoint="participants-contact")
    uudex_api.add_resource(ParticipantGroupAPI, "/auth/participants/<uuid:participant_uuid>/groups",
                           endpoint="participants-groups")

    # Role
    uudex_api.add_resource(RoleAPI, "/auth/roles", endpoint="roles")
    uudex_api.add_resource(RoleAPI, "/auth/roles/<uuid:role_uuid>", endpoint="role")
    uudex_api.add_resource(RoleEndpointAPI, "/auth/roles/<uuid:role_uuid>/endpoints", endpoint="role-endpoint")

    # Group
    uudex_api.add_resource(GroupAPI, "/auth/groups", endpoint="groups")
    uudex_api.add_resource(GroupAPI, "/auth/groups/<uuid:group_uuid>", endpoint="group")
    uudex_api.add_resource(GroupMemberAPI, "/auth/groups/<uuid:group_uuid>/members", endpoint="group-members")
    uudex_api.add_resource(GroupMemberAPI, "/auth/groups/<uuid:group_uuid>/members/<uuid:object_uuid>", endpoint="group-member")
    uudex_api.add_resource(GroupManagerAPI, "/auth/groups/<uuid:group_uuid>/managers", endpoint="group-managers")
    uudex_api.add_resource(GroupManagerAPI, "/auth/groups/<uuid:group_uuid>/managers/<uuid:object_uuid>", endpoint="group-manager")

    # Permission
    uudex_api.add_resource(PermissionAPI, "/auth/permissions", endpoint="permissions")
    uudex_api.add_resource(PermissionAPI, "/auth/permissions/<uuid:object_uuid>", endpoint="permission")
    uudex_api.add_resource(PermissionAPI, "/auth/permissions/<privilege>/<uuid:subject_uuid>/target/<uuid:object_uuid>",
                           endpoint="remove-permission")

    # Object Type
    uudex_api.add_resource(ObjectTypeAPI, "/auth/object_type/<uuid:object_uuid>", endpoint="object-type")

    # Subject ACL Policy
    uudex_api.add_resource(subject_policy_api.SubjectPolicyAPI, "/subject-policies/<uuid:subject_policy_uuid>", endpoint="subject-policy")
    uudex_api.add_resource(subject_policy_api.SubjectPolicyAPI, "/subject-policies", endpoint="subject-policies")
    #
    uudex_api.add_resource(subject_policy_api.SubjectPolicyAclConstraintAPI, "/subject-policies/<uuid:subject_policy_uuid>/acl-constraints",
                           endpoint="subject-policies-acl-constraints")
    uudex_api.add_resource(subject_policy_api.SubjectPolicyAclConstraintAPI, "/subject-policies/<uuid:subject_policy_uuid>/acl-constraints/<int:acl_constraint_id>",
                           endpoint="subject-policies-acl-constraint")

    # Subject
    uudex_api.add_resource(subject_api.SubjectDiscoveryAPI, "/subjects/discover", endpoint="subjects-discover")
    uudex_api.add_resource(subject_api.SubjectAPI, "/subjects", endpoint="subjects")
    uudex_api.add_resource(subject_api.SubjectAPI, "/subjects/<uuid:subject_uuid>", endpoint="subject")
    uudex_api.add_resource(subject_api.SubjectPublishAPI, "/subjects/<uuid:subject_uuid>/publish", endpoint="subjects-publish")

    # Subscription
    uudex_api.add_resource(subscription_api.SubscriptionAPI, "/subscriptions", endpoint="subscriptions")
    uudex_api.add_resource(subscription_api.SubscriptionAPI, "/subscriptions/<uuid:subscription_uuid>", endpoint="subscription")
    uudex_api.add_resource(subscription_api.SubscriptionConsumeAPI, "/subscriptions/<uuid:subscription_uuid>/consume",
                           endpoint="subscriptions-consume")
    uudex_api.add_resource(subscription_api.SubscriptionSubjectAPI, "/subscriptions/<uuid:subscription_uuid>/subjects",
                           endpoint="subscriptions-subjects")
    uudex_api.add_resource(subscription_api.SubscriptionSubjectAPI, "/subscriptions/<uuid:subscription_uuid>/subjects/<int:subscription_subject_id>",
                           endpoint="subscriptions-subject")
