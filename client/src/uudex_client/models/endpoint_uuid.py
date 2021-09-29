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


class EndpointUuid(object):
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
        'endpoint_uuid': 'str'
    }

    attribute_map = {
        'endpoint_uuid': 'endpoint_uuid'
    }

    def __init__(self, endpoint_uuid=None):  # noqa: E501
        """EndpointUuid - a model defined in Swagger"""  # noqa: E501
        self._endpoint_uuid = None
        self.discriminator = None
        if endpoint_uuid is not None:
            self.endpoint_uuid = endpoint_uuid

    @property
    def endpoint_uuid(self):
        """Gets the endpoint_uuid of this EndpointUuid.  # noqa: E501


        :return: The endpoint_uuid of this EndpointUuid.  # noqa: E501
        :rtype: str
        """
        return self._endpoint_uuid

    @endpoint_uuid.setter
    def endpoint_uuid(self, endpoint_uuid):
        """Sets the endpoint_uuid of this EndpointUuid.


        :param endpoint_uuid: The endpoint_uuid of this EndpointUuid.  # noqa: E501
        :type: str
        """

        self._endpoint_uuid = endpoint_uuid

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
        if issubclass(EndpointUuid, dict):
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
        if not isinstance(other, EndpointUuid):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
