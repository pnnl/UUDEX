from __future__ import print_function

import base64
from pprint import pprint
import logging
#
import uudex_client
#

LOG_FORMAT = ('%(levelname) -9s %(asctime)s  %(name) -55s %(funcName) '
              '-35s %(lineno) -4d: %(message)s')

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
#

configuration = uudex_client.Configuration()
client = uudex_client.ApiClient(configuration)
subject_api = uudex_client.SubjectApi(client)

# ----------------------------------------------------------------------------------------------

try:
    # publish a message
    print("\nPublish ::")

    message_payload1 = "FIRST - 1235 - test - test - abc"
    message_payload2 = "SECOND - 1235 - test - test - abc"

    if isinstance(message_payload1, str):
        b64_payload1 = message_payload1.encode("utf-8")
    else:
        b64_payload1 = message_payload1

    if isinstance(message_payload2, str):
        b64_payload2 = message_payload2.encode("utf-8")
    else:
        b64_payload2 = message_payload2

    b64_payload1 = base64.b64encode(b64_payload1).decode("utf-8")
    b64_payload2 = base64.b64encode(b64_payload2).decode("utf-8")

    resp = subject_api.publish_message('aef03e7e-44cc-4617-9c74-cffd956b831e',
                                       # body=[{"message": b64_payload1}, {"message": b64_payload2}])
                                       body={"message": b64_payload1})
    pprint(resp)

except Exception as e:
    print("Exception: %s\n" % e)
