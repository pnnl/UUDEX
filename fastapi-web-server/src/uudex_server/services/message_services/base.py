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

import abc

#
# note: this interface is in-flux as use cases mature
#
# todo: interface needs to accommodate kafka better
#


class UUDEXBrokerService(abc.ABC):

    @staticmethod
    def build_queue_name(tag, subject_name, subscription_uuid) -> str:
        return f"q_{tag}_{subject_name}_{subscription_uuid}"

    @staticmethod
    def build_exchange_name(subject_name, subject_uuid) -> str:
        return f"e_{subject_name}_{subject_uuid}"

    # return newly created "queue"
    @abc.abstractmethod
    def create_subscription_subject(self, subscription_uuid, subject_uuid, subject_name,
                                    tag) -> str:
        # pure virtual
        pass

    # return an rc that signifies success or failure
    @abc.abstractmethod
    def delete_subscription_subject(self, subscription_uuid, subject_name, tag) -> int:
        # pure virtual
        pass

    # return an rc that signifies success or failure
    @abc.abstractmethod
    def create_subject(self, subject_name, subject_uuid) -> int:
        # pure virtual
        pass

    # return an rc that signifies success or failure
    @abc.abstractmethod
    def delete_subject(self, subject_name, subject_uuid):
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
            subscription_uuid,
            subject_uuid,
            subject_name,
            tag,
            max_queue_size_kb=None,
            max_message_count=None,
            full_queue_behavior="NO_CONSTRAINT"):
        pass
