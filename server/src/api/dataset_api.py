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

import base64
import hashlib
#
import json
from http import HTTPStatus

from flask_restful import abort
from flask import g, request
#
import config
import views
from api import base
from app_container import app
from services import authorization_service
from services.authorization_service import has_subject_access
#
from services.message_services.message_broker_common import message_broker_factory
from models import db, Subject, Dataset
from views.dataset_view import DatasetView
from views.dataset_view_enriched import DatasetViewEnriched


# -----------------------------------------------------------------------------------------------------


class DatasetAPI(base.UUDEXResource):

    @staticmethod
    def _build_message(verb, dataset_uuid, subject_uuid, payload=None):
        fulfillment_type = "DATA_PUSH" if payload else "DATA_NOTIFY"
        ret = {"verb": verb, "fulfillment_type": fulfillment_type, "dataset_uuid": dataset_uuid,
                "subject_uuid": subject_uuid, "payload": payload}
        return json.dumps(ret)

    def _send_message(self, backing_exchange_name, subject_name, message):

        try:
            mb_client = message_broker_factory(config.MESSAGE_BROKER_URL)

            if not mb_client.publish_message(backing_exchange_name, subject_name, message):
                abort(500, code=500, message="Error publishing message to subject, see server log file")
        except Exception as ex:
            db.session.rollback()  # rollback db work if broker error
            app.logger.error(f"Failure while sending message to broker :: {ex}")
            abort(500, message="Message Broker failure, see server log file")

    # get
    #
    # endpoint: /datasets OR
    # endpoint: /datasets/<uuid:dataset_uuid>
    #
    # Returns a collection of all the Datasets applied to given search parameters
    #
    # Query parm: subject_uuid - Subject to search
    # Query parm: search_expression - Contains a custom query expression that applies a filter based on key/value properties
    # Query parm: participant_uuid - Limit search to datasets owned by this participant
    #
    #  OR
    #
    # Returns a single Dataset
    #
    #
    def get_dataset(self, dataset_uuid):

        if dataset_uuid:
            subject_uuid = str(dataset_uuid)
            dataset = Dataset.query.get_uuid_or_404(subject_uuid)
            if not has_subject_access("SUBSCRIBE", dataset.subject.subject_uuid, dataset.subject.owner_participant_id):
                abort(403, message="Not authorized to read/subscribe to Subject")
            resp = DatasetViewEnriched.generate_resp(dataset)
            return views.generate_resp_envelope(resp),  HTTPStatus.OK

        subject_uuid = request.args.get('subject_uuid')
        if not subject_uuid:
            abort(400, message="subject_uuid required")

        subject = Subject.query.get_uuid_or_404(subject_uuid)
        if not has_subject_access("SUBSCRIBE", subject_uuid, subject.owner_participant_id):
            abort(403, message="Not authorized to read/subscribe to Subject")

        kwargs = {}
        kwargs['subject_id'] = subject.subject_id
        participant_uuid = request.args.get('participant_uuid')
        search_expression_string = request.args.get('search_expression', None)
        if search_expression_string is not None:
            try:
                search_expression_list = json.loads(search_expression_string)
            except json.decoder.JSONDecodeError:
                abort(400, code=400, message=f"search expression string is not in correct format:{search_expression_string}")

            if 'properties' in list(search_expression_list.keys()):
                search_expression_list['properties'] = json.dumps(search_expression_list['properties'])
                kwargs.update(search_expression_list)

        datasets = Dataset.query.filter_by(**kwargs).all()
        #datasets = Dataset.query.filter(Dataset.subject_id == subject.subject_id).all()
        if not datasets:
            abort(404, message="No Datasets found")

        resp = DatasetViewEnriched.generate_resp(datasets)
        return views.generate_resp_envelope(resp), 200

    def get(self, dataset_uuid=None):
        return self.get_dataset(dataset_uuid)

    # post
    #
    # endpoint: /subjects/<uuid:subject_uuid>/datasets
    #
    # Create a single Dataset in the given Subject and optionally publish a message that contains the Dataset
    # Query parm : publish_message - Whether to also publish a notice message to the parent subject
    #
    def create_dataset(self):

        args = DatasetView.parse_post_req()

        uuid = args.get('subject_uuid')
        subject = Subject.query.get_uuid_or_404(uuid)

        # check if caller is allowed to create dataset
        if not has_subject_access("PUBLISH", uuid, subject.owner_participant_id):
            abort(403, message="Not authorized to publish to Subject")

        args['subject_id'] = subject.subject_id
        args['owner_participant_id'] = g.participant_id
        del args['subject_uuid']

        dataset = Dataset()
        dataset.set_columns(**args)

        try:
            datasets = Dataset.query.filter(Dataset.subject_id == subject.subject_id).all()
        except Exception as ex:
            datasets = []

        existing_payload_size = 0
        for dsets in datasets:
            existing_payload_size += dsets.payload_size

        # Get policy settings for subject
        policy_attributes = authorization_service.get_subject_policy_attributes(g.participant_id,
                                                                                subject.dataset_definition_id)
        try:
            max_queue_size_bytes = policy_attributes["max_queue_size_kb"][1] * 1000
        except KeyError as e:
            max_queue_size_bytes = 0

        props = args.get('properties', None)
        dataset_name = args.get('dataset_name', None)
        if props:
            try:
                json_props = json.loads(props)
            except json.decoder.JSONDecodeError:
                abort(400, code=400, message="Properties string is not in correct format")

        bin_payload = base64.b64decode(args['payload'], validate=True)
        if existing_payload_size + len(bin_payload) > max_queue_size_bytes:
            abort(404, message=f"Cannot store the dataset. Maximum dataset size for the subject"
                               f" is reached as per subject policy")

        bin_payload = base64.b64decode(args['payload'], validate=True)
        dataset.payload = bin_payload
        dataset.payload_size = len(bin_payload)
        dataset.payload_md5_hash = hashlib.md5(bin_payload).hexdigest()
        dataset.payload_compression_algorithm = 'NONE'
        dataset.version_number = 1
        if props:
            dataset.properties = props
        if dataset_name:
            dataset.dataset_name = dataset_name
        db.session.add(dataset)
        db.session.flush()

        #
        # If measurement_values type -> publish directly to rabbit here
        # If event -> call dataset API to publish.  Then API looks as subject fulfillment_type to determine how to pub to rabbit
        #

        payload = None if subject.fulfillment_types_available == "DATA_NOTIFY" else args['payload']
        message = self._build_message("created", str(dataset.dataset_uuid), str(subject.subject_uuid), payload=payload)

        try:
           self._send_message(subject.backing_exchange_name, subject.subject_name, message)
        except Exception:
           abort(500, code=500, message="Error publishing dataset creation notification message")

        db.session.commit()

        resp = DatasetViewEnriched.generate_resp(dataset)
        return views.generate_resp_envelope(resp), 200

    def post(self):
        return self.create_dataset()

    # patch
    #
    # endpoint: /datasets/<uuid:dataset_uuid>
    #
    # Update the Dataset and optionally publish a notification message
    # Query parm : publish_message - Whether to also publish a notice message to the parent subject
    #
    def update_dataset(self, dataset_uuid):

        uuid = str(dataset_uuid)
        dataset = Dataset.query.get_uuid_or_404(uuid)
        if not dataset:
            abort(404, message="Dataset not found")

        # check if caller is allowed to access dataset
        subject_uuid = dataset.subject.subject_uuid
        if not has_subject_access("MANAGE", subject_uuid, dataset.subject.owner_participant_id):
            abort(403, message="Not authorized to publish to Subject")

        args = DatasetView.parse_patch_req()

        changes = dataset.set_columns(**args)
        if len(changes):
            if 'payload' in args:
                bin_payload = base64.b64decode(args['payload'], validate=True)
                dataset.payload = bin_payload
                dataset.payload_size = len(bin_payload)
                dataset.payload_md5_hash = hashlib.md5(bin_payload).hexdigest()
                dataset.payload_compression_algorithm = 'NONE'

            dataset.version_number += 1

            db.session.flush()

            publish = bool(request.args.get('publish_message'))
            if publish:
                subject = dataset.subject
                if 'payload' in args and subject.fulfillment_types_available != "DATA_NOTIFY":
                  payload = args['payload']
                else:
                  payload = None

                message = self._build_message("updated", str(dataset.dataset_uuid), str(subject.subject_uuid),
                                              payload=payload)
                self._send_message(subject.backing_exchange_name, subject.subject_name, message)

            db.session.commit()

        resp = DatasetViewEnriched.generate_resp(dataset)
        return views.generate_put_resp_envelope(resp, changes), 200

    def patch(self, dataset_uuid):
        return self.update_dataset(dataset_uuid)

    # delete
    #
    # endpoint: /datasets/<uuid:dataset_uuid>
    #
    # Delete the Dataset and optionally publish a notification message
    # Query parm : publish_message - Whether to also publish a notice message to the parent subject
    #
    def delete_dataset(self, dataset_uuid):

        uuid = str(dataset_uuid)
        dataset = Dataset.query.get_uuid_or_404(uuid)

        # check if caller is allowed to access dataset
        subject_uuid = dataset.subject.subject_uuid
        if not has_subject_access("MANAGE", subject_uuid, dataset.subject.owner_participant_id):
            abort(403, message="Not authorized to publish to Subject")

        db.session.delete(dataset)

        publish = bool(request.args.get('publish_message'))

        if publish:
            subject = dataset.subject
            message = self._build_message("deleted", str(dataset.dataset_uuid), str(subject.subject_uuid),
                                          payload=None)
            self._send_message(subject.backing_exchange_name, subject.subject_name, message)

        db.session.commit()

    def delete(self, dataset_uuid):
        self.delete_dataset(dataset_uuid)
        return '', 204
