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
from views.custom_validators import max_length


class SubscriptionView(views.base.ModelViewBase):
    @classmethod
    def _build_resp_fields(cls):
        cls._resp_fields = {
            "subscription_uuid": fields.String,
            "subscription_name": fields.String,
            "subscription_state": fields.String,
            "create_datetime": fields.DateTime(dt_format='iso8601'),
            "owner_endpoint_uuid": fields.String(attribute='owner_endpoint.endpoint_uuid')
        }

    @classmethod
    def _build_post_parser(cls):
        cls._post_parser.add_argument("subscription_uuid", type=str)
        cls._post_parser.add_argument("subscription_name", type=max_length(30), required=True)
        cls._post_parser.add_argument("subscription_state", type=str, choices=("ACTIVE", "PAUSED"), required=True)
        cls._post_parser.add_argument("create_datetime", type=str)
        cls._post_parser.add_argument("owner_endpoint_uuid", type=str)
