# coding: utf-8

"""
    UUDEXApi

    uudex api  # noqa: E501

    OpenAPI spec version: 1.0
    Contact: jeff.welsh@pnnl.gov
    Generated by: https://github.com/swagger-api/swagger-codegen.git
"""

from __future__ import absolute_import

import unittest

import uudex_client
from api.object_type_api import ObjectTypeApi  # noqa: E501
from uudex_client.rest import ApiException


class TestObjectTypeApi(unittest.TestCase):
    """ObjectTypeApi unit test stubs"""

    def setUp(self):
        self.api = api.object_type_api.ObjectTypeApi()  # noqa: E501

    def tearDown(self):
        pass

    def test_get_object_type(self):
        """Test case for get_object_type

        Get object type based on a generic object UUID  # noqa: E501
        """
        pass


if __name__ == '__main__':
    unittest.main()
