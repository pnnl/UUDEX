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


class SubjectPolicyAclConstraint(object):
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
        'participant_uuid_list': 'list[str]'
    }

    attribute_map = {
        'subject_policy_acl_constraint_id': 'subject_policy_acl_constraint_id',
        'privilege_allowed_name': 'privilege_allowed_name',
        'grant_scope_name': 'grant_scope_name',
        'participant_uuid_list': 'participant_uuid_list'
    }

    def __init__(self, subject_policy_acl_constraint_id=None, privilege_allowed_name=None, grant_scope_name=None, participant_uuid_list=None):  # noqa: E501
        """SubjectPolicyAclConstraint - a model defined in Swagger"""  # noqa: E501
        self._subject_policy_acl_constraint_id = None
        self._privilege_allowed_name = None
        self._grant_scope_name = None
        self._participant_uuid_list = None
        self.discriminator = None
        if subject_policy_acl_constraint_id is not None:
            self.subject_policy_acl_constraint_id = subject_policy_acl_constraint_id
        self.privilege_allowed_name = privilege_allowed_name
        self.grant_scope_name = grant_scope_name
        self.participant_uuid_list = participant_uuid_list

    @property
    def subject_policy_acl_constraint_id(self):
        """Gets the subject_policy_acl_constraint_id of this SubjectPolicyAclConstraint.  # noqa: E501


        :return: The subject_policy_acl_constraint_id of this SubjectPolicyAclConstraint.  # noqa: E501
        :rtype: int
        """
        return self._subject_policy_acl_constraint_id

    @subject_policy_acl_constraint_id.setter
    def subject_policy_acl_constraint_id(self, subject_policy_acl_constraint_id):
        """Sets the subject_policy_acl_constraint_id of this SubjectPolicyAclConstraint.


        :param subject_policy_acl_constraint_id: The subject_policy_acl_constraint_id of this SubjectPolicyAclConstraint.  # noqa: E501
        :type: int
        """

        self._subject_policy_acl_constraint_id = subject_policy_acl_constraint_id

    @property
    def privilege_allowed_name(self):
        """Gets the privilege_allowed_name of this SubjectPolicyAclConstraint.  # noqa: E501


        :return: The privilege_allowed_name of this SubjectPolicyAclConstraint.  # noqa: E501
        :rtype: str
        """
        return self._privilege_allowed_name

    @privilege_allowed_name.setter
    def privilege_allowed_name(self, privilege_allowed_name):
        """Sets the privilege_allowed_name of this SubjectPolicyAclConstraint.


        :param privilege_allowed_name: The privilege_allowed_name of this SubjectPolicyAclConstraint.  # noqa: E501
        :type: str
        """
        if privilege_allowed_name is None:
            raise ValueError("Invalid value for `privilege_allowed_name`, must not be `None`")  # noqa: E501
        allowed_values = ["BROADEST_ALLOWED_PUBLISHER_ACCESS", "BROADEST_ALLOWED_SUBSCRIBER_ACCESS", "BROADEST_ALLOWED_MANAGER_ACCESS"]  # noqa: E501
        if privilege_allowed_name not in allowed_values:
            raise ValueError(
                "Invalid value for `privilege_allowed_name` ({0}), must be one of {1}"  # noqa: E501
                .format(privilege_allowed_name, allowed_values)
            )

        self._privilege_allowed_name = privilege_allowed_name

    @property
    def grant_scope_name(self):
        """Gets the grant_scope_name of this SubjectPolicyAclConstraint.  # noqa: E501


        :return: The grant_scope_name of this SubjectPolicyAclConstraint.  # noqa: E501
        :rtype: str
        """
        return self._grant_scope_name

    @grant_scope_name.setter
    def grant_scope_name(self, grant_scope_name):
        """Sets the grant_scope_name of this SubjectPolicyAclConstraint.


        :param grant_scope_name: The grant_scope_name of this SubjectPolicyAclConstraint.  # noqa: E501
        :type: str
        """
        if grant_scope_name is None:
            raise ValueError("Invalid value for `grant_scope_name`, must not be `None`")  # noqa: E501
        allowed_values = ["ALLOW_ONLY", "ALLOW_EXCEPT", "ALLOW_ALL", "ALLOW_NONE"]  # noqa: E501
        if grant_scope_name not in allowed_values:
            raise ValueError(
                "Invalid value for `grant_scope_name` ({0}), must be one of {1}"  # noqa: E501
                .format(grant_scope_name, allowed_values)
            )

        self._grant_scope_name = grant_scope_name

    @property
    def participant_uuid_list(self):
        """Gets the participant_uuid_list of this SubjectPolicyAclConstraint.  # noqa: E501


        :return: The participant_uuid_list of this SubjectPolicyAclConstraint.  # noqa: E501
        :rtype: list[str]
        """
        return self._participant_uuid_list

    @participant_uuid_list.setter
    def participant_uuid_list(self, participant_uuid_list):
        """Sets the participant_uuid_list of this SubjectPolicyAclConstraint.


        :param participant_uuid_list: The participant_uuid_list of this SubjectPolicyAclConstraint.  # noqa: E501
        :type: list[str]
        """
        if participant_uuid_list is None:
            raise ValueError("Invalid value for `participant_uuid_list`, must not be `None`")  # noqa: E501

        self._participant_uuid_list = participant_uuid_list

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
        if issubclass(SubjectPolicyAclConstraint, dict):
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
        if not isinstance(other, SubjectPolicyAclConstraint):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
