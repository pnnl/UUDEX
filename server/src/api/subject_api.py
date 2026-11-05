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

import hashlib
#
from http import HTTPStatus
from flask_restful import abort
from flask import g, request
from sqlalchemy import or_
#
import config
from api import base
from api.base import RequestProxy
from app_container import app
from models import db, Subject, DatasetDefinition, SubscriptionSubject
from services import authorization_service
#
from services.message_services.base import MessageBrokerServiceBase
from services.message_services.message_broker_common import message_broker_factory
import views
from views.message_publish_resp_view import MessagePublishRespView
from views.message_publish_view import MessagePublishView
from views.subject_view import SubjectView
from views.subject_view_discovery import SubjectViewDiscovery
from views.subject_view_enriched import SubjectViewEnriched


class SubjectAPI(base.UUDEXResource):

    # post
    #
    # endpoint: /subjects
    #
    # Creates a Subject if the calling participant is authorized
    #
    def create_subject(self):
        authorization_service.uudex_admin_or_part_admin_or_subj_admin_or_403()

        args = SubjectView.parse_post_req()

        dataset = DatasetDefinition.query.get_uuid_or_404(args['dataset_definition_uuid'])

        args['dataset_definition_id'] = dataset.dataset_definition_id
        args['owner_participant_id'] = g.participant_id

        if not g.uudex_admin:
          # check if caller is allowed to create subject according to subject policies
          policy_attributes = authorization_service.get_subject_policy_attributes(g.participant_id, dataset.dataset_definition_id)
          if policy_attributes['action'][1] in ["DENY", "REVIEW"]:  # include "REVIEW" in this demo version for now, may be handled more completely in later version
              abort(403, message=f"Subject creation denied by Subject Policy, at policy level [{policy_attributes['action'][0]}], for given Dataset")

        subject = Subject()
        subject.set_columns(**args)

        db.session.add(subject)
        db.session.flush()

        try:
            mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)
            new_queue_name = mb_client.create_subject(subject.subject_name, subject.subject_uuid)
            subject.set_columns(backing_exchange_name=MessageBrokerServiceBase.build_exchange_name(subject.subject_name,
                                                                                                   subject.subject_uuid))
        except Exception as ex:
            db.session.rollback()  # rollback db work if broker error
            # error_message = urllib.parse.unquote(ex.args[0])
            app.logger.error(f"Message broker failure :: {ex}")
            abort(500, message="Message Broker failure, see server log file")

        db.session.commit()

        resp = SubjectView.generate_resp(subject)
        return views.generate_resp_envelope(resp), 200

    def post(self, ):
        return self.create_subject()

    # get
    #
    # endpoint: /subjects OR
    # endpoint: /subjects/<uuid:subject_uuid>
    #
    # Return a collection of all Subjects in the system
    #
    def get_subject(self, subject_uuid):
        authorization_service.uudex_admin_or_part_admin_or_subj_admin_or_403()

        if not g.uudex_admin:
            filters = [Subject.owner_participant_id == g.participant_id]
        else:
            filters = [1 == 1]

        if subject_uuid is None:
            subjects = Subject.query.filter(*filters).all()
        else:
            uuid = str(subject_uuid)
            subjects = Subject.query.filter(*filters).get_uuid_or_404(uuid)

        resp = SubjectViewEnriched.generate_resp(subjects)
        return views.generate_resp_envelope(resp), 200

    def get(self, subject_uuid=None):
        return self.get_subject(subject_uuid)

    # patch
    #
    # endpoint: /admin/subjects/<uuid:subject_uuid>
    #
    # Update a single Subject
    #
    def update_subject(self, subject_uuid):
        authorization_service.uudex_admin_or_part_admin_or_subj_admin_or_403()

        if not g.uudex_admin:
            filters = [Subject.owner_participant_id == g.participant_id]
        else:
            filters = [1 == 1]

        uuid = str(subject_uuid)
        subject = Subject.query.filter(*filters).get_uuid_or_404(uuid)
        args = SubjectView.parse_patch_req()

        changes = subject.set_columns(**args)
        if len(changes):
            db.session.commit()

        resp = SubjectView.generate_resp(subject)
        return views.generate_put_resp_envelope(resp, changes), 200

    def patch(self, subject_uuid):
        return self.update_subject(subject_uuid)


    # delete
    #
    # endpoint: /admin/subjects/<uuid:subject_uuid>
    #
    # Delete a single Subject
    #
    def delete_subject(self, subject_uuid):
        authorization_service.uudex_admin_or_part_admin_or_subj_admin_or_403()

        if not g.uudex_admin:
            filters = [Subject.owner_participant_id == g.participant_id]
        else:
            filters = [1 == 1]

        uuid = str(subject_uuid)
        subject = Subject.query.filter(*filters).get_uuid_or_404(uuid)
        db.session.delete(subject)

        mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)
        mb_client.delete_subject(subject.subject_name, subject.subject_uuid)

        db.session.commit()

    def delete(self, subject_uuid):
        self.delete_subject(subject_uuid)
        return '', 204

class SubjectDiscoveryAPI(base.UUDEXResource):

    # get
    #
    # endpoint: /subjects/discover
    #
    # Performs the subject discovery action.
    #
    # Returns a collection of Subjects the calling endpoint is authorized to view
    #
    def discover(self):
        subject_uuids = authorization_service.get_discoverable_subjects(g.endpoint_uuid)

        # get subjects in uuid list and include any subjects owned by caller's participant
        subjects  = Subject.query.filter(or_(Subject.subject_uuid.in_(subject_uuids), Subject.owner_participant_id == g.participant_id)).all()

        if subjects is None or len(subjects) == 0:
            abort(404, code=404, message="No Subjects found")

        resp = SubjectViewDiscovery.generate_resp(subjects)
        return views.generate_resp_envelope(resp), 200

    def get(self):
        return self.discover()


class SubjectPublishAPI(base.UUDEXResource):

    def _send_message(self, backing_exchange_name, subject_name, message):

        try:
            mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)

            if not mb_client.publish_message(backing_exchange_name, subject_name, message):
                abort(500, code=500, message="Error publishing message to subject, see server log file")
        except Exception as ex:
            app.logger.error(f"Failure while sending message to broker :: {ex}")
            err_msg = "Message Broker failure, see server log file"
            try:
                import pyrabbit2
                if type(ex) == pyrabbit2.http.HTTPError:
                    err_msg = ex.reason
            except ImportError:
                pass
            abort(500, message=err_msg)

    # post
    #
    # endpoint: /subjects/{subject_uuid}/publish
    #
    # Publish one or more messages
    #
    # NOTE: we assume the payload is always base64 encoded by the client (ie, will be decoded when consumed)
    #
    def publish_message(self, subject_uuid):

        uuid = str(subject_uuid)
        subject = Subject.query.get_uuid_or_404(uuid)

        # subject must be part of a Subscription before a message can be published to it
        subscriptions = SubscriptionSubject.query.filter(SubscriptionSubject.subject_id == subject.subject_id).all()
        if subscriptions is None or len(subscriptions) == 0:
            abort(404, message=f"No Subscription for subject found, publish will not go through.")

        # check if caller is allowed to publish to Subject
        if not authorization_service.has_subject_access("PUBLISH", uuid, subject.owner_participant_id):
            abort(HTTPStatus.FORBIDDEN, message="Not authorized to publish to Subject")

        resp_list = list()
        request_json_list = list()

        if not isinstance(request.json, list):  # if not multiple requests
            request_json_list.append(request.json)
        else:
            request_json_list = request.json

        message_index = 0
        for message_json in request_json_list:  # request.json:
            new_req = RequestProxy()
            new_req.json = message_json
            args = MessagePublishView.parse_post_req(new_req)
            payload = args['message']
            self._send_message(subject.backing_exchange_name, subject.subject_name, payload)
            resp_message = {"message_index": message_index,
                            "message_md5_hash": hashlib.md5(payload.encode("utf-8")).hexdigest()}
            resp_list.append(resp_message)
            message_index = message_index + 1

        resp = MessagePublishRespView.generate_resp({"messages": resp_list})
        return views.generate_resp_envelope(resp), HTTPStatus.OK

    def post(self, subject_uuid):
        return self.publish_message(subject_uuid)

