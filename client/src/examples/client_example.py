from __future__ import print_function
from pprint import pprint
import logging
#
import urllib3

import uudex_client
from uudex_client import configurator
from uudex_client.rest import ApiException

LOG_FORMAT = ('%(levelname) -9s %(asctime)s  %(name) -55s %(funcName) '
              '-35s %(lineno) -4d: %(message)s')
logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
#
configuration = uudex_client.Configuration()

configurator.set_values(configuration, "pnnl_dev_windows")

client = uudex_client.ApiClient(configuration)
subscription_api = uudex_client.SubscriptionApi(client)
subject_api = uudex_client.SubjectApi(client)
data_type_api = uudex_client.DatatypeApi(client)
dataset_api = uudex_client.DatasetApi(client)
participant_api = uudex_client.ParticipantApi(client)

# ----------------------------------------------------------------------------------------------

try:
    # dataset
    print("\nDataset ::")
    datasets = dataset_api.get_datasets("c6d882de-4fb2-47f9-82fc-4e20944c98c2")
    pprint(datasets)
    dataset = dataset_api.get_dataset("e4254ee3-caa7-4cd6-bf7f-0f42eacd4b14")

    # subscription
    print("\nSubscription ::")
    subscription = subscription_api.get_subscription("a4f23ea9-f3e5-4e3e-b894-2a138b29564a")
    pprint(subscription)
    updated_sub = subscription_api.update_subscription("a4f23ea9-f3e5-4e3e-b894-2a138b29564a",
                                                       body={"subscription_name": "Test sub123",
                                                       "subscription_state": "ACTIVE"})

    print("\nSubject access ::")
    subscription_subjects = subscription_api.get_subscription_subjects("a4f23ea9-f3e5-4e3e-b894-2a138b29564a")

    for sub_subject in subscription_subjects:
        print("subject: " + sub_subject.subject_uuid)
        access = subject_api.get_subject_access(sub_subject.subject_uuid, 'SUBSCRIBE')
        pprint(access)


    # subjects
    print("\nSubject (liveness) ::")
    liveness_subject = subject_api.discover_subjects(subject_name_filter="_liveness")
    pprint(liveness_subject)

    print("\nSubjects ::")
    subjects = subject_api.discover_subjects()
    pprint(subjects)


    # participant
    print("\nParent Participants ::")
    parent_participant = participant_api.get_parent_participant()
    pprint(parent_participant)

    # requires admin priv
    print("\nAll participants ::")
    all_participants = participant_api.admin_get_all_participants()
    pprint(all_participants)

except Exception as e:
    print("Exception: %s\n" % e)

# ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------

try:
    datasets = dataset_api.get_datasets("c6d882de-4fb2-47f9-82fc-4e20944c98c2")
    dataset = dataset_api.get_dataset("42b4eeff-022a-468f-86b7-70adc06e0bcc")
except Exception as e:
    print("Exception: %s\n" % e)


try:
    new_sub = subscription_api.get_subscription("a4f23ea9-f3e5-4e3e-b894-2a138b29564a")
    #new_sub.subscription_state = "ACTIVE"
    #updated = subscription_api.update_subscription("a4f23ea9-f3e5-4e3e-b894-2a138b29564a", body=new_sub)

    updated = subscription_api.update_subscription("a4f23ea9-f3e5-4e3e-b894-2a138b29564a",
                                                   body={"subscription_name": "Test sub", "subscription_state": "ACTIVE"})
except Exception as e:
    print("Exception: %s\n" % e)


try:
    # Returns the calling Endpoint's parent Participant
    api_response = participant_api.get_parent_participant()
    pprint(api_response)

except ApiException as e:
    print("Exception when calling DefaultApi->get_parent_participant: %s\n" % e)


try:
    # Returns a collection of all Data Types in the system
    sub_subjects = subscription_api.get_subscription_subjects("a4f23ea9-f3e5-4e3e-b894-2a138b29564a")
    # subscription = next((x for x in subscriptions if x.subscription_uuid == "a4f23ea9-f3e5-4e3e-b894-2a138b29564a"), None)
    pprint(sub_subjects)

    for sub_subject in sub_subjects:
        print("subject: " + sub_subject.subject_uuid)
        access = subject_api.get_subject_access(sub_subject.subject_uuid, 'SUBSCRIBE')

    subscription = subscription_api.get_subscription_subjects("a4f23ea9-f3e5-4e3e-b894-2a138b29564a")
    for subject in subscription.subjects:
        print("subject: " + subject.backing_queue_name)

except ApiException as e:
    print("Exception when calling DefaultApi->get_all_data_types: %s\n" % e)
except urllib3.exceptions.HTTPError as e:
    print("HHTP exception when calling DefaultApi->get_all_data_types: %s\n" % e)


try:
    # Returns a collection of all Data Types in the system
    api_response = data_type_api.get_all_data_types()
    pprint(api_response)
except ApiException as e:
    print("Exception when calling DefaultApi->get_all_data_types: %s\n" % e)
