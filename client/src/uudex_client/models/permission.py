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


class Permission(object):
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
        'privilege': 'str',
        'object_uuid': 'str',
        'object_type': 'str',
        'except_modifier_override': 'str'
    }

    attribute_map = {
        'subject_uuid': 'subject_uuid',
        'privilege': 'privilege',
        'object_uuid': 'object_uuid',
        'object_type': 'object_type',
        'except_modifier_override': 'except_modifier_override'
    }

    def __init__(self, subject_uuid=None, privilege=None, object_uuid=None, object_type=None, except_modifier_override=None):  # noqa: E501
        """Permission - a model defined in Swagger"""  # noqa: E501
        self._subject_uuid = None
        self._privilege = None
        self._object_uuid = None
        self._object_type = None
        self._except_modifier_override = None
        self.discriminator = None
        self.subject_uuid = subject_uuid
        self.privilege = privilege
        self.object_uuid = object_uuid
        self.object_type = object_type
        self.except_modifier_override = except_modifier_override

    @property
    def subject_uuid(self):
        """Gets the subject_uuid of this Permission.  # noqa: E501

        The subject to receive the privilege grant  # noqa: E501

        :return: The subject_uuid of this Permission.  # noqa: E501
        :rtype: str
        """
        return self._subject_uuid

    @subject_uuid.setter
    def subject_uuid(self, subject_uuid):
        """Sets the subject_uuid of this Permission.

        The subject to receive the privilege grant  # noqa: E501

        :param subject_uuid: The subject_uuid of this Permission.  # noqa: E501
        :type: str
        """
        if subject_uuid is None:
            raise ValueError("Invalid value for `subject_uuid`, must not be `None`")  # noqa: E501

        self._subject_uuid = subject_uuid

    @property
    def privilege(self):
        """Gets the privilege of this Permission.  # noqa: E501

        One of PUBLISH, SUBSCRIBE, or DISCOVER  # noqa: E501

        :return: The privilege of this Permission.  # noqa: E501
        :rtype: str
        """
        return self._privilege

    @privilege.setter
    def privilege(self, privilege):
        """Sets the privilege of this Permission.

        One of PUBLISH, SUBSCRIBE, or DISCOVER  # noqa: E501

        :param privilege: The privilege of this Permission.  # noqa: E501
        :type: str
        """
        if privilege is None:
            raise ValueError("Invalid value for `privilege`, must not be `None`")  # noqa: E501
        allowed_values = ["SUBSCRIBE", "PUBLISH", "MANAGE", "DISCOVER"]  # noqa: E501
        if privilege not in allowed_values:
            raise ValueError(
                "Invalid value for `privilege` ({0}), must be one of {1}"  # noqa: E501
                .format(privilege, allowed_values)
            )

        self._privilege = privilege

    @property
    def object_uuid(self):
        """Gets the object_uuid of this Permission.  # noqa: E501

        The UUID of the object  # noqa: E501

        :return: The object_uuid of this Permission.  # noqa: E501
        :rtype: str
        """
        return self._object_uuid

    @object_uuid.setter
    def object_uuid(self, object_uuid):
        """Sets the object_uuid of this Permission.

        The UUID of the object  # noqa: E501

        :param object_uuid: The object_uuid of this Permission.  # noqa: E501
        :type: str
        """
        if object_uuid is None:
            raise ValueError("Invalid value for `object_uuid`, must not be `None`")  # noqa: E501

        self._object_uuid = object_uuid

    @property
    def object_type(self):
        """Gets the object_type of this Permission.  # noqa: E501

        The type code of the object represented in the object_uuid field.  This code can be 's', 'r', 'g', 'e' or 'p', which represents 'Subject', 'Role', 'Group', 'Endpoint' or 'Participant', respectively  # noqa: E501

        :return: The object_type of this Permission.  # noqa: E501
        :rtype: str
        """
        return self._object_type

    @object_type.setter
    def object_type(self, object_type):
        """Sets the object_type of this Permission.

        The type code of the object represented in the object_uuid field.  This code can be 's', 'r', 'g', 'e' or 'p', which represents 'Subject', 'Role', 'Group', 'Endpoint' or 'Participant', respectively  # noqa: E501

        :param object_type: The object_type of this Permission.  # noqa: E501
        :type: str
        """
        if object_type is None:
            raise ValueError("Invalid value for `object_type`, must not be `None`")  # noqa: E501

        self._object_type = object_type

    @property
    def except_modifier_override(self):
        """Gets the except_modifier_override of this Permission.  # noqa: E501

        Specifies if the allow_except modifier applies to this permission.  Essentially inverts the permission rule and allows everyone (ie, public group) the applicable privilege EXCEPT the target of this grant.  See the UUDEX security design documents for details.  # noqa: E501

        :return: The except_modifier_override of this Permission.  # noqa: E501
        :rtype: str
        """
        return self._except_modifier_override

    @except_modifier_override.setter
    def except_modifier_override(self, except_modifier_override):
        """Sets the except_modifier_override of this Permission.

        Specifies if the allow_except modifier applies to this permission.  Essentially inverts the permission rule and allows everyone (ie, public group) the applicable privilege EXCEPT the target of this grant.  See the UUDEX security design documents for details.  # noqa: E501

        :param except_modifier_override: The except_modifier_override of this Permission.  # noqa: E501
        :type: str
        """
        if except_modifier_override is None:
            raise ValueError("Invalid value for `except_modifier_override`, must not be `None`")  # noqa: E501
        allowed_values = ["Y", "N"]  # noqa: E501
        if except_modifier_override not in allowed_values:
            raise ValueError(
                "Invalid value for `except_modifier_override` ({0}), must be one of {1}"  # noqa: E501
                .format(except_modifier_override, allowed_values)
            )

        self._except_modifier_override = except_modifier_override

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
        if issubclass(Permission, dict):
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
        if not isinstance(other, Permission):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
