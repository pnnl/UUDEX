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


class BrokerError(Exception):
    """A message broker call failed. Services raise this instead of the client library's errors."""


# A broker name is minted once, here, from server-made UUIDs only. It is stored on its row and
# read back from there; nothing rebuilds one, so no client string can steer or alias a name.
def exchange_name(subject_uuid: str) -> str:
    return f"e_{subject_uuid}"


def queue_name(subject_uuid: str, subscription_uuid: str) -> str:
    return f"q_uudex_{subject_uuid}_{subscription_uuid}"


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
