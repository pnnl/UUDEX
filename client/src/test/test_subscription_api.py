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
from api.subscription_api import SubscriptionApi  # noqa: E501
from uudex_client.rest import ApiException


class TestSubscriptionApi(unittest.TestCase):
    """SubscriptionApi unit test stubs"""

    def setUp(self):
        self.api = api.subscription_api.SubscriptionApi()  # noqa: E501

    def tearDown(self):
        pass

    def test_attach_subscription_subject(self):
        """Test case for attach_subscription_subject

        Attach a single Subject to the given Subscription  # noqa: E501
        """
        pass

    def test_consume_subscription(self):
        """Test case for consume_subscription

        Consumes the subscription and returns one or more pending messages from message broker  # noqa: E501
        """
        pass

    def test_create_subscription(self):
        """Test case for create_subscription

        Create a single Subscription  # noqa: E501
        """
        pass

    def test_delete_subscription(self):
        """Test case for delete_subscription

        Delelete a Subscription  # noqa: E501
        """
        pass

    def test_detach_subscription_subject(self):
        """Test case for detach_subscription_subject

        Detach a Subject from the given Subscription  # noqa: E501
        """
        pass

    def test_get_subscription(self):
        """Test case for get_subscription

        Gets a single Subscription  # noqa: E501
        """
        pass

    def test_get_subscription_subjects(self):
        """Test case for get_subscription_subjects

        Returns a collection of all Subjects attached to the given Subscription  # noqa: E501
        """
        pass

    def test_get_subscriptions(self):
        """Test case for get_subscriptions

        Returns a collection of the invoker's Subscriptions  # noqa: E501
        """
        pass

    def test_update_subscription(self):
        """Test case for update_subscription

        Update a single Subscription  # noqa: E501
        """
        pass


if __name__ == '__main__':
    unittest.main()