from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from functools import wraps
from typing import Annotated

from fastapi import Request

from uudex_server.core.settings import Settings
from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.models.endpoint_models import EndPoint

_log = logging.getLogger(__name__)


class EndpointCache:
    """
    A simple cache to store endpoint information based on the certificate common name (CN).
    This is used to avoid repeated database lookups for the same endpoint.
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        """
        Initialize the cache with a maximum size and time-to-live (TTL) for cached items.
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.timestamps: dict[str, float] = {}
        self._cache: dict[str, EndPoint] = {}
        self._lock = threading.RLock()

    def _is_expired(self, key: str) -> bool:
        if key not in self.timestamps:
            return True
        return time.time() - self.timestamps[key] > self.ttl_seconds

    def _cleanup_expired(self):
        """Remove expired entries"""
        current_time = time.time()
        expired_keys = [
            key
            for key, timestamp in self.timestamps.items()
            if current_time - timestamp > self.ttl_seconds
        ]
        for key in expired_keys:
            self._cache.pop(key, None)
            self.timestamps.pop(key, None)

    def _evict_oldest(self):
        """Remove oldest entry if cache is full"""
        if len(self._cache) >= self.max_size:
            oldest_key = min(self.timestamps.keys(), key=self.timestamps.get)
            self._cache.pop(oldest_key, None)
            self.timestamps.pop(oldest_key, None)

    def get(self, key: str) -> EndPoint | None:
        with self._lock:
            if key in self._cache and not self._is_expired(key):
                return self._cache[key]
            return None

    def set(self, key: str, value: EndPoint):
        with self._lock:
            self._cleanup_expired()
            self._evict_oldest()
            self._cache[key] = value
            self.timestamps[key] = time.time()

    def invalidate(self, key: str):
        with self._lock:
            self._cache.pop(key, None)
            self.timestamps.pop(key, None)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self.timestamps.clear()


authentication_cache = EndpointCache(max_size=100, ttl_seconds=3600)


async def get_request_user(request: Annotated[Request, Request]) -> AuthenticatedUser | None:
    """
    Get authenticated user from request state, using the certificate CN stored by middleware.
    """
    cert_cn = getattr(request.state, "cert_cn", None)

    if not cert_cn:
        return None

    # This would need a database session - better to use the dependency instead
    # For now, return None to indicate we need to use the proper dependency
    return None


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
        Get endpoint by certificate DN, using cache first, then database lookup.
        """
        # Check cache first
        cached_endpoint = authentication_cache.get(certificate_dn)
        if cached_endpoint:
            return cached_endpoint

        # Query database using the endpoint repository pattern
        from uudex_server.repos.endpoint_repository import EndpointRepository

        repo = EndpointRepository(db_session)
        endpoint = await repo.select_endpoint_by_certificate_dn(certificate_dn)

        if not endpoint or endpoint.active_sw.upper() != "Y":
            return None

        # Check if participant is active
        if endpoint.participant.active_sw.upper() != "Y":
            return None

        # Cache the endpoint
        authentication_cache.set(certificate_dn, endpoint)
        return endpoint


# """

# UUDEX

# Copyright © 2021, Battelle Memorial Institute

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

# import threading
# from functools import wraps
# #
# from http import HTTPStatus

# from flask import g, request
# import flask_restful
# #
# import config
# from models import Endpoint
# from services import authorization_service
# from services.authorization_service import BuiltInUUID

# _endpoint_cache = dict()
# _thread_sync_event = threading.Lock()

# class EndpointCacheEntry:

#     def __init__(self, endpoint_id, endpoint_uuid, endpoint_user_name, participant_id, participant_uuid,
#                  participant_active_sw):
#         self.endpoint_id = endpoint_id
#         self.endpoint_uuid = endpoint_uuid
#         self.endpoint_user_name = endpoint_user_name
#         self.participant_id = participant_id
#         self.participant_uuid = participant_uuid
#         self.participant_active_sw = participant_active_sw

# def add_endpoint_cache_entry(cert_cn, endpoint):
#     global _endpoint_cache
#     global _thread_sync_event

#     with _thread_sync_event:
#         _endpoint_cache[cert_cn] = endpoint

# def get_endpoint_cache_entry(cert_cn):
#     global _endpoint_cache
#     global _thread_sync_event

#     endpoint = None
#     with _thread_sync_event:
#         endpoint = _endpoint_cache.get(cert_cn)

#     return endpoint

# def invalidate_endpoint_cache_entry(cert_cn):
#     global _endpoint_cache
#     global _thread_sync_event

#     with _thread_sync_event:
#         _endpoint_cache.pop(cert_cn, None)

# def get_peer_cert():

#     peer_cert_key_name = config.PEER_CERT_KEY_NAME if config.APP_SERVER_HOST == "weurkzieg" else f"HTTP_{config.PEER_CERT_KEY_NAME}"
#     passed_cert_piece = request.headers.environ.get(peer_cert_key_name)

#     if not passed_cert_piece:
#         return None

#     if config.APP_SERVER_HOST == "gunicorn_proxied":
#         attributes = passed_cert_piece.split(',')
#         if not attributes:
#             return None
#         for attribute in attributes:
#             if attribute.split('=')[0] == "CN":
#                 return attribute.split('=')[1]
#         return None
#     else:
#         return passed_cert_piece

# def authenticate_session(func):
#     @wraps(func)
#     def wrapper(*args, **kwargs):

#         passed_cert_cn = get_peer_cert()
#         if not passed_cert_cn:
#             flask_restful.abort(HTTPStatus.UNAUTHORIZED, message="Unauthorized: Peer certificate required")

#         # check calling user is authorized based on the passed cert's cn
#         endpoint_cached = get_endpoint_cache_entry(passed_cert_cn)
#         if endpoint_cached is None:
#             db_endpoint = Endpoint.query.filter(Endpoint.certificate_dn == passed_cert_cn)\
#                                      .filter(Endpoint.active_sw == "Y") \
#                                      .one_or_none()
#             if db_endpoint:
#                 endpoint_cached = EndpointCacheEntry(db_endpoint.endpoint_id, db_endpoint.endpoint_uuid,
#                                                      db_endpoint.endpoint_user_name,
#                                                      db_endpoint.participant_id,
#                                                      db_endpoint.participant.participant_uuid,
#                                                      db_endpoint.participant.active_sw)
#                 add_endpoint_cache_entry(passed_cert_cn, endpoint_cached)

#         auth = endpoint_cached is not None and endpoint_cached.participant_active_sw == "Y"

#         if auth:
#             g.authenticated = True
#             g.endpoint_id = endpoint_cached.endpoint_id
#             g.endpoint_uuid = endpoint_cached.endpoint_uuid
#             g.endpoint_user_name = endpoint_cached.endpoint_user_name
#             g.participant_id = endpoint_cached.participant_id
#             g.participant_uuid = endpoint_cached.participant_uuid

#             #
#             # Check for built-in roles
#             #
#             # well known UUID for built-in role UUDEXAdmin
#             g.uudex_admin = authorization_service.has_role(endpoint_cached.endpoint_uuid, BuiltInUUID.WN_UUDEX_ADMIN_ROLE_UUID)
#             # well known UUID for built-in role ParticipantAdmin
#             g.participant_admin = authorization_service.has_role(endpoint_cached.endpoint_uuid, BuiltInUUID.WN_PARTICIPANT_ADMIN_ROLE_UUID)
#             # well known UUID for built-in role RoleAdmin
#             g.role_admin = authorization_service.has_role(endpoint_cached.endpoint_uuid, BuiltInUUID.WN_ROLE_ADMIN_UUID)
#             # well known UUID for built-in role SubjectAdmin
#             g.subject_admin = authorization_service.has_role(endpoint_cached.endpoint_uuid, BuiltInUUID.WN_SUBJECT_ADMIN_UUID)

#             return func(*args, **kwargs)
#             # return determine_admin_access(func, *args, **kwargs)
#         else:
#             g.authenticated = False

#         flask_restful.abort(HTTPStatus.UNAUTHORIZED, message="Unauthorized: Invalid peer certificate")

#     return wrapper

# def determine_admin_access(func, *args, **kwargs):

#     # check if calling controller class is prefixed with "Admin".  If so check if caller
#     # is an administrator, return 403 error if not
#     if func.__qualname__[0:5] == "Admin" and not g.uudex_admin:
#         flask_restful.abort(HTTPStatus.FORBIDDEN, message="Administrator access required")

#     return func(*args, **kwargs)
