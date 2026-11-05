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

from flask_restful import abort
#
from flask import g
import common
import config
from api import base
#
from app_container import app
from models import db, Subscription, SubscriptionSubject, Subject, Endpoint
from services import authorization_service
import views
#
from services.message_services.base import MessageBrokerServiceBase
from services.message_services.message_broker_common import message_broker_factory
from views.message_consume_resp_view import MessageConsumeRespView
from views.subscription_subject_view import SubscriptionSubjectView
from views.subscription_view import SubscriptionView
from views.subscription_view_enriched import SubscriptionViewEnriched

# -----------------------------------------------------------------------------------------------------


class SubscriptionAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /subscriptions AND
    # endpoint: /subscriptions/<uuid:subscription_uuid>
    #
    # Returns a collection of the calling endpoint's Subscriptions OR
    # Get a single Subscription that the calling endpoint owns
    #
    def get_subscription(self, subscription_uuid):

        app.logger.debug(f"get_subscription: [{str(subscription_uuid)}]")

        if subscription_uuid is None:
            if not g.uudex_admin:
                filters = [Subscription.owner_endpoint_id == g.endpoint_id]
            else:
                filters = [1 == 1]
        else:
            uuid = str(subscription_uuid)
            if not g.uudex_admin:
                filters = [Subscription.owner_endpoint_id == g.endpoint_id, Subscription.subscription_uuid == uuid]
            else:
                filters = [Subscription.subscription_uuid == uuid]

        subscriptions = db.session.query(Subscription.subscription_uuid, Subscription.subscription_name, Subscription.subscription_state,
                                         Subscription.create_datetime, Endpoint.endpoint_uuid.label("owner_endpoint_uuid"),
                                         SubscriptionSubject.subscription_subject_id,
                                         Subject.subject_uuid, Subject.subject_name, SubscriptionSubject.preferred_fulfillment_type,
                                         SubscriptionSubject.backing_queue_name).\
            select_from(Subscription). \
            outerjoin(Endpoint). \
            outerjoin(SubscriptionSubject). \
            outerjoin(Subject). \
            filter(*filters). \
            all()

        if subscriptions is None or len(subscriptions) == 0:
            abort(404, message=f"No subscriptions found")

        nested_subscription = common.nest_flat_list(subscriptions, [
                              {"key_name": "",          "key_idx": 0, "start_idx": 0, "end_idx": 4},
                              {"key_name": "subjects",  "key_idx": 0, "start_idx": 5, "end_idx": 9}])

        if subscription_uuid is None and type(nested_subscription) != list:
            nested_subscription = [nested_subscription]

        resp = SubscriptionViewEnriched.generate_resp(nested_subscription)
        return views.generate_resp_envelope(resp), 200

    def get(self, subscription_uuid=None):
        return self.get_subscription(subscription_uuid)

    # post
    #
    # endpoint: /subscriptions
    #
    # Create a single Subscription for the endpoint

    #
    def create_subscription(self, ):

        args = SubscriptionView.parse_post_req()

        del args['owner_endpoint_uuid']
        args['owner_endpoint_id'] = g.endpoint_id

        subscription = Subscription()
        subscription.set_columns(**args)

        db.session.add(subscription)
        db.session.commit()

        resp = SubscriptionView.generate_resp(subscription)
        return views.generate_resp_envelope(resp), 200

    def post(self, ):
        return self.create_subscription()

    # patch
    #
    # endpoint: /subscriptions/<uuid:subscription_uuid>
    #
    # Update a single endpoint's Subscription
    #
    def update_subscription(self, subscription_uuid):

        uuid = str(subscription_uuid)
        subscription = Subscription.query.filter(Subscription.owner_endpoint_id == g.endpoint_id, Subscription.subscription_uuid == uuid).first()

        if subscription is None:
            abort(404, message=f"Subscription not found")

        args = SubscriptionView.parse_patch_req()

        changes = subscription.set_columns(**args)
        if len(changes):
            db.session.commit()

        resp = SubscriptionView.generate_resp(subscription)
        return views.generate_put_resp_envelope(resp, changes), 200

    def patch(self, subscription_uuid):
        return self.update_subscription(subscription_uuid)

    # delete
    #
    # endpoint: /subscriptions/<uuid:subscription_uuid>
    #
    # Delelete an endpoint's Subscription
    #
    def delete_subscription(self, subscription_uuid):

        uuid = str(subscription_uuid)
        subscription = Subscription.query.filter(Subscription.owner_endpoint_id == g.endpoint_id, Subscription.subscription_uuid == uuid).first()

        if subscription is None:
            abort(404, message=f"Subscription not found")

        subscription_subjects = db.session.query(Subscription.subscription_uuid, Subject.subject_name).\
            select_from(Subscription).\
            join(SubscriptionSubject).\
            join(Subject).filter(Subscription.owner_endpoint_id == g.endpoint_id,
                                 Subscription.subscription_uuid == uuid).all()

        db.session.delete(subscription)
        db.session.flush()

        # Deletion of a subscription cascade deletes all related subscription_subjects so
        # delete any related queues as well
        try:
            mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)

            for subscription_subject in subscription_subjects:
                mb_client.delete_subscription_subject(subscription_subject.subscription_uuid, subscription_subject.subject_name,
                                                      g.endpoint_user_name)

        except Exception as ex:
            db.session.rollback()  # rollback db work if broker error
            app.logger.error(f"Message broker failure :: {ex}")
            abort(500, message="Message Broker failure, see server log file")

        db.session.commit()

    def delete(self, subscription_uuid):
        self.delete_subscription(subscription_uuid)
        return '', 204


# -----------------------------------------------------------------------------------------------------


class SubscriptionSubjectAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /subscriptions/<uuid:subscription_uuid>/subjects
    #
    # Returns a collection of Subjects attached to the calling endpoint's given Subscription
    #
    def get_subscription_subjects(self, subscription_uuid):
        uuid = str(subscription_uuid)
        if not g.uudex_admin:
            filters = [Subscription.owner_endpoint_id == g.endpoint_id, Subscription.subscription_uuid == uuid]
        else:
            filters = [Subscription.subscription_uuid == uuid]

        subscription_subjects = SubscriptionSubject.query.\
            join(Subscription).\
            filter(*filters).all()

        if subscription_subjects is None:
            abort(404, message=f"No Subscription Subjects exist for given Subscription and calling endpoint")

        resp = SubscriptionSubjectView.generate_resp(subscription_subjects)
        return views.generate_resp_envelope(resp), 200

    def get(self, subscription_uuid):
        return self.get_subscription_subjects(subscription_uuid)

    # post
    #
    # endpoint: /subscriptions/<uuid:subscription_uuid>/subjects
    #
    # Attach a single Subject to an endpoint's given Subscription
    #
    def attach_subscription_subject(self, subscription_uuid):

        uuid = str(subscription_uuid)
        subscription = Subscription.query.filter(Subscription.owner_endpoint_id == g.endpoint_id, Subscription.subscription_uuid == uuid).first()
        if subscription is None:
            abort(404, message=f"Subscription not found")

        args = SubscriptionSubjectView.parse_post_req()

        # check is allowed to subscribe to subject
        if not authorization_service.has_subject_access("SUBSCRIBE", args['subject_uuid'], g.endpoint_uuid):
            abort(401, message=f"Unauthorized to subscribe to given Subject")

        subject = Subject.query.get_uuid_or_404(args['subject_uuid'])

        args['subject_id'] = subject.subject_id
        args['subscription_id'] = subscription.subscription_id
        args['backing_queue_name'] = MessageBrokerServiceBase.build_queue_name(g.endpoint_user_name, subject.subject_name,
                                                                               subscription.subscription_uuid)

        subscription_subject = SubscriptionSubject()
        subscription_subject.set_columns(**args)

        db.session.add(subscription_subject)
        db.session.flush()

        # Get policy settings for subject
        policy_attributes = authorization_service.get_subject_policy_attributes(g.participant_id, subject.dataset_definition_id)
        # print(f"POLCY_ATTRIBUTES: {policy_attributes}")

        try:
            full_queue_behavior = policy_attributes["full_queue_behavior"][1]
        except KeyError as e:
            full_queue_behavior= "NO_CONSTRAINTS"

        try:
            max_queue_size_bytes = policy_attributes["max_queue_size_kb"][1]*1000
        except KeyError as e:
            max_queue_size_bytes = None

        try:
            max_msg_cnt = policy_attributes["max_message_count"][1]
        except KeyError as e:
            max_msg_cnt = None

        # print(f"POLCY_ATTRIBUTES: {full_queue_behavior}, {policy_attributes}, {max_queue_size_bytes}, {max_msg_cnt}")

        try:
            mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)
            # If no performance constraints are needed
            if full_queue_behavior == "NO_CONSTRAINTS":
                new_queue_name = mb_client.create_subscription_subject(subscription.subscription_uuid, subject.subject_uuid, subject.subject_name,
                                                                   g.endpoint_user_name)
            else:
                # If performance constraints are needed
                new_queue_name = mb_client.create_subscription_subject_with_performance_constraints(subscription.subscription_uuid,
                subject.subject_uuid,
                subject.subject_name,
                g.endpoint_user_name,
                max_queue_size_kb=max_queue_size_bytes,
                max_message_count=max_msg_cnt,
                full_queue_behavior=full_queue_behavior)

            subscription_subject.set_columns(backing_queue_name=new_queue_name)

        except Exception as ex:
            db.session.rollback()  # rollback db work if broker error
            app.logger.error(f"Message broker failure :: {ex}")
            abort(500, message="Message Broker failure, see server log file")

        db.session.commit()

        resp = SubscriptionSubjectView.generate_resp(subscription_subject)
        return views.generate_resp_envelope(resp), 200

    def post(self, subscription_uuid):
        return self.attach_subscription_subject(subscription_uuid)

    # delete
    #
    # endpoint: /subscriptions/<uuid:subscription_uuid>/subjects/<int:subscription_subject_id>
    #
    # Detach a Subject from the calling endpoint's given Subscription
    #
    def detach_subscription_subject(self, subscription_uuid, subscription_subject_id):

        uuid = str(subscription_uuid)
        subscription_subject = db.session.query(SubscriptionSubject, Subject, Subscription).join(Subject).join(Subscription).\
            filter(SubscriptionSubject.subscription_subject_id == subscription_subject_id,
                   Subscription.owner_endpoint_id == g.endpoint_id,
                   Subscription.subscription_uuid == uuid).first()

        if subscription_subject is None:
            abort(404, message=f"Subscription Subject not found")

        db.session.delete(subscription_subject.SubscriptionSubject)
        db.session.flush()

        try:
            mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)

            mb_client.delete_subscription_subject(subscription_subject.Subscription.subscription_uuid, subscription_subject.Subject.subject_name,
                                                  g.endpoint_user_name)

        except Exception as ex:
            db.session.rollback()  # rollback db work if broker error
            app.logger.error(f"Message broker failure :: {ex}")
            abort(500, message="Message Broker failure, see server log file")

        db.session.commit()

    def delete(self, subscription_uuid, subscription_subject_id):
        self.detach_subscription_subject(subscription_uuid, subscription_subject_id)
        return '', 204


# -----------------------------------------------------------------------------------------------------


class SubscriptionConsumeAPI(base.UUDEXResource):

    def _get_messages(self, backing_queue_name, count=10):

        try:
            mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)
            messages = mb_client.get_messages(backing_queue_name, count)
            return messages
        except Exception as ex:
            db.session.rollback()  # rollback db work if broker error
            app.logger.error(f"Failure while getting message from broker :: {ex}")
            abort(500, message="Message Broker failure, see server log file")

    def _delete_queue(self, backing_queue_name):

        try:
            mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)
            mb_client.delete_queue(backing_queue_name)
        except Exception as ex:
            pass

    # get
    #
    # endpoint: /subscriptions/{subscription_uuid}/consume
    #
    # Consumes and returns one or more pending messages from message broker
    #
    #
    def consume_subscription(self, subscription_uuid):

        uuid = str(subscription_uuid)
        filters = [Subscription.owner_endpoint_id == g.endpoint_id, Subscription.subscription_uuid == uuid]

        subscription_subjects = db.session.query(Subject.subject_uuid, Subject.subject_name, Subject.owner_participant_id,
                                         SubscriptionSubject.preferred_fulfillment_type,
                                         SubscriptionSubject.backing_queue_name).\
            select_from(Subscription). \
            outerjoin(SubscriptionSubject). \
            outerjoin(Subject). \
            filter(*filters). \
            order_by(Subject.subject_name). \
            all()

        if subscription_subjects is None or len(subscription_subjects) == 0:
            abort(HTTPStatus.NOT_FOUND, message=f"Subscription does not exist for calling endpoint")

        resp_list = list()
        for subscription_subject in subscription_subjects:
            if not authorization_service.has_subject_access("SUBSCRIBE", subscription_subject.subject_uuid,
                                                            subscription_subject.owner_participant_id):
                self._delete_queue(subscription_subject.backing_queue_name)
                abort(HTTPStatus.FORBIDDEN, message=f"Unauthorized to consume Subject {subscription_subject.subject_uuid}")

            consume_object = {"subject_uuid": subscription_subject.subject_uuid,
                              "subject_name": subscription_subject.subject_name,
                              "message_count": 0,
                              "messages": list()}
            while True:
                messages = self._get_messages(subscription_subject.backing_queue_name, 10)
                if messages is None or len(messages) == 0:
                    break
                for message in messages:
                    entry = dict()
                    entry["message"] = message["payload"]
                    consume_object["messages"].append(entry)

            consume_object["message_count"] = len(consume_object["messages"])

            resp = MessageConsumeRespView.generate_resp(consume_object)
            resp_list.append(resp)

        return views.generate_resp_envelope(resp_list), HTTPStatus.OK

    def get(self, subscription_uuid=None):
        return self.consume_subscription(subscription_uuid)
