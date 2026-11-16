from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps

from uudex_server.core.settings import Settings
from uudex_server.models.endpoint_models import EndPoint

_log = logging.getLogger(__name__)


def authenticate(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


class AuthenticationService:
    @staticmethod
    def create(settings: Settings) -> AuthenticationService:
        return AuthenticationService()

    async def get_endpoint_by_certificate_dn(
        self, certificate_dn: str, db_session
    ) -> EndPoint | None:
        """
        Get the active endpoint of an active participant for a certificate DN.
        Read on every request so a deactivated caller loses access at once.
        """
        from uudex_server.repos.endpoint_repository import EndpointRepository

        repo = EndpointRepository(db_session)
        endpoint = await repo.select_endpoint_by_certificate_dn(certificate_dn)

        if not endpoint or endpoint.active_sw.upper() != "Y":
            return None

        # Check if participant is active
        if endpoint.participant.active_sw.upper() != "Y":
            return None

        return endpoint


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


# class EndpointCacheEntry:

#     def __init__(self, endpoint_id, endpoint_uuid, endpoint_user_name, participant_id, participant_uuid,
#                  participant_active_sw):

# def add_endpoint_cache_entry(cert_cn, endpoint):
#     global _endpoint_cache
#     global _thread_sync_event

#     with _thread_sync_event:

# def get_endpoint_cache_entry(cert_cn):
#     global _endpoint_cache
#     global _thread_sync_event

#     with _thread_sync_event:


# def invalidate_endpoint_cache_entry(cert_cn):
#     global _endpoint_cache
#     global _thread_sync_event

#     with _thread_sync_event:

# def get_peer_cert():


#     if not passed_cert_piece:

#     if config.APP_SERVER_HOST == "gunicorn_proxied":
#         if not attributes:
#         for attribute in attributes:
#             if attribute.split('=')[0] == "CN":

# def authenticate_session(func):
#     @wraps(func)
#     def wrapper(*args, **kwargs):

#         if not passed_cert_cn:

#         # check calling user is authorized based on the passed cert's cn
#         if endpoint_cached is None:
#                                      .one_or_none()
#             if db_endpoint:
#                 endpoint_cached = EndpointCacheEntry(db_endpoint.endpoint_id, db_endpoint.endpoint_uuid,
#                                                      db_endpoint.endpoint_user_name,
#                                                      db_endpoint.participant_id,
#                                                      db_endpoint.participant.participant_uuid,
#                                                      db_endpoint.participant.active_sw)


#         if auth:

#             #
#             # Check for built-in roles
#             #
#             # well known UUID for built-in role UUDEXAdmin
#             # well known UUID for built-in role ParticipantAdmin
#             # well known UUID for built-in role RoleAdmin
#             # well known UUID for built-in role SubjectAdmin


# def determine_admin_access(func, *args, **kwargs):

#     # check if calling controller class is prefixed with "Admin".  If so check if caller
#     # is an administrator, return 403 error if not
#     if func.__qualname__[0:5] == "Admin" and not g.uudex_admin:
