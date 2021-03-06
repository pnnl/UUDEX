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

from uudex_client.models import SubjectPolicyEnrichedObjectList

class SubjectPolicyEnrichedAclConstraints(object):
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
        'subject_policy_acl_constraint_id': 'int',
        'privilege_allowed_name': 'str',
        'grant_scope_name': 'str',
        'object_list': 'list[SubjectPolicyEnrichedObjectList]'
    }

    attribute_map = {
        'subject_policy_acl_constraint_id': 'subject_policy_acl_constraint_id',
        'privilege_allowed_name': 'privilege_allowed_name',
        'grant_scope_name': 'grant_scope_name',
        'object_list': 'object_list'
    }

    def __init__(self, subject_policy_acl_constraint_id=None, privilege_allowed_name=None, grant_scope_name=None, object_list=None):  # noqa: E501
        """SubjectPolicyEnrichedAclConstraints - a model defined in Swagger"""  # noqa: E501
        self._subject_policy_acl_constraint_id = None
        self._privilege_allowed_name = None
        self._grant_scope_name = None
        self._object_list = None
        self.discriminator = None
        if subject_policy_acl_constraint_id is not None:
            self.subject_policy_acl_constraint_id = subject_policy_acl_constraint_id
        if privilege_allowed_name is not None:
            self.privilege_allowed_name = privilege_allowed_name
        if grant_scope_name is not None:
            self.grant_scope_name = grant_scope_name
        if object_list is not None:
            self.object_list = object_list

    @property
    def subject_policy_acl_constraint_id(self):
        """Gets the subject_policy_acl_constraint_id of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501


        :return: The subject_policy_acl_constraint_id of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501
        :rtype: int
        """
        return self._subject_policy_acl_constraint_id

    @subject_policy_acl_constraint_id.setter
    def subject_policy_acl_constraint_id(self, subject_policy_acl_constraint_id):
        """Sets the subject_policy_acl_constraint_id of this SubjectPolicyEnrichedAclConstraints.


        :param subject_policy_acl_constraint_id: The subject_policy_acl_constraint_id of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501
        :type: int
        """

        self._subject_policy_acl_constraint_id = subject_policy_acl_constraint_id

    @property
    def privilege_allowed_name(self):
        """Gets the privilege_allowed_name of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501


        :return: The privilege_allowed_name of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501
        :rtype: str
        """
        return self._privilege_allowed_name

    @privilege_allowed_name.setter
    def privilege_allowed_name(self, privilege_allowed_name):
        """Sets the privilege_allowed_name of this SubjectPolicyEnrichedAclConstraints.


        :param privilege_allowed_name: The privilege_allowed_name of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501
        :type: str
        """

        self._privilege_allowed_name = privilege_allowed_name

    @property
    def grant_scope_name(self):
        """Gets the grant_scope_name of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501


        :return: The grant_scope_name of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501
        :rtype: str
        """
        return self._grant_scope_name

    @grant_scope_name.setter
    def grant_scope_name(self, grant_scope_name):
        """Sets the grant_scope_name of this SubjectPolicyEnrichedAclConstraints.


        :param grant_scope_name: The grant_scope_name of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501
        :type: str
        """

        self._grant_scope_name = grant_scope_name

    @property
    def object_list(self):
        """Gets the object_list of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501


        :return: The object_list of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501
        :rtype: list[SubjectPolicyEnrichedObjectList]
        """
        return self._object_list

    @object_list.setter
    def object_list(self, object_list):
        """Sets the object_list of this SubjectPolicyEnrichedAclConstraints.


        :param object_list: The object_list of this SubjectPolicyEnrichedAclConstraints.  # noqa: E501
        :type: list[SubjectPolicyEnrichedObjectList]
        """

        self._object_list = object_list

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
        if issubclass(SubjectPolicyEnrichedAclConstraints, dict):
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
        if not isinstance(other, SubjectPolicyEnrichedAclConstraints):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
