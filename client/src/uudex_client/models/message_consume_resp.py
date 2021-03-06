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


class MessageConsumeResp(object):
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
        'subject_uuid': 'str',
        'subject_name': 'str',
        'message_count': 'int',
        'messages': 'list[MessageConsumeRespMessages]'
    }

    attribute_map = {
        'subject_uuid': 'subject_uuid',
        'subject_name': 'subject_name',
        'message_count': 'message_count',
        'messages': 'messages'
    }

    def __init__(self, subject_uuid=None, subject_name=None, message_count=None, messages=None):  # noqa: E501
        """MessageConsumeResp - a model defined in Swagger"""  # noqa: E501
        self._subject_uuid = None
        self._subject_name = None
        self._message_count = None
        self._messages = None
        self.discriminator = None
        if subject_uuid is not None:
            self.subject_uuid = subject_uuid
        if subject_name is not None:
            self.subject_name = subject_name
        if message_count is not None:
            self.message_count = message_count
        if messages is not None:
            self.messages = messages

    @property
    def subject_uuid(self):
        """Gets the subject_uuid of this MessageConsumeResp.  # noqa: E501


        :return: The subject_uuid of this MessageConsumeResp.  # noqa: E501
        :rtype: str
        """
        return self._subject_uuid

    @subject_uuid.setter
    def subject_uuid(self, subject_uuid):
        """Sets the subject_uuid of this MessageConsumeResp.


        :param subject_uuid: The subject_uuid of this MessageConsumeResp.  # noqa: E501
        :type: str
        """

        self._subject_uuid = subject_uuid

    @property
    def subject_name(self):
        """Gets the subject_name of this MessageConsumeResp.  # noqa: E501


        :return: The subject_name of this MessageConsumeResp.  # noqa: E501
        :rtype: str
        """
        return self._subject_name

    @subject_name.setter
    def subject_name(self, subject_name):
        """Sets the subject_name of this MessageConsumeResp.


        :param subject_name: The subject_name of this MessageConsumeResp.  # noqa: E501
        :type: str
        """

        self._subject_name = subject_name

    @property
    def message_count(self):
        """Gets the message_count of this MessageConsumeResp.  # noqa: E501


        :return: The message_count of this MessageConsumeResp.  # noqa: E501
        :rtype: int
        """
        return self._message_count

    @message_count.setter
    def message_count(self, message_count):
        """Sets the message_count of this MessageConsumeResp.


        :param message_count: The message_count of this MessageConsumeResp.  # noqa: E501
        :type: int
        """

        self._message_count = message_count

    @property
    def messages(self):
        """Gets the messages of this MessageConsumeResp.  # noqa: E501


        :return: The messages of this MessageConsumeResp.  # noqa: E501
        :rtype: list[MessageConsumeRespMessages]
        """
        return self._messages

    @messages.setter
    def messages(self, messages):
        """Sets the messages of this MessageConsumeResp.


        :param messages: The messages of this MessageConsumeResp.  # noqa: E501
        :type: list[MessageConsumeRespMessages]
        """

        self._messages = messages

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
        if issubclass(MessageConsumeResp, dict):
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
        if not isinstance(other, MessageConsumeResp):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
