import base64

import uudex_client
from uudex_client import Dataset


class UudexPublisher:
    def __init__(self, configuration):
        self._uudex_client = uudex_client.ApiClient(configuration)
        self._subscription_api = uudex_client.SubscriptionApi(self._uudex_client)
        self._subject_api = uudex_client.SubjectApi(self._uudex_client)
        self._dataset_api = uudex_client.DatasetApi(self._uudex_client)

    def publish(self, subject_uuid, message_payload, dataset_uuid=None, dataset_name=None, description=None,
                properties=None):
        # todo: TTL based LRU cache for access results keyed by subject_uuid
        access = self._subject_api.get_subject_access(subject_uuid, 'PUBLISH')
        if access.access_level == "DENY":
            raise Exception(f"Access denied to publish to subject [{subject_uuid}")

        # Subject type of EVENT
        if access.subject_subscription_type == "EVENT":
            if isinstance(message_payload, str):
                b64_payload = message_payload.encode("utf-8")
            else:
                b64_payload = message_payload

            b64_payload = base64.b64encode(b64_payload).decode("utf-8")

            if not dataset_uuid:
                if not dataset_name and not description:
                    raise Exception(
                        f"dataset_name and description are required when creating a new Dataset for an EVENT Subject")
                new_dataset = Dataset(dataset_name=dataset_name, description=description, properties=properties,
                                      payload=b64_payload, payload_compression_algorithm="NONE",
                                      subject_uuid=subject_uuid)
                new_dataset = self._dataset_api.create_dataset(body=new_dataset)
                return new_dataset
            else:
                # just set payload for now - TODO: change other attributes
                dataset = self._dataset_api.get_dataset(dataset_uuid)
                dataset.payload = b64_payload
                updated_dataset = self._dataset_api.update_dataset(dataset_uuid, body=dataset, publish_message=True)
                return updated_dataset

        # Subject type of MEASUREMENT_VALUES (ie, ICCP) published here
        body = [uudex_client.MessagePublish(message=message_payload)]
        message_payload = self._subject_api.publish_message(subject_uuid, body=body)
        return message_payload
