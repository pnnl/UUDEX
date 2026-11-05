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
#
from flask_restful import abort
#
from api import base
from models import Participant, Endpoint, AuthGroup, AuthRole
import views
from views.generic_auth_obj_view import GenericAuthObjView


class ObjectTypeAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /auth/object_type/<uuid:object_uuid>
    #
    # Get object type based on a generic auth object UUID
    #
    def get_object_type(self, object_uuid):

        object_uuid = str(object_uuid)
        object_type_resp = {}
        auth_object = Participant.query.filter(Participant.participant_uuid == object_uuid).one_or_none()
        if auth_object is not None:
            object_type_resp['object_uuid'] = auth_object.participant_uuid
            object_type_resp['object_type'] = 'p'

        if auth_object is None:
            auth_object = Endpoint.query.filter(Endpoint.endpoint_uuid == object_uuid).one_or_none()
            if auth_object is not None:
                object_type_resp['object_uuid'] = auth_object.endpoint_uuid
                object_type_resp['object_type'] = 'e'

        if auth_object is None:
            auth_object = AuthGroup.query.filter(AuthGroup.group_uuid == object_uuid).one_or_none()
            if auth_object is not None:
                object_type_resp['object_uuid'] = auth_object.group_uuid
                object_type_resp['object_type'] = 'g'

        if auth_object is None:
            auth_object = AuthRole.query.filter(AuthRole.role_uuid == object_uuid).one_or_none()
            if auth_object is not None:
                object_type_resp['object_uuid'] = auth_object.role_uuid
                object_type_resp['object_type'] = 'r'

        if auth_object is None:
            abort(HTTPStatus.NOT_FOUND, message="Object not found")

        resp = GenericAuthObjView.generate_resp(object_type_resp)
        return views.generate_resp_envelope(resp), 200

    def get(self, object_uuid):
        return self.get_object_type(object_uuid)
