# coding: utf-8

"""
    UUDEXApi

    uudex api  # noqa: E501

    OpenAPI spec version: 1.0
    Contact: jeff.welsh@pnnl.gov
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""

import pprint
import re  # noqa: F401

import six


class SubscriptionSubject(object):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    """
    """
    Attributes:
      swagger_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    swagger_types = {
        'subscription_subject_id': 'int',
        'subject_uuid': 'str',
        'subject_name': 'str',
        'preferred_fulfillment_type': 'str',
        'backing_queue_name': 'str'
    }

    attribute_map = {
        'subscription_subject_id': 'subscription_subject_id',
        'subject_uuid': 'subject_uuid',
        'subject_name': 'subject_name',
        'preferred_fulfillment_type': 'preferred_fulfillment_type',
        'backing_queue_name': 'backing_queue_name'
    }

    def __init__(self, subscription_subject_id=None, subject_uuid=None, subject_name=None, preferred_fulfillment_type=None, backing_queue_name=None):  # noqa: E501
        """SubscriptionSubject - a model defined in Swagger"""  # noqa: E501
        self._subscription_subject_id = None
        self._subject_uuid = None
        self._subject_name = None
        self._preferred_fulfillment_type = None
        self._backing_queue_name = None
        self.discriminator = None
        if subscription_subject_id is not None:
            self.subscription_subject_id = subscription_subject_id
        self.subject_uuid = subject_uuid
        if subject_name is not None:
            self.subject_name = subject_name
        self.preferred_fulfillment_type = preferred_fulfillment_type
        if backing_queue_name is not None:
            self.backing_queue_name = backing_queue_name

    @property
    def subscription_subject_id(self):
        """Gets the subscription_subject_id of this SubscriptionSubject.  # noqa: E501


        :return: The subscription_subject_id of this SubscriptionSubject.  # noqa: E501
        :rtype: int
        """
        return self._subscription_subject_id

    @subscription_subject_id.setter
    def subscription_subject_id(self, subscription_subject_id):
        """Sets the subscription_subject_id of this SubscriptionSubject.


        :param subscription_subject_id: The subscription_subject_id of this SubscriptionSubject.  # noqa: E501
        :type: int
        """

        self._subscription_subject_id = subscription_subject_id

    @property
    def subject_uuid(self):
        """Gets the subject_uuid of this SubscriptionSubject.  # noqa: E501


        :return: The subject_uuid of this SubscriptionSubject.  # noqa: E501
        :rtype: str
        """
        return self._subject_uuid

    @subject_uuid.setter
    def subject_uuid(self, subject_uuid):
        """Sets the subject_uuid of this SubscriptionSubject.


        :param subject_uuid: The subject_uuid of this SubscriptionSubject.  # noqa: E501
        :type: str
        """
        if subject_uuid is None:
            raise ValueError("Invalid value for `subject_uuid`, must not be `None`")  # noqa: E501

        self._subject_uuid = subject_uuid

    @property
    def subject_name(self):
        """Gets the subject_name of this SubscriptionSubject.  # noqa: E501


        :return: The subject_name of this SubscriptionSubject.  # noqa: E501
        :rtype: str
        """
        return self._subject_name

    @subject_name.setter
    def subject_name(self, subject_name):
        """Sets the subject_name of this SubscriptionSubject.


        :param subject_name: The subject_name of this SubscriptionSubject.  # noqa: E501
        :type: str
        """

        self._subject_name = subject_name

    @property
    def preferred_fulfillment_type(self):
        """Gets the preferred_fulfillment_type of this SubscriptionSubject.  # noqa: E501


        :return: The preferred_fulfillment_type of this SubscriptionSubject.  # noqa: E501
        :rtype: str
        """
        return self._preferred_fulfillment_type

    @preferred_fulfillment_type.setter
    def preferred_fulfillment_type(self, preferred_fulfillment_type):
        """Sets the preferred_fulfillment_type of this SubscriptionSubject.


        :param preferred_fulfillment_type: The preferred_fulfillment_type of this SubscriptionSubject.  # noqa: E501
        :type: str
        """
        if preferred_fulfillment_type is None:
            raise ValueError("Invalid value for `preferred_fulfillment_type`, must not be `None`")  # noqa: E501
        allowed_values = ["DATA_PUSH", "DATA_NOTIFY"]  # noqa: E501
        if preferred_fulfillment_type not in allowed_values:
            raise ValueError(
                "Invalid value for `preferred_fulfillment_type` ({0}), must be one of {1}"  # noqa: E501
                .format(preferred_fulfillment_type, allowed_values)
            )

        self._preferred_fulfillment_type = preferred_fulfillment_type

    @property
    def backing_queue_name(self):
        """Gets the backing_queue_name of this SubscriptionSubject.  # noqa: E501


        :return: The backing_queue_name of this SubscriptionSubject.  # noqa: E501
        :rtype: str
        """
        return self._backing_queue_name

    @backing_queue_name.setter
    def backing_queue_name(self, backing_queue_name):
        """Sets the backing_queue_name of this SubscriptionSubject.


        :param backing_queue_name: The backing_queue_name of this SubscriptionSubject.  # noqa: E501
        :type: str
        """

        self._backing_queue_name = backing_queue_name

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.swagger_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
            else:
                result[attr] = value
        if issubclass(SubscriptionSubject, dict):
            for key, value in self.items():
                result[key] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, SubscriptionSubject):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other