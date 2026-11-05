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

from flask_restful import fields
#
import views.base
from views.generic_auth_obj_view import GenericAuthObjView

def object_list(value):
    object_uuid = value['object_uuid']
    if not object_uuid:
        raise ValueError("The object_uuid parameter is required")
    object_type  = value['object_type']
    if object_type not in ['s', 'e', 'p', 'g', 'r']:
        raise ValueError("The object_type parameter must be one of: 's', 'e', 'p', 'g', 'r'")
    return value

class SubjectPolicyAclConstraintView(views.base.ModelViewBase):
    @classmethod
    def _build_resp_fields(cls):
        cls._resp_fields = {
            "subject_policy_acl_constraint_id": fields.Integer(None),
            "privilege_allowed_name": fields.String,
            "grant_scope_name": fields.String,
            "object_list": fields.List(fields.Nested(GenericAuthObjView.get_resp_fields()))
        }

    @classmethod
    def _build_post_parser(cls):
        cls._post_parser.add_argument("subject_policy_acl_constraint_id", type=int)
        cls._post_parser.add_argument("privilege_allowed_name", type=str, choices=(
            "BROADEST_ALLOWED_PUBLISHER_ACCESS", "BROADEST_ALLOWED_SUBSCRIBER_ACCESS",
            "BROADEST_ALLOWED_MANAGER_ACCESS"), required=True)
        cls._post_parser.add_argument("grant_scope_name", type=str, choices=(
            "ALLOW_ONLY", "ALLOW_EXCEPT", "ALLOW_ALL", "ALLOW_NONE"), required=True)
        cls._post_parser.add_argument("object_list", action='append', type=object_list, required=True)
