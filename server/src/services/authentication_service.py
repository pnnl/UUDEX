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

import threading
from functools import wraps
#
from http import HTTPStatus

from flask import g, request
import flask_restful
#
import config
from models import Endpoint
from services import authorization_service
from services.authorization_service import BuiltInUUID

_endpoint_cache = dict()
_thread_sync_event = threading.Lock()


class EndpointCacheEntry:

    def __init__(self, endpoint_id, endpoint_uuid, endpoint_user_name, participant_id, participant_uuid,
                 participant_active_sw):
        self.endpoint_id = endpoint_id
        self.endpoint_uuid = endpoint_uuid
        self.endpoint_user_name = endpoint_user_name
        self.participant_id = participant_id
        self.participant_uuid = participant_uuid
        self.participant_active_sw = participant_active_sw


def add_endpoint_cache_entry(cert_cn, endpoint):
    global _endpoint_cache
    global _thread_sync_event

    with _thread_sync_event:
        _endpoint_cache[cert_cn] = endpoint


def get_endpoint_cache_entry(cert_cn):
    global _endpoint_cache
    global _thread_sync_event

    endpoint = None
    with _thread_sync_event:
        endpoint = _endpoint_cache.get(cert_cn)

    return endpoint


def invalidate_endpoint_cache_entry(cert_cn):
    global _endpoint_cache
    global _thread_sync_event

    with _thread_sync_event:
        _endpoint_cache.pop(cert_cn, None)

def get_peer_cert():

    peer_cert_key_name = config.PEER_CERT_KEY_NAME if config.APP_SERVER_HOST == "weurkzieg" else f"HTTP_{config.PEER_CERT_KEY_NAME}"
    passed_cert_piece = request.headers.environ.get(peer_cert_key_name)

    if not passed_cert_piece:
        return None

    if config.APP_SERVER_HOST == "gunicorn_proxied":
        attributes = passed_cert_piece.split(',')
        if not attributes:
            return None
        for attribute in attributes:
            if attribute.split('=')[0] == "CN":
                return attribute.split('=')[1]
        return None
    else:
        return passed_cert_piece


def authenticate_session(func):
    @wraps(func)
    def wrapper(*args, **kwargs):

        passed_cert_cn = get_peer_cert()
        if not passed_cert_cn:
            flask_restful.abort(HTTPStatus.UNAUTHORIZED, message="Unauthorized: Peer certificate required")

        # check calling user is authorized based on the passed cert's cn
        endpoint_cached = get_endpoint_cache_entry(passed_cert_cn)
        if endpoint_cached is None:
            db_endpoint = Endpoint.query.filter(Endpoint.certificate_dn == passed_cert_cn)\
                                     .filter(Endpoint.active_sw == "Y") \
                                     .one_or_none()
            if db_endpoint:
                endpoint_cached = EndpointCacheEntry(db_endpoint.endpoint_id, db_endpoint.endpoint_uuid,
                                                     db_endpoint.endpoint_user_name,
                                                     db_endpoint.participant_id,
                                                     db_endpoint.participant.participant_uuid,
                                                     db_endpoint.participant.active_sw)
                add_endpoint_cache_entry(passed_cert_cn, endpoint_cached)

        auth = endpoint_cached is not None and endpoint_cached.participant_active_sw == "Y"

        if auth:
            g.authenticated = True
            g.endpoint_id = endpoint_cached.endpoint_id
            g.endpoint_uuid = endpoint_cached.endpoint_uuid
            g.endpoint_user_name = endpoint_cached.endpoint_user_name
            g.participant_id = endpoint_cached.participant_id
            g.participant_uuid = endpoint_cached.participant_uuid

            #
            # Check for built-in roles
            #
            # well known UUID for built-in role UUDEXAdmin
            g.uudex_admin = authorization_service.has_role(endpoint_cached.endpoint_uuid, BuiltInUUID.WN_UUDEX_ADMIN_ROLE_UUID)
            # well known UUID for built-in role ParticipantAdmin
            g.participant_admin = authorization_service.has_role(endpoint_cached.endpoint_uuid, BuiltInUUID.WN_PARTICIPANT_ADMIN_ROLE_UUID)
            # well known UUID for built-in role RoleAdmin
            g.role_admin = authorization_service.has_role(endpoint_cached.endpoint_uuid, BuiltInUUID.WN_ROLE_ADMIN_UUID)
            # well known UUID for built-in role SubjectAdmin
            g.subject_admin = authorization_service.has_role(endpoint_cached.endpoint_uuid, BuiltInUUID.WN_SUBJECT_ADMIN_UUID)

            return func(*args, **kwargs)
            # return determine_admin_access(func, *args, **kwargs)
        else:
            g.authenticated = False

        flask_restful.abort(HTTPStatus.UNAUTHORIZED, message="Unauthorized: Invalid peer certificate")

    return wrapper


def determine_admin_access(func, *args, **kwargs):

    # check if calling controller class is prefixed with "Admin".  If so check if caller
    # is an administrator, return 403 error if not
    if func.__qualname__[0:5] == "Admin" and not g.uudex_admin:
        flask_restful.abort(HTTPStatus.FORBIDDEN, message="Administrator access required")

    return func(*args, **kwargs)
