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

from collections import OrderedDict
from uuid import uuid4

import config
from views.contact_view import ContactView


# TODO: do we even need metadata?? Should be for message passing only?
def generate_resp_envelope(payload, object_type="objectType"):

    if not config.INCLUDE_RESPONSE_META_DATA:
        return payload

    first = None

    for first in payload:
        break  # first is bound to the first item

    if first is not None:
        if isinstance(first, OrderedDict):
            count = len(payload)
        else:
            count = 1
    else:
        count = 0

    # message_uuid = str(uuid4())

    if isinstance(payload, list):
        for i, item in enumerate(payload):
            metadata = OrderedDict({"payload_item": i + 1, "payload_item_count": count})
            item['metadata_'] = metadata
    else:
        metadata = OrderedDict({"payload_item": 1, "payload_item_count": count})
        payload['metadata_'] = metadata

    return payload


# TODO: do we even need metadata?? Should be for message passing only?
def generate_put_resp_envelope(payload, changes, object_type="objectType"):

    if not config.INCLUDE_RESPONSE_META_DATA:
        return payload

    # message_uuid = str(uuid4())

    metadata = OrderedDict({"payload_item": 1, "payload_item_count": 1, "change_log": changes})
    payload['metadata_'] = metadata

    return payload
