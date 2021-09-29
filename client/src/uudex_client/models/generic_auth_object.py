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


class GenericAuthObject(object):
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
        'object_uuid': 'str',
        'object_type': 'str'
    }

    attribute_map = {
        'object_uuid': 'object_uuid',
        'object_type': 'object_type'
    }

    def __init__(self, object_uuid=None, object_type=None):  # noqa: E501
        """GenericAuthObject - a model defined in Swagger"""  # noqa: E501
        self._object_uuid = None
        self._object_type = None
        self.discriminator = None
        self.object_uuid = object_uuid
        self.object_type = object_type

    @property
    def object_uuid(self):
        """Gets the object_uuid of this GenericAuthObject.  # noqa: E501

        The UUID of the object.  # noqa: E501

        :return: The object_uuid of this GenericAuthObject.  # noqa: E501
        :rtype: str
        """
        return self._object_uuid

    @object_uuid.setter
    def object_uuid(self, object_uuid):
        """Sets the object_uuid of this GenericAuthObject.

        The UUID of the object.  # noqa: E501

        :param object_uuid: The object_uuid of this GenericAuthObject.  # noqa: E501
        :type: str
        """
        if object_uuid is None:
            raise ValueError("Invalid value for `object_uuid`, must not be `None`")  # noqa: E501

        self._object_uuid = object_uuid

    @property
    def object_type(self):
        """Gets the object_type of this GenericAuthObject.  # noqa: E501

        The type code of the object represented in the object_uuid field.  This code can be 's', 'r', 'g', 'e' or 'p', which represents 'Subject', 'Role', 'Group', 'Endpoint' or 'Participant', respectively   # noqa: E501

        :return: The object_type of this GenericAuthObject.  # noqa: E501
        :rtype: str
        """
        return self._object_type

    @object_type.setter
    def object_type(self, object_type):
        """Sets the object_type of this GenericAuthObject.

        The type code of the object represented in the object_uuid field.  This code can be 's', 'r', 'g', 'e' or 'p', which represents 'Subject', 'Role', 'Group', 'Endpoint' or 'Participant', respectively   # noqa: E501

        :param object_type: The object_type of this GenericAuthObject.  # noqa: E501
        :type: str
        """
        if object_type is None:
            raise ValueError("Invalid value for `object_type`, must not be `None`")  # noqa: E501

        self._object_type = object_type

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
        if issubclass(GenericAuthObject, dict):
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
        if not isinstance(other, GenericAuthObject):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
