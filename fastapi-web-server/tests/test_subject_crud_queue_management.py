"""
Comprehensive tests for subject CRUD operations and queue management
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from uudex_server.main import app
from uudex_server.models import Subject, SubjectUpdate, SubjectQueueInfo, MessagePublishRequest
from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.models.endpoint_models import EndPoint
from uudex_server.models.subject_models import (
    SubjectCreate,
    QueueManagementRequest,
    QueueManagementResponse,
    SubjectWithMetrics,
    BulkSubjectOperation,
    BulkOperationResult
)

client = TestClient(app)


# =====================================================
# FIXTURES
# =====================================================

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
def mock_subject():
    """Create a mock subject for testing"""
    return Subject(
        subject_id=1,
        subject_uuid="test-subject-uuid",
        subject_name="test-subject",
        dataset_instance_key="test-key",
        subscription_type="pull",
        fulfillment_types_available="immediate",
        full_queue_behavior="NO_CONSTRAINT",
        max_queue_size_kb=None,
        max_message_count=None,
        priority=None,
        backing_exchange_name="e_test-subject_test-subject-uuid",
        owner_participant_id=1,
        dataset_definition_id=1
    )


@pytest.fixture
def mock_subject_create():
    """Create a mock SubjectCreate for testing"""
    return SubjectCreate(
        subject_uuid="test-subject-uuid",
        subject_name="test-subject",
        dataset_instance_key="test-key",
        subscription_type="pull",
        fulfillment_types_available="immediate",
        full_queue_behavior="NO_CONSTRAINT",
        max_queue_size_kb=None,
        max_message_count=None,
        priority=None,
        backing_exchange_name="e_test-subject_test-subject-uuid",
        owner_participant_id=1,
        dataset_definition_id=1
    )


@pytest.fixture
def mock_broker_service():
    """Create a mock message broker service"""
    broker = Mock()
    broker.create_subject = Mock(return_value=0)
    broker.delete_subject = Mock(return_value=0)
    broker.build_exchange_name = Mock(return_value="e_test-subject_test-subject-uuid")
    broker.build_queue_name = Mock(return_value="q_uudex_test-subject_test-subscription-uuid")
    broker.publish_message = Mock(return_value=0)
    broker.delete_queue = Mock(return_value=0)
    return broker


# =====================================================
# BASIC CRUD OPERATIONS TESTS
# =====================================================

class TestSubjectCRUD:
    """Test suite for basic subject CRUD operations"""

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_get_all_subjects_admin(self, mock_repo, mock_admin_user):
        """Test getting all subjects as admin user"""
        from uudex_server.endpoints.subject_endpoints import get_all_subjects
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_repo_instance = Mock()
        mock_repo_instance.select_all = AsyncMock(return_value=[])
        mock_repo.return_value = mock_repo_instance
        
        # Call endpoint
        result = await get_all_subjects(session=mock_session, user=mock_admin_user)
        
        # Assertions
        assert result == []
        mock_repo_instance.select_all.assert_called_once()

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @patch('uudex_server.endpoints.subject_endpoints.pr.select_all_subjects')
    @pytest.mark.asyncio
    async def test_get_all_subjects_regular_user(self, mock_select_all, mock_repo, mock_user):
        """Test getting subjects as regular user (filtered by participant)"""
        from uudex_server.endpoints.subject_endpoints import get_all_subjects
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_select_all.return_value = []
        
        # Call endpoint
        result = await get_all_subjects(session=mock_session, user=mock_user)
        
        # Assertions
        assert result == []
        mock_select_all.assert_called_once_with(session=mock_session, participant_id=1)

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_create_subject_success(self, mock_repo, mock_user, mock_subject_create, mock_subject, mock_broker_service):
        """Test successful subject creation"""
        from uudex_server.endpoints.subject_endpoints import create_subject
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_repo_instance = Mock()
        mock_repo_instance.create = AsyncMock(return_value=mock_subject)
        mock_repo.return_value = mock_repo_instance
        
        # Call endpoint
        result = await create_subject(
            subject_data=mock_subject_create,
            session=mock_session,
            user=mock_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert result == mock_subject
        mock_repo_instance.create.assert_called_once()
        mock_broker_service.create_subject.assert_called_once()

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_create_subject_broker_failure(self, mock_repo, mock_user, mock_subject_create, mock_subject, mock_broker_service):
        """Test subject creation with broker failure (should rollback)"""
        from uudex_server.endpoints.subject_endpoints import create_subject
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_repo_instance = Mock()
        mock_repo_instance.create = AsyncMock(return_value=mock_subject)
        mock_repo_instance.delete = AsyncMock()
        mock_repo.return_value = mock_repo_instance
        
        # Make broker fail
        mock_broker_service.create_subject.side_effect = Exception("Broker error")
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await create_subject(
                subject_data=mock_subject_create,
                session=mock_session,
                user=mock_user,
                broker=mock_broker_service
            )
        
        # Assertions
        assert exc_info.value.status_code == 500
        assert "Failed to create message broker infrastructure" in str(exc_info.value.detail)
        mock_repo_instance.delete.assert_called_once_with(mock_subject.subject_id)

    @patch('uudex_server.endpoints.subject_endpoints.pr.select_subject_by_id')
    @pytest.mark.asyncio
    async def test_get_subject_by_id_success(self, mock_select, mock_user, mock_subject):
        """Test getting subject by ID with proper authorization"""
        from uudex_server.endpoints.subject_endpoints import get_subject_by_id
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        mock_select.return_value = mock_subject
        
        # Call endpoint
        result = await get_subject_by_id(
            subject_id=1,
            session=mock_session,
            user=mock_user
        )
        
        # Assertions
        assert result == mock_subject

    @patch('uudex_server.endpoints.subject_endpoints.pr.select_subject_by_id')
    @pytest.mark.asyncio
    async def test_get_subject_by_id_not_found(self, mock_select, mock_user):
        """Test getting non-existent subject by ID"""
        from uudex_server.endpoints.subject_endpoints import get_subject_by_id
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_select.return_value = None
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await get_subject_by_id(
                subject_id=999,
                session=mock_session,
                user=mock_user
            )
        
        # Assertions
        assert exc_info.value.status_code == 404
        assert "Subject not found" in str(exc_info.value.detail)

    @patch('uudex_server.endpoints.subject_endpoints.pr.select_subject_by_id')
    @pytest.mark.asyncio
    async def test_get_subject_by_id_unauthorized(self, mock_select, mock_user):
        """Test getting subject by ID with insufficient authorization"""
        from uudex_server.endpoints.subject_endpoints import get_subject_by_id
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        # Subject owned by different participant
        different_subject = Subject(
            subject_id=1,
            subject_uuid="test-subject-uuid",
            subject_name="test-subject",
            dataset_instance_key="test-key",
            subscription_type="pull",
            fulfillment_types_available="immediate",
            full_queue_behavior="NO_CONSTRAINT",
            max_queue_size_kb=None,
            max_message_count=None,
            priority=None,
            backing_exchange_name="e_test-subject_test-subject-uuid",
            owner_participant_id=999,  # Different participant
            dataset_definition_id=1
        )
        mock_select.return_value = different_subject
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await get_subject_by_id(
                subject_id=1,
                session=mock_session,
                user=mock_user
            )
        
        # Assertions
        assert exc_info.value.status_code == 403
        assert "Not authorized to view this subject" in str(exc_info.value.detail)

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_get_subject_by_uuid_success(self, mock_repo, mock_user, mock_subject):
        """Test getting subject by UUID"""
        from uudex_server.endpoints.subject_endpoints import get_subject_by_uuid
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_repo_instance = Mock()
        mock_repo_instance.select_by_field = AsyncMock(return_value=mock_subject)
        mock_repo.return_value = mock_repo_instance
        
        # Call endpoint
        result = await get_subject_by_uuid(
            subject_uuid="test-subject-uuid",
            session=mock_session,
            user=mock_user
        )
        
        # Assertions
        assert result == mock_subject
        mock_repo_instance.select_by_field.assert_called_once_with("subject_uuid", "test-subject-uuid")

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @patch('uudex_server.endpoints.subject_endpoints.pr.select_subject_by_id')
    @pytest.mark.asyncio
    async def test_update_subject_success(self, mock_select, mock_repo, mock_user, mock_subject):
        """Test successful subject update"""
        from uudex_server.endpoints.subject_endpoints import update_subject
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_select.return_value = mock_subject
        
        mock_repo_instance = Mock()
        mock_repo_instance.update = AsyncMock(return_value=mock_subject)
        mock_repo.return_value = mock_repo_instance
        
        update_data = SubjectUpdate(subject_name="updated-subject-name")
        
        # Call endpoint
        result = await update_subject(
            subject_id=1,
            subject_update=update_data,
            session=mock_session,
            user=mock_user,
            broker=Mock()
        )
        
        # Assertions
        assert result == mock_subject
        mock_repo_instance.update.assert_called_once()

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @patch('uudex_server.endpoints.subject_endpoints.pr.select_subject_by_id')
    @pytest.mark.asyncio
    async def test_delete_subject_success(self, mock_select, mock_repo, mock_user, mock_subject, mock_broker_service):
        """Test successful subject deletion"""
        from uudex_server.endpoints.subject_endpoints import delete_subject
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_select.return_value = mock_subject
        
        mock_repo_instance = Mock()
        mock_repo_instance.delete = AsyncMock()
        mock_repo.return_value = mock_repo_instance
        
        # Call endpoint
        result = await delete_subject(
            subject_id=1,
            session=mock_session,
            user=mock_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert result["message"] == "Subject deleted successfully"
        assert result["subject_id"] == 1
        mock_broker_service.delete_subject.assert_called_once()
        mock_repo_instance.delete.assert_called_once_with(1)


# =====================================================
# QUEUE MANAGEMENT TESTS
# =====================================================

class TestQueueManagement:
    """Test suite for queue management operations"""

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_get_subject_queue_info(self, mock_repo, mock_user, mock_subject, mock_broker_service):
        """Test getting queue information for a subject"""
        from uudex_server.endpoints.subject_endpoints import get_subject_queue_info
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_repo_instance = Mock()
        mock_repo_instance.select_by_field = AsyncMock(return_value=mock_subject)
        mock_repo.return_value = mock_repo_instance
        
        # Call endpoint
        result = await get_subject_queue_info(
            subject_uuid="test-subject-uuid",
            session=mock_session,
            user=mock_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert isinstance(result, SubjectQueueInfo)
        assert result.subject_uuid == "test-subject-uuid"
        assert result.subject_name == "test-subject"

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_manage_subject_queues_info_action(self, mock_repo, mock_user, mock_subject, mock_broker_service):
        """Test queue management with info action"""
        from uudex_server.endpoints.subject_endpoints import manage_subject_queues
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_repo_instance = Mock()
        mock_repo_instance.select_by_field = AsyncMock(return_value=mock_subject)
        mock_repo.return_value = mock_repo_instance
        
        queue_request = QueueManagementRequest(action="info")
        
        # Call endpoint
        result = await manage_subject_queues(
            subject_uuid="test-subject-uuid",
            queue_request=queue_request,
            session=mock_session,
            user=mock_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert isinstance(result, QueueManagementResponse)
        assert result.success is True
        assert "Queue information retrieved successfully" in result.message

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_manage_subject_queues_delete_action(self, mock_repo, mock_user, mock_subject, mock_broker_service):
        """Test queue management with delete action"""
        from uudex_server.endpoints.subject_endpoints import manage_subject_queues
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_repo_instance = Mock()
        mock_repo_instance.select_by_field = AsyncMock(return_value=mock_subject)
        mock_repo.return_value = mock_repo_instance
        
        queue_request = QueueManagementRequest(action="delete", queue_name="test-queue")
        
        # Call endpoint
        result = await manage_subject_queues(
            subject_uuid="test-subject-uuid",
            queue_request=queue_request,
            session=mock_session,
            user=mock_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert isinstance(result, QueueManagementResponse)
        assert result.success is True
        assert "Queue test-queue deleted successfully" in result.message
        mock_broker_service.delete_queue.assert_called_once_with("test-queue")

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_manage_subject_queues_unsupported_action(self, mock_repo, mock_user, mock_subject, mock_broker_service):
        """Test queue management with unsupported action"""
        from uudex_server.endpoints.subject_endpoints import manage_subject_queues
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_repo_instance = Mock()
        mock_repo_instance.select_by_field = AsyncMock(return_value=mock_subject)
        mock_repo.return_value = mock_repo_instance
        
        queue_request = QueueManagementRequest(action="invalid-action")
        
        # Call endpoint - should return error response, not raise exception
        result = await manage_subject_queues(
            subject_uuid="test-subject-uuid",
            queue_request=queue_request,
            session=mock_session,
            user=mock_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert isinstance(result, QueueManagementResponse)
        assert result.success is False
        assert "Unsupported action: invalid-action" in result.message


# =====================================================
# MESSAGE PUBLISHING TESTS
# =====================================================

class TestMessagePublishing:
    """Test suite for message publishing functionality"""

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_publish_messages_to_subject_success(self, mock_repo, mock_user, mock_subject, mock_broker_service):
        """Test successful message publishing to subject"""
        from uudex_server.endpoints.subject_endpoints import publish_messages_to_subject
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_repo_instance = Mock()
        mock_repo_instance.select_by_field = AsyncMock(return_value=mock_subject)
        mock_repo.return_value = mock_repo_instance
        
        publish_request = MessagePublishRequest(messages=["test message 1", "test message 2"])
        
        # Call endpoint
        result = await publish_messages_to_subject(
            subject_uuid="test-subject-uuid",
            publish_request=publish_request,
            session=mock_session,
            user=mock_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert result.published_count == 2
        assert result.subject_uuid == "test-subject-uuid"
        assert len(result.message_ids) == 2
        assert mock_broker_service.publish_message.call_count == 2

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_publish_messages_subject_not_found(self, mock_repo, mock_user):
        """Test publishing to non-existent subject"""
        from uudex_server.endpoints.subject_endpoints import publish_messages_to_subject
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_repo_instance = Mock()
        mock_repo_instance.select_by_field = AsyncMock(return_value=None)
        mock_repo.return_value = mock_repo_instance
        
        publish_request = MessagePublishRequest(messages=["test message"])
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await publish_messages_to_subject(
                subject_uuid="non-existent-uuid",
                publish_request=publish_request,
                session=mock_session,
                user=mock_user,
                broker=Mock()
            )
        
        # Assertions
        assert exc_info.value.status_code == 404
        assert "Subject not found" in str(exc_info.value.detail)


# =====================================================
# BULK OPERATIONS TESTS
# =====================================================

class TestBulkOperations:
    """Test suite for bulk subject operations"""

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_bulk_delete_subjects_success(self, mock_repo, mock_admin_user, mock_subject, mock_broker_service):
        """Test successful bulk deletion of subjects"""
        from uudex_server.endpoints.subject_endpoints import bulk_subject_operations
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo_instance = Mock()
        mock_repo_instance.select_by_field = AsyncMock(return_value=mock_subject)
        mock_repo_instance.delete = AsyncMock()
        mock_repo.return_value = mock_repo_instance
        
        bulk_request = BulkSubjectOperation(
            subject_uuids=["uuid1", "uuid2"],
            operation="delete"
        )
        
        # Call endpoint
        result = await bulk_subject_operations(
            bulk_request=bulk_request,
            session=mock_session,
            user=mock_admin_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert isinstance(result, BulkOperationResult)
        assert len(result.successful) == 2
        assert len(result.failed) == 0
        assert result.total_processed == 2

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_bulk_operations_non_admin_user(self, mock_repo, mock_user):
        """Test bulk operations with non-admin user (should fail)"""
        from uudex_server.endpoints.subject_endpoints import bulk_subject_operations
        
        mock_session = Mock(spec=AsyncSession)
        
        bulk_request = BulkSubjectOperation(
            subject_uuids=["uuid1"],
            operation="delete"
        )
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await bulk_subject_operations(
                bulk_request=bulk_request,
                session=mock_session,
                user=mock_user,
                broker=Mock()
            )
        
        # Assertions
        assert exc_info.value.status_code == 403
        assert "Only administrators can perform bulk operations" in str(exc_info.value.detail)


# =====================================================
# ADVANCED FEATURES TESTS
# =====================================================

class TestAdvancedFeatures:
    """Test suite for advanced features like metrics"""

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @patch('uudex_server.endpoints.subject_endpoints.pr.select_all_subjects')
    @pytest.mark.asyncio
    async def test_get_subjects_with_metrics(self, mock_select_all, mock_repo, mock_user, mock_subject, mock_broker_service):
        """Test getting subjects with metrics"""
        from uudex_server.endpoints.subject_endpoints import get_subjects_with_metrics
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        # Make subject have empty subscription_links to avoid AttributeError
        mock_subject.subscription_links = []
        mock_select_all.return_value = [mock_subject]
        
        # Call endpoint
        result = await get_subjects_with_metrics(
            session=mock_session,
            user=mock_user,
            broker=mock_broker_service
        )
        
        # Assertions
        assert len(result) == 1
        assert isinstance(result[0], SubjectWithMetrics)
        assert result[0].subject == mock_subject
        assert result[0].subscriptions_count == 0

    @patch('uudex_server.endpoints.subject_endpoints.pr.SubjectRepository')
    @pytest.mark.asyncio
    async def test_discover_subjects_admin_user(self, mock_repo, mock_admin_user):
        """Test discover subjects as admin user"""
        from uudex_server.endpoints.subject_endpoints import discover_subjects
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo_instance = Mock()
        mock_repo_instance.select_all = AsyncMock(return_value=[])
        mock_repo.return_value = mock_repo_instance
        
        # Call endpoint
        result = await discover_subjects(session=mock_session, user=mock_admin_user)
        
        # Assertions
        assert result == []
        mock_repo_instance.select_all.assert_called_once()

    @patch('uudex_server.endpoints.subject_endpoints.pr.select_all_subjects')
    @pytest.mark.asyncio
    async def test_discover_subjects_regular_user(self, mock_select_all, mock_user):
        """Test discover subjects as regular user"""
        from uudex_server.endpoints.subject_endpoints import discover_subjects
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_user.endpoint)
        
        mock_select_all.return_value = []
        
        # Call endpoint
        result = await discover_subjects(session=mock_session, user=mock_user)
        
        # Assertions
        assert result == []
        mock_select_all.assert_called_once_with(session=mock_session, participant_id=1)


# =====================================================
# VALIDATION TESTS
# =====================================================

class TestValidation:
    """Test suite for input validation"""

    def test_subject_create_validation(self):
        """Test SubjectCreate model validation"""
        # Valid creation with all required fields
        subject_create = SubjectCreate(
            subject_uuid="test-uuid",
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
        assert subject_create.subject_name == "test-subject"
        assert subject_create.subject_uuid == "test-uuid"

    def test_subject_update_validation(self):
        """Test SubjectUpdate model validation"""
        # Valid update with partial fields
        subject_update = SubjectUpdate(subject_name="updated-name")
        assert subject_update.subject_name == "updated-name"
        assert subject_update.dataset_instance_key is None

    def test_queue_management_request_validation(self):
        """Test QueueManagementRequest model validation"""
        # Valid request
        queue_request = QueueManagementRequest(action="info")
        assert queue_request.action == "info"
        assert queue_request.queue_name is None

        # Request with queue name
        queue_request_with_name = QueueManagementRequest(
            action="delete", 
            queue_name="test-queue"
        )
        assert queue_request_with_name.queue_name == "test-queue"

    def test_bulk_operation_validation(self):
        """Test BulkSubjectOperation model validation"""
        # Valid bulk operation
        bulk_op = BulkSubjectOperation(
            subject_uuids=["uuid1", "uuid2"],
            operation="delete"
        )
        assert len(bulk_op.subject_uuids) == 2
        assert bulk_op.operation == "delete"

        # Empty list should fail validation
        with pytest.raises(ValueError):
            BulkSubjectOperation(subject_uuids=[], operation="delete")