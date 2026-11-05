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

from flask_restful import fields
#
import views.base


class SubjectView(views.base.ModelViewBase):
    @classmethod
    def _build_resp_fields(cls):
        cls._resp_fields = {
            "subject_uuid": fields.String,
            "subject_name": fields.String,
            "dataset_instance_key": fields.String,
            "description": fields.String,
            "subscription_type": fields.String,
            "fulfillment_types_available": fields.String,
            "full_queue_behavior": fields.String,
            "max_queue_size_kb": fields.Integer(None),
            "max_message_count": fields.Integer(None),
            "priority": fields.Integer(None),
            "dataset_definition_uuid":  fields.String(attribute='dataset_definition.dataset_definition_uuid'),
            "owner_participant_uuid": fields.String(attribute='owner_participant.participant_uuid'),
            "create_datetime": fields.DateTime(dt_format='iso8601'),
        }

    @classmethod
    def _build_post_parser(cls):
        cls._post_parser.add_argument("subject_uuid", type=str)
        cls._post_parser.add_argument("subject_name", type=str, required=True)
        cls._post_parser.add_argument("dataset_instance_key", type=str, required=True)
        cls._post_parser.add_argument("description", type=str, required=True)
        cls._post_parser.add_argument("subscription_type", type=str, choices=("MEASUREMENT_VALUES", "EVENT"), required=True)
        cls._post_parser.add_argument("fulfillment_types_available", type=str, choices=("DATA_PUSH", "DATA_NOTIFY", "BOTH"), required=True)
        cls._post_parser.add_argument("full_queue_behavior", type=str, choices=("BLOCK_NEW", "PURGE_OLD", "NO_CONSTRAINT"))
        cls._post_parser.add_argument("max_queue_size_kb", type=int)
        cls._post_parser.add_argument("max_message_count", type=int)
        cls._post_parser.add_argument("priority", type=int)
        cls._post_parser.add_argument("dataset_definition_uuid", type=str, required=True)
        cls._post_parser.add_argument("owner_participant_uuid", type=str)
        cls._post_parser.add_argument("create_datetime", type=str)
