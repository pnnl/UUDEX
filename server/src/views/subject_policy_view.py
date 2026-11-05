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


class SubjectPolicyView(views.base.ModelViewBase):
    @classmethod
    def _build_resp_fields(cls):
        cls._resp_fields = {
            "subject_policy_uuid": fields.String,
            "action": fields.String,
            "full_queue_behavior": fields.String,
            "max_queue_size_kb": fields.Integer(None),
            "max_message_count": fields.Integer(None),
            "max_priority": fields.Integer(None),
            "dataset_definition_uuid": fields.String,
            "target_participant_uuid": fields.String(attribute="target_participant.participant_uuid"),
        }

    @classmethod
    def _build_post_parser(cls):
        cls._post_parser.add_argument("subject_policy_uuid", type=str)
        cls._post_parser.add_argument("action", type=str, choices=(None, "ALLOW", "DENY", "REVIEW"))
        cls._post_parser.add_argument("full_queue_behavior", type=str, choices=(None, "BLOCK_NEW", "PURGE_OLD", "NO_CONSTRAINT"))
        cls._post_parser.add_argument("max_queue_size_kb", type=int)
        cls._post_parser.add_argument("max_message_count", type=int)
        cls._post_parser.add_argument("max_priority", type=int)
        cls._post_parser.add_argument("dataset_definition_uuid", type=str)
        cls._post_parser.add_argument("target_participant_uuid", type=str)

