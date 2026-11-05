"""
Tests for message consumption endpoint
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from uudex_server.main import app
from uudex_server.models import Subscription, Subject
from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.models.endpoint_models import EndPoint
from uudex_server.models.message_models import MessageConsumeRequest, MessageContent
from uudex_server.models.participant_models import Participant
from uudex_server.models.subscription_subject_models import SubscriptionSubject

client = TestClient(app)


@pytest.fixture
def mock_user():
    """Create a mock authenticated user for testing"""
    endpoint = EndPoint(
        endpoint_id=1,
        participant_id=1,
        endpoint_name="test-endpoint",
        certificate_dn="CN=test-user",
        uudex_administrator_sw="N"
    )
    return AuthenticatedUser(endpoint=endpoint)


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user for testing"""
    endpoint = EndPoint(
        endpoint_id=2,
        participant_id=1,
        endpoint_name="admin-endpoint",
        certificate_dn="CN=admin-user",
        uudex_administrator_sw="Y"
    )
    return AuthenticatedUser(endpoint=endpoint)


@pytest.fixture
def mock_subscription():
    """Create a mock subscription for testing"""
    return Subscription(
        subscription_uuid="test-subscription-uuid",
        subscription_name="Test Subscription",
        owner_endpoint_id=1,
        participant_id=1
    )


@pytest.fixture
def mock_subject():
    """Create a mock subject for testing"""
    return Subject(
        subject_uuid="test-subject-uuid",
        subject_name="test-subject",
        dataset_instance_key="test-key",
        subscription_type="pull",
        fulfillment_types_available="immediate",
        full_queue_behavior="NO_CONSTRAINT",
        max_queue_size_kb=None,
        max_message_count=None,
        priority=None,
        backing_exchange_name="test-exchange",
        owner_participant_id=1,
        dataset_definition_id=1
    )


@pytest.fixture
def mock_subscription_subject(mock_subscription, mock_subject):
    """Create a mock subscription subject relationship"""
    return SubscriptionSubject(
        subscription_uuid=mock_subscription.subscription_uuid,
        subject_uuid=mock_subject.subject_uuid,
        subscription=mock_subscription,
        subject=mock_subject
    )


class TestMessageConsumption:
    """Test suite for message consumption functionality"""

    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionRepository')
    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionSubjectRepository')
    @patch('uudex_server.endpoints.subscription_endpoints.message_broker_factory')
    @patch('uudex_server.endpoints.subscription_endpoints.get_settings')
    @pytest.mark.asyncio
    async def test_consume_messages_success(self, mock_get_settings, mock_broker_factory, 
                                          mock_sub_subject_repo, mock_sub_repo,
                                          mock_user, mock_subscription, mock_subscription_subject):
        """Test successful message consumption"""
        from uudex_server.endpoints.subscription_endpoints import consume_messages
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_sub_repo_instance = Mock()
        mock_sub_repo_instance.select_subscription_by_uuid = AsyncMock(return_value=mock_subscription)
        mock_sub_repo.return_value = mock_sub_repo_instance
        
        mock_sub_subject_repo_instance = Mock()
        mock_sub_subject_repo_instance.select_subjects_by_subscription_uuid = AsyncMock(return_value=[mock_subscription_subject])
        mock_sub_subject_repo.return_value = mock_sub_subject_repo_instance
        
        mock_settings = Mock()
        mock_settings.messagebus_connection = "rabbitmq://test"
        mock_get_settings.return_value = mock_settings
        
        mock_broker = Mock()
        mock_broker.build_queue_name.return_value = "q_uudex_test-subject_test-subscription-uuid"
        mock_broker.get_messages.return_value = [
            {
                'payload': 'test message 1',
                'message_id': 'msg-1',
                'timestamp': datetime.utcnow(),
                'properties': {'key': 'value'}
            }
        ]
        mock_broker_factory.return_value = mock_broker
        
        consume_request = MessageConsumeRequest(count=1, timeout=30)
        
        # Call the endpoint
        result = await consume_messages(
            subscription_uuid="test-subscription-uuid",
            consume_request=consume_request,
            session=mock_session,
            user=mock_user
        )
        
        # Assertions
        assert result.subscription_uuid == "test-subscription-uuid"
        assert result.total_consumed == 1
        assert len(result.messages) == 1
        assert result.messages[0].payload == "test message 1"
        assert result.messages[0].message_id == "msg-1"
        
        # Verify repository calls
        mock_sub_repo_instance.select_subscription_by_uuid.assert_called_once_with(
            subscription_uuid="test-subscription-uuid"
        )
        mock_sub_subject_repo_instance.select_subjects_by_subscription_uuid.assert_called_once()
        
        # Verify broker calls
        mock_broker.build_queue_name.assert_called_once_with(
            tag="uudex",
            subject_name="test-subject", 
            subscription_uuid="test-subscription-uuid"
        )
        mock_broker.get_messages.assert_called_once_with(
            "q_uudex_test-subject_test-subscription-uuid",
            count=1
        )

    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionRepository')
    @pytest.mark.asyncio
    async def test_consume_messages_subscription_not_found(self, mock_sub_repo, mock_user):
        """Test consuming messages from non-existent subscription"""
        from uudex_server.endpoints.subscription_endpoints import consume_messages
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_sub_repo_instance = Mock()
        mock_sub_repo_instance.select_subscription_by_uuid = AsyncMock(return_value=None)
        mock_sub_repo.return_value = mock_sub_repo_instance
        
        consume_request = MessageConsumeRequest(count=1)
        
        # Call should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await consume_messages(
                subscription_uuid="non-existent-uuid",
                consume_request=consume_request,
                session=mock_session,
                user=mock_user
            )
        
        assert exc_info.value.status_code == 404
        assert "Subscription not found" in str(exc_info.value.detail)

    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionRepository')
    @pytest.mark.asyncio
    async def test_consume_messages_unauthorized(self, mock_sub_repo, mock_user):
        """Test consuming messages from subscription owned by different user"""
        from uudex_server.endpoints.subscription_endpoints import consume_messages
        
        # Setup mocks - subscription owned by different endpoint
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        different_subscription = Subscription(
            subscription_uuid="test-subscription-uuid",
            subscription_name="Different User's Subscription",
            owner_endpoint_id=999,  # Different from mock_user.endpoint.endpoint_id (1)
            participant_id=1
        )
        mock_sub_repo_instance = Mock()
        mock_sub_repo_instance.select_subscription_by_uuid = AsyncMock(return_value=different_subscription)
        mock_sub_repo.return_value = mock_sub_repo_instance
        
        consume_request = MessageConsumeRequest(count=1)
        
        # Call should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await consume_messages(
                subscription_uuid="test-subscription-uuid",
                consume_request=consume_request,
                session=mock_session,
                user=mock_user
            )
        
        assert exc_info.value.status_code == 403
        assert "Not authorized to consume messages" in str(exc_info.value.detail)

    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionRepository')
    @pytest.mark.asyncio
    async def test_consume_messages_admin_bypass_authorization(self, mock_sub_repo, mock_admin_user):
        """Test that admin users can consume from any subscription"""
        from uudex_server.endpoints.subscription_endpoints import consume_messages
        
        # Setup mocks - subscription owned by different endpoint but user is admin
        mock_session = Mock(spec=AsyncSession)
        
        different_subscription = Subscription(
            subscription_uuid="test-subscription-uuid", 
            subscription_name="Different User's Subscription",
            owner_endpoint_id=999,  # Different from admin user
            participant_id=1
        )
        mock_sub_repo_instance = Mock()
        mock_sub_repo_instance.select_subscription_by_uuid = AsyncMock(return_value=different_subscription)
        mock_sub_repo.return_value = mock_sub_repo_instance
        
        # Mock empty subscription subjects to avoid broker setup
        with patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionSubjectRepository') as mock_sub_subject_repo:
            mock_sub_subject_repo_instance = Mock()
            mock_sub_subject_repo_instance.select_subjects_by_subscription_uuid = AsyncMock(return_value=[])
            mock_sub_subject_repo.return_value = mock_sub_subject_repo_instance
            
            consume_request = MessageConsumeRequest(count=1)
            
            # Should succeed for admin user
            result = await consume_messages(
                subscription_uuid="test-subscription-uuid",
                consume_request=consume_request,
                session=mock_session,
                user=mock_admin_user
            )
            
            # Should return empty response but not raise authorization error
            assert result.subscription_uuid == "test-subscription-uuid"
            assert result.total_consumed == 0
            assert len(result.messages) == 0

    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionRepository')
    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionSubjectRepository')
    @pytest.mark.asyncio
    async def test_consume_messages_no_subjects(self, mock_sub_subject_repo, mock_sub_repo, 
                                              mock_user, mock_subscription):
        """Test consuming messages from subscription with no attached subjects"""
        from uudex_server.endpoints.subscription_endpoints import consume_messages
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_sub_repo_instance = Mock()
        mock_sub_repo_instance.select_subscription_by_uuid = AsyncMock(return_value=mock_subscription)
        mock_sub_repo.return_value = mock_sub_repo_instance
        
        mock_sub_subject_repo_instance = Mock()
        mock_sub_subject_repo_instance.select_subjects_by_subscription_uuid = AsyncMock(return_value=[])
        mock_sub_subject_repo.return_value = mock_sub_subject_repo_instance
        
        consume_request = MessageConsumeRequest(count=5)
        
        # Call the endpoint
        result = await consume_messages(
            subscription_uuid="test-subscription-uuid",
            consume_request=consume_request,
            session=mock_session,
            user=mock_user
        )
        
        # Should return empty response
        assert result.subscription_uuid == "test-subscription-uuid"
        assert result.total_consumed == 0
        assert len(result.messages) == 0

    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionRepository')
    @patch('uudex_server.endpoints.subscription_endpoints.ssr.SubscriptionSubjectRepository')
    @patch('uudex_server.endpoints.subscription_endpoints.message_broker_factory')
    @patch('uudex_server.endpoints.subscription_endpoints.get_settings')
    @pytest.mark.asyncio
    async def test_consume_messages_multiple_subjects(self, mock_get_settings, mock_broker_factory,
                                                    mock_sub_subject_repo, mock_sub_repo,
                                                    mock_user, mock_subscription):
        """Test consuming messages from subscription with multiple subjects"""
        from uudex_server.endpoints.subscription_endpoints import consume_messages
        
        # Setup mocks with multiple subjects
        subject1 = Subject(
            subject_uuid="subject-1", 
            subject_name="subject-1", 
            dataset_instance_key="key-1",
            subscription_type="pull",
            fulfillment_types_available="immediate",
            full_queue_behavior="NO_CONSTRAINT",
            max_queue_size_kb=None,
            max_message_count=None,
            priority=None,
            backing_exchange_name="exchange-1",
            owner_participant_id=1,
            dataset_definition_id=1
        )
        subject2 = Subject(
            subject_uuid="subject-2", 
            subject_name="subject-2", 
            dataset_instance_key="key-2",
            subscription_type="pull",
            fulfillment_types_available="immediate",
            full_queue_behavior="NO_CONSTRAINT",
            max_queue_size_kb=None,
            max_message_count=None,
            priority=None,
            backing_exchange_name="exchange-2",
            owner_participant_id=1,
            dataset_definition_id=1
        )
        
        subscription_subjects = [
            SubscriptionSubject(
                subscription_uuid=mock_subscription.subscription_uuid,
                subject_uuid="subject-1",
                subscription=mock_subscription,
                subject=subject1
            ),
            SubscriptionSubject(
                subscription_uuid=mock_subscription.subscription_uuid,
                subject_uuid="subject-2", 
                subscription=mock_subscription,
                subject=subject2
            )
        ]
        
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_sub_repo_instance = Mock()
        mock_sub_repo_instance.select_subscription_by_uuid = AsyncMock(return_value=mock_subscription)
        mock_sub_repo.return_value = mock_sub_repo_instance
        
        mock_sub_subject_repo_instance = Mock()
        mock_sub_subject_repo_instance.select_subjects_by_subscription_uuid = AsyncMock(return_value=subscription_subjects)
        mock_sub_subject_repo.return_value = mock_sub_subject_repo_instance
        
        mock_settings = Mock()
        mock_settings.messagebus_connection = "rabbitmq://test"
        mock_get_settings.return_value = mock_settings
        
        mock_broker = Mock()
        mock_broker.build_queue_name.return_value = "q_uudex_subject_test-subscription-uuid"
        mock_broker.get_messages.side_effect = [
            [{'payload': 'message from subject 1', 'message_id': 'msg-1'}],
            [{'payload': 'message from subject 2', 'message_id': 'msg-2'}]
        ]
        mock_broker_factory.return_value = mock_broker
        
        consume_request = MessageConsumeRequest(count=2)
        
        # Call the endpoint
        result = await consume_messages(
            subscription_uuid="test-subscription-uuid",
            consume_request=consume_request,
            session=mock_session,
            user=mock_user
        )
        
        # Should return messages from both subjects
        assert result.subscription_uuid == "test-subscription-uuid"
        assert result.total_consumed == 2
        assert len(result.messages) == 2
        
        # Verify broker was called for both subjects
        assert mock_broker.get_messages.call_count == 2


class TestMessageConsumeRequest:
    """Test suite for MessageConsumeRequest model validation"""

    def test_valid_request(self):
        """Test valid message consume request"""
        request = MessageConsumeRequest(count=5, timeout=60)
        assert request.count == 5
        assert request.timeout == 60

    def test_default_values(self):
        """Test default values for MessageConsumeRequest"""
        request = MessageConsumeRequest()
        assert request.count == 1
        assert request.timeout == 30

    def test_count_validation(self):
        """Test count field validation"""
        # Valid count
        request = MessageConsumeRequest(count=50)
        assert request.count == 50
        
        # Invalid count - too low
        with pytest.raises(ValueError):
            MessageConsumeRequest(count=0)
            
        # Invalid count - too high  
        with pytest.raises(ValueError):
            MessageConsumeRequest(count=101)

    def test_timeout_validation(self):
        """Test timeout field validation"""
        # Valid timeout
        request = MessageConsumeRequest(timeout=120)
        assert request.timeout == 120
        
        # Invalid timeout - too low
        with pytest.raises(ValueError):
            MessageConsumeRequest(timeout=0)
            
        # Invalid timeout - too high
        with pytest.raises(ValueError):
            MessageConsumeRequest(timeout=301)