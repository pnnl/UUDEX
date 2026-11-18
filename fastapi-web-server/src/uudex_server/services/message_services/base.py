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

import abc
import uuid
from typing import Protocol


class BrokerError(Exception):
    """A message broker call failed. Services raise this instead of the client library's errors.

    status_code is the broker's HTTP status when it answered with one (404 for a missing queue),
    and None when it did not answer, as for a network failure or rejected credentials.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class UntrustedBrokerName(Exception):
    """A stored broker name is not one the server could have minted for its own row."""


class _HasExchange(Protocol):
    subject_uuid: str
    backing_exchange_name: str


# A broker name is minted once, here, from server-made UUIDs only. It is stored on its row and
# read back from there; nothing rebuilds one, so no client string can steer or alias a name.
def exchange_name(subject_uuid: str) -> str:
    return f"e_{subject_uuid}"


def queue_name(subject_uuid: str, subscription_uuid: str) -> str:
    return f"q_uudex_{subject_uuid}_{subscription_uuid}"


def trusted_exchange_name(subject: _HasExchange) -> str:
    """The stored exchange name, or UntrustedBrokerName when it is not tied to this row alone.

    Rows written before names were server-minted may hold a client-chosen uuid or a name copied
    from another subject. A canonical uuid is fixed-length and unique, so a name that ends in it
    cannot be another row's name.
    """
    subject_uuid, name = subject.subject_uuid, subject.backing_exchange_name
    try:
        canonical = str(uuid.UUID(subject_uuid)) == subject_uuid
    except (ValueError, TypeError, AttributeError):
        canonical = False
    if not canonical:
        raise UntrustedBrokerName(f"subject_uuid {subject_uuid!r} is not a canonical uuid")
    if not (isinstance(name, str) and name.startswith("e_") and name.endswith(f"_{subject_uuid}")):
        raise UntrustedBrokerName(f"exchange {name!r} is not tied to subject {subject_uuid}")
    return name


#
# note: this interface is in-flux as use cases mature
#
# todo: interface needs to accommodate kafka better
#


class UUDEXBrokerService(abc.ABC):
    # Legacy builder, still read by purge and consume until they read the stored name.
    @staticmethod
    def build_queue_name(tag, subject_name, subscription_uuid) -> str:
        return f"q_{tag}_{subject_name}_{subscription_uuid}"

    # return newly created "queue"
    @abc.abstractmethod
    def create_subscription_subject(self, queue_name, exchange_name) -> str:
        # pure virtual
        pass

    # return an rc that signifies success or failure
    @abc.abstractmethod
    def delete_subscription_subject(self, queue_name) -> int:
        # pure virtual
        pass

    # return an rc that signifies success or failure
    @abc.abstractmethod
    def create_exchange(self, exchange_name) -> int:
        # pure virtual
        pass

    # return an rc that signifies success or failure
    @abc.abstractmethod
    def delete_exchange(self, exchange_name):
        # pure virtual
        pass

    # return an rc that signifies success or failure
    @abc.abstractmethod
    def delete_queue(self, queue_name) -> int:
        pass

    # return an rc that signifies success or failure
    @abc.abstractmethod
    def publish_message(self, subject_exchange, routing_key, payload, payload_enc="string") -> int:
        pass

    # count: how many messages to fetch from message broker
    # returns: list of dicts. messages[msg-index]['payload'] will contain the message body
    @abc.abstractmethod
    def get_messages(self, queue, count=1) -> str:
        pass

    @abc.abstractmethod
    def create_subscription_subject_with_performance_constraints(
        self,
        queue_name,
        exchange_name,
        max_queue_size_kb=None,
        max_message_count=None,
        full_queue_behavior="NO_CONSTRAINT",
    ):
        pass
