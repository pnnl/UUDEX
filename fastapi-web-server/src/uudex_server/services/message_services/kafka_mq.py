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

from urllib import parse

from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic

#
from services.message_services.base import MessageBrokerServiceBase

#
# note: this interface  is in-flux as use cases mature
#
# todo: handle vhost with these calls - this assumes "/" for vhost


class KafkaService(MessageBrokerServiceBase):
    def __init__(self, url, **kwargs):
        hostname, username, password = self._parse_url(url)
        self._producer = KafkaProducer(bootstrap_servers=hostname)  # Sends Kafka messages
        self._consumer = KafkaConsumer(bootstrap_servers=hostname)  #  Receives Kafka messages
        self._admin = KafkaAdminClient(
            bootstrap_servers=hostname, client_id="uudex"
        )  # Used to create and delete kafka topics
        super().__init__(**kwargs)

    @staticmethod
    def _parse_url(url):
        res = parse.urlparse(url, allow_fragments=False)
        hostname = res.hostname + ":" + str(res.port)
        parms = parse.parse_qs(res.query)

        if "username" not in parms or "password" not in parms:
            raise ValueError("Malformed MESSAGE_BROKER_URL setting")

        return hostname, parms.get("username")[0], parms.get("password")[0]

    def create_subscription_subject(
        self, subscription_uuid, subject_uuid, subject_name, tag
    ):  # Add a topic to the subscription list
        try:
            subscriptions = self._consumer.subscription()
            subscriptions.add(subject_name)
            self._consumer.subscribe(subscriptions)
        except:
            return None
        return tag + subject_name + subject_uuid

    def delete_subscription_subject(
        self, subscription_uuid, subject_name, tag
    ):  # Remove a topic from the subscription list
        try:
            subscriptions = self._consumer.subscription()
            subscriptions.remove(subject_name)
            self._consumer.subscribe(subscriptions)
        except:
            return 0
        return 1

    def create_subject(self, subject_name, subject_uuid):  # Create a Kafka topic
        try:
            topic_list = [NewTopic(name=str(subject_name), num_partitions=1, replication_factor=1)]
            self._admin.create_topics(new_topics=topic_list, validate_only=False)
        except:
            return 0
        return 1

    def delete_queue(self, queue_name):
        return 1  # not implemented for Kafka

    def publish_message(self, subject_exchange, routing_key, payload, payload_enc="string"):
        try:
            self._producer.send(routing_key, payload)
        except:
            return 0
        return 1

    def get_messages(self, queue, count=1):
        try:
            messages = []
            for message in self._consumer:
                messages.append(message)
        except:
            return None
        return messages
