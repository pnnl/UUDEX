"""

UUDEX

Copyright (c) 2021, Battelle Memorial Institute

1. Battelle Memorial Institute (hereinafter Battelle) hereby grants
permission to any person or entity lawfully obtaining a copy of this
software and associated documentation files (hereinafter "the Software")
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

import functools
from urllib import parse

from pyrabbit2 import http as pyrabbit_http
from pyrabbit2.api import APIError, Client

#
from uudex_server.services.message_services.base import BrokerError, UUDEXBrokerService

# PermissionError is what pyrabbit2 raises for an HTTP 401.
_LIBRARY_ERRORS = (
    pyrabbit_http.HTTPError,
    pyrabbit_http.NetworkError,
    APIError,
    PermissionError,
)


def _raises_broker_error(method):
    """Re-raise pyrabbit2 failures as BrokerError so callers need not import the library."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except _LIBRARY_ERRORS as e:
            raise BrokerError(f"RabbitMQ {method.__name__} failed: {e}") from e

    return wrapper

#
# note: this interface  is in-flux as use cases mature
#
# todo: handle vhost with these calls - this assumes "/" for vhost


class RabbitMqService(UUDEXBrokerService):
    def __init__(self, url, **kwargs):
        hostname, username, password = self._parse_url(url)
        self._client = Client(hostname, username, password)
        super().__init__(**kwargs)

    @staticmethod
    def _parse_url(url):
        res = parse.urlparse(url, allow_fragments=False)
        hostname = res.hostname + ":" + str(res.port)
        parms = parse.parse_qs(res.query)

        if "username" not in parms or "password" not in parms:
            raise ValueError("Malformed MESSAGE_BROKER_URL setting")

        return hostname, parms.get("username")[0], parms.get("password")[0]

    @_raises_broker_error
    def create_subscription_subject(self, subscription_uuid, subject_uuid, subject_name, tag):
        queue_name = self.build_queue_name(tag, subject_name, subscription_uuid)
        self._client.create_queue("/", queue_name, auto_delete=False, durable=True, exclusive=False)

        exchange_name = self.build_exchange_name(subject_name, subject_uuid)
        self._client.create_binding("/", exchange_name, queue_name, "")

        return queue_name

    @_raises_broker_error
    def create_subscription_subject_with_performance_constraints(
        self,
        subscription_uuid,
        subject_uuid,
        subject_name,
        tag,
        max_queue_size_kb=None,
        max_message_count=None,
        full_queue_behavior="NO_CONSTRAINT",
    ):
        queue_name = self.build_queue_name(tag, subject_name, subscription_uuid)
        kwargs = {}
        kwargs["arguments"] = {}
        if full_queue_behavior == "PURGE_OLD":
            # Here, if max queue size in bytes and/or max message count is set, then default
            # behavior is oldest messages are delete when queue gets full
            if max_queue_size_kb is not None:
                kwargs["arguments"]["x-max-length-bytes"] = max_queue_size_kb
            if max_message_count is not None:
                kwargs["arguments"]["x-max-length"] = max_message_count
            self._client.create_queue(
                "/", queue_name, auto_delete=False, durable=True, exclusive=False, **kwargs
            )
        elif full_queue_behavior == "BLOCK_NEW":
            # Here, if max queue size in bytes and/or max message count is set, then behavior is
            # rabbitmq doesn't allow more publishes after queue is full
            if max_queue_size_kb is not None:
                kwargs["arguments"]["x-max-length-bytes"] = max_queue_size_kb
            if max_message_count is not None:
                kwargs["arguments"]["x-max-length"] = max_message_count
            kwargs["arguments"]["x-overflow"] = "reject-publish"
            self._client.create_queue(
                "/", queue_name, auto_delete=False, durable=True, exclusive=False, **kwargs
            )
        else:
            # Reverting to default behavior: full_queue_behavior==NO_CONSTRAINT
            self._client.create_queue(
                "/", queue_name, auto_delete=False, durable=True, exclusive=False
            )
        exchange_name = self.build_exchange_name(subject_name, subject_uuid)
        self._client.create_binding("/", exchange_name, queue_name, "")

        return queue_name

    @_raises_broker_error
    def delete_subscription_subject(self, subscription_uuid, subject_name, tag):
        queue_name = self.build_queue_name(tag, subject_name, subscription_uuid)
        self._client.purge_queue("/", queue_name)
        rc = self._client.delete_queue("/", queue_name)
        return rc

    @_raises_broker_error
    def create_subject(self, subject_name, subject_uuid):
        exchange_name = self.build_exchange_name(subject_name, subject_uuid)
        rc = self._client.create_exchange("/", exchange_name, "fanout", False, True, False)
        return rc

    @_raises_broker_error
    def delete_subject(self, subject_name, subject_uuid):
        exchange_name = self.build_exchange_name(subject_name, subject_uuid)
        print(f"exchange name: {exchange_name}")
        rc = self._client.delete_exchange("/", exchange_name)
        return rc

    @_raises_broker_error
    def delete_queue(self, queue_name):
        return self._client.delete_queue("/", queue_name)

    @_raises_broker_error
    def publish_message(self, subject_exchange, routing_key, payload, payload_enc="string"):
        # payload_enc: string or base64  # noqa: ERA001
        return self._client.publish(
            "/",
            subject_exchange,
            routing_key,
            payload,
            payload_enc,
            properties={"delivery_mode": 2},
        )  # 2 = persistent

    @_raises_broker_error
    def get_messages(self, queue, count=1):
        return self._client.get_messages("/", queue, count)
