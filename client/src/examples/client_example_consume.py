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
subscription_api = uudex_client.SubscriptionApi(client)

# ----------------------------------------------------------------------------------------------

try:
    # consume a subscription
    print("\nConsume ::")

    resp = subscription_api.consume_subscription("aa6f1305-20ad-42d1-affa-43cafb8f1bf4")
    pprint(resp)

except Exception as e:
    print("Exception: %s\n" % e)
