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

import flask_restful
from flask_restful import http_status_message
#
from api import participant_api, subject_policy_api, subject_api, subscription_api
from api.endpoint_api import EndpointAPI, EndpointAPI
#
import common
import config


class UUDEXApi(flask_restful.Api):
    def handle_error(self, e):
        """Our custom error handler for the API class,  tweaked to suit our purposes.
        This is needed so we can get the exact error response format we want, in a
        repeatable fashion no matter which http error code is passed.

        :param e: the raised Exception object
        :type e: Exception

        """
        resp = super().handle_error(e)

        error_cls_name = type(e).__name__
        if error_cls_name not in self.errors:
            message = common.extract_attr_from_exception(e, str(e))
            if resp.status_code >= 500:
                message = http_status_message(resp.status_code) + " :: " + message

            resp.data = "{{\"code\": {0}, \"message\": \"{1}\" }}".format(resp.status_code, message)

        return resp


uudex_api = UUDEXApi(prefix=config.API_PREFIX)
