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
from api.dataset_api import DatasetApi  # noqa: E501
from uudex_client.rest import ApiException


class TestDatasetApi(unittest.TestCase):
    """DatasetApi unit test stubs"""

    def setUp(self):
        self.api = api.dataset_api.DatasetApi()  # noqa: E501

    def tearDown(self):
        pass

    def test_create_dataset(self):
        """Test case for create_dataset

        Create a single Dataset in the given Subject and optionally publish a message that contains the Dataset  # noqa: E501
        """
        pass

    def test_delete_dataset(self):
        """Test case for delete_dataset

        Delete the Dataset and optionally publish a notification message  # noqa: E501
        """
        pass

    def test_get_dataset(self):
        """Test case for get_dataset

        Returns a single Dataset  # noqa: E501
        """
        pass

    def test_get_datasets(self):
        """Test case for get_datasets

        Returns a collection of Datasets, given the passed search parameters  # noqa: E501
        """
        pass

    def test_update_dataset(self):
        """Test case for update_dataset

        Update the Dataset and optionally publish a notification message  # noqa: E501
        """
        pass


if __name__ == '__main__':
    unittest.main()