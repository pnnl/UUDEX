"""
Comprehensive tests for certificate management endpoints
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from uudex_server.main import app
from uudex_server.models import (
    EndPoint, 
    CertificateCreateRequest,
    CertificateResponse,
    BulkCertificateOperation,
    BulkCertificateResult,
    CertificateFileInfo
)
from uudex_server.models.common_types import YNSwitch
from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.models.endpoint_models import EndPoint
from uudex_server.endpoints.uudex_endpoints import extract_cn_from_dn

client = TestClient(app)


# =====================================================
# FIXTURES
# =====================================================

@pytest.fixture
def mock_admin_user():
    """Create a mock admin user for testing"""
    endpoint = EndPoint(
        endpoint_id=1,
        endpoint_uuid="admin-uuid",
        endpoint_user_name="admin",
        certificate_dn="CN=admin",
        description="Admin endpoint",
        uudex_administrator_sw="Y",
        participant_administrator_sw="N",
        participant_id=1
    )
    return AuthenticatedUser(endpoint=endpoint)


@pytest.fixture
def mock_regular_user():
    """Create a mock regular user for testing"""
    endpoint = EndPoint(
        endpoint_id=2,
        endpoint_uuid="user-uuid",
        endpoint_user_name="user",
        certificate_dn="CN=user",
        description="Regular user endpoint",
        uudex_administrator_sw="N",
        participant_administrator_sw="N",
        participant_id=1
    )
    return AuthenticatedUser(endpoint=endpoint)


@pytest.fixture
def mock_endpoint():
    """Create a mock endpoint for testing"""
    return EndPoint(
        endpoint_id=3,
        endpoint_uuid="test-endpoint-uuid",
        endpoint_user_name="test-user",
        certificate_dn="CN=test-user",
        description="Test endpoint",
        uudex_administrator_sw="N",
        participant_administrator_sw="N",
        participant_id=1
    )


@pytest.fixture
def sample_cert_request():
    """Create a sample certificate creation request"""
    return CertificateCreateRequest(
        certificate_dn="CN=alice",
        endpoint_user_name="Alice Smith",
        description="Alice's client certificate",
        participant_id=1,
        uudex_administrator_sw=YNSwitch.N,
        participant_administrator_sw=YNSwitch.N
    )


# =====================================================
# UTILITY FUNCTION TESTS
# =====================================================

class TestUtilityFunctions:
    """Test utility functions for certificate management"""
    
    def test_extract_cn_from_dn_simple(self):
        """Test CN extraction from simple DN"""
        result = extract_cn_from_dn("CN=alice")
        assert result == "alice"
    
    def test_extract_cn_from_dn_complex(self):
        """Test CN extraction from complex DN"""
        result = extract_cn_from_dn("/CN=bob/O=Organization/C=US")
        assert result == "bob"
    
    def test_extract_cn_from_dn_with_commas(self):
        """Test CN extraction from DN with commas"""
        result = extract_cn_from_dn("CN=charlie,O=Org,C=US")
        assert result == "charlie"
    
    def test_extract_cn_from_dn_no_cn(self):
        """Test CN extraction when no CN is present"""
        result = extract_cn_from_dn("O=Organization")
        assert result == "O=Organization"


# =====================================================
# CERTIFICATE CREATION TESTS
# =====================================================

class TestCertificateCreation:
    """Test certificate creation functionality"""

    @patch('uudex_server.endpoints.uudex_endpoints.generate_client_certificate')
    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_create_certificate_success(self, mock_repo_class, mock_gen_cert, mock_admin_user, sample_cert_request, mock_endpoint):
        """Test successful certificate creation"""
        from uudex_server.endpoints.uudex_endpoints import create_certificate
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_endpoint_by_certificate_dn = AsyncMock(return_value=None)  # No existing cert
        mock_repo.create_endpoint = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        # Mock certificate generation
        mock_gen_cert.return_value = (True, "Certificate generated successfully")
        
        # Call endpoint
        result = await create_certificate(
            cert_request=sample_cert_request,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, CertificateResponse)
        assert result.success is True
        assert "Certificate and endpoint created successfully" in result.message
        assert result.endpoint == mock_endpoint
        mock_gen_cert.assert_called_once()
        mock_repo.create_endpoint.assert_called_once()

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_create_certificate_non_admin_user(self, mock_repo_class, mock_regular_user, sample_cert_request):
        """Test certificate creation with non-admin user (should fail)"""
        from uudex_server.endpoints.uudex_endpoints import create_certificate
        
        mock_session = Mock(spec=AsyncSession)
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await create_certificate(
                cert_request=sample_cert_request,
                session=mock_session,
                user=mock_regular_user
            )
        
        assert exc_info.value.status_code == 403
        assert "Only UUDEX administrators can create certificates" in str(exc_info.value.detail)

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_create_certificate_duplicate_dn(self, mock_repo_class, mock_admin_user, sample_cert_request, mock_endpoint):
        """Test certificate creation with duplicate DN"""
        from uudex_server.endpoints.uudex_endpoints import create_certificate
        
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_endpoint_by_certificate_dn = AsyncMock(return_value=mock_endpoint)  # Existing cert
        mock_repo_class.return_value = mock_repo
        
        # Call endpoint
        result = await create_certificate(
            cert_request=sample_cert_request,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, CertificateResponse)
        assert result.success is False
        assert "already exists" in result.message

    @patch('uudex_server.endpoints.uudex_endpoints.generate_client_certificate')
    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_create_certificate_generation_failure(self, mock_repo_class, mock_gen_cert, mock_admin_user, sample_cert_request):
        """Test certificate creation when certificate generation fails"""
        from uudex_server.endpoints.uudex_endpoints import create_certificate
        
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_endpoint_by_certificate_dn = AsyncMock(return_value=None)  # No existing cert
        mock_repo_class.return_value = mock_repo
        
        # Mock certificate generation failure
        mock_gen_cert.return_value = (False, "Certificate generation script not found")
        
        # Call endpoint
        result = await create_certificate(
            cert_request=sample_cert_request,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, CertificateResponse)
        assert result.success is False
        assert "Failed to generate certificate" in result.message


# =====================================================
# CERTIFICATE LISTING AND RETRIEVAL TESTS
# =====================================================

class TestCertificateRetrieval:
    """Test certificate listing and retrieval functionality"""

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_list_certificates_admin(self, mock_repo_class, mock_admin_user):
        """Test listing certificates as admin user"""
        from uudex_server.endpoints.uudex_endpoints import list_certificates
        
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_all_endpoints = AsyncMock(return_value=[])
        mock_repo_class.return_value = mock_repo
        
        # Call endpoint
        result = await list_certificates(session=mock_session, user=mock_admin_user)
        
        # Assertions
        assert result == []
        mock_repo.select_all_endpoints.assert_called_once()

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_get_endpoint_by_id_success(self, mock_repo_class, mock_admin_user, mock_endpoint):
        """Test getting endpoint by ID"""
        from uudex_server.endpoints.uudex_endpoints import get_endpoint_by_id
        
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        # Call endpoint
        result = await get_endpoint_by_id(
            endpoint_id=3,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert result == mock_endpoint

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_get_endpoint_by_id_not_found(self, mock_repo_class, mock_admin_user):
        """Test getting non-existent endpoint by ID"""
        from uudex_server.endpoints.uudex_endpoints import get_endpoint_by_id
        
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=None)
        mock_repo_class.return_value = mock_repo
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await get_endpoint_by_id(
                endpoint_id=999,
                session=mock_session,
                user=mock_admin_user
            )
        
        assert exc_info.value.status_code == 404
        assert "Endpoint not found" in str(exc_info.value.detail)


# =====================================================
# CERTIFICATE UPDATE TESTS
# =====================================================

class TestCertificateUpdate:
    """Test certificate update functionality"""

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_update_certificate_success(self, mock_repo_class, mock_admin_user, mock_endpoint):
        """Test successful certificate update"""
        from uudex_server.endpoints.uudex_endpoints import update_certificate
        from uudex_server.models.endpoint_models import EndPointUpdate
        
        mock_session = Mock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        update_data = EndPointUpdate(description="Updated description")
        
        # Call endpoint
        result = await update_certificate(
            endpoint_id=3,
            endpoint_update=update_data,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, CertificateResponse)
        assert result.success is True
        assert "updated successfully" in result.message
        mock_session.commit.assert_called_once()

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_update_certificate_non_admin(self, mock_repo_class, mock_regular_user):
        """Test certificate update with non-admin user"""
        from uudex_server.endpoints.uudex_endpoints import update_certificate
        from uudex_server.models.endpoint_models import EndPointUpdate
        
        mock_session = Mock(spec=AsyncSession)
        update_data = EndPointUpdate(description="Updated description")
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await update_certificate(
                endpoint_id=3,
                endpoint_update=update_data,
                session=mock_session,
                user=mock_regular_user
            )
        
        assert exc_info.value.status_code == 403


# =====================================================
# CERTIFICATE DELETION TESTS
# =====================================================

class TestCertificateDeletion:
    """Test certificate deletion functionality"""

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_delete_certificate_success(self, mock_repo_class, mock_admin_user, mock_endpoint):
        """Test successful certificate deletion"""
        from uudex_server.endpoints.uudex_endpoints import delete_certificate
        
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo.delete = AsyncMock()
        mock_repo_class.return_value = mock_repo
        
        # Call endpoint
        result = await delete_certificate(
            endpoint_id=3,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, CertificateResponse)
        assert result.success is True
        assert "deleted successfully" in result.message
        mock_repo.delete.assert_called_once_with(mock_endpoint)


# =====================================================
# BULK OPERATIONS TESTS
# =====================================================

class TestBulkOperations:
    """Test bulk certificate operations"""

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_bulk_operations_grant_admin(self, mock_repo_class, mock_admin_user, mock_endpoint):
        """Test bulk grant admin operation"""
        from uudex_server.endpoints.uudex_endpoints import bulk_certificate_operations
        
        mock_session = Mock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        bulk_request = BulkCertificateOperation(
            endpoint_ids=[3, 4, 5],
            operation="grant_admin"
        )
        
        # Call endpoint
        result = await bulk_certificate_operations(
            bulk_request=bulk_request,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, BulkCertificateResult)
        assert len(result.successful) == 3
        assert result.total_processed == 3
        # Check that the YNSwitch was assigned properly
        from uudex_server.models.common_types import YNSwitch
        assert mock_endpoint.uudex_administrator_sw == YNSwitch.Y

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_bulk_operations_non_admin(self, mock_repo_class, mock_regular_user):
        """Test bulk operations with non-admin user"""
        from uudex_server.endpoints.uudex_endpoints import bulk_certificate_operations
        
        mock_session = Mock(spec=AsyncSession)
        
        bulk_request = BulkCertificateOperation(
            endpoint_ids=[3],
            operation="delete"
        )
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await bulk_certificate_operations(
                bulk_request=bulk_request,
                session=mock_session,
                user=mock_regular_user
            )
        
        assert exc_info.value.status_code == 403

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_bulk_operations_mixed_results(self, mock_repo_class, mock_admin_user, mock_endpoint):
        """Test bulk operations with mixed success/failure results"""
        from uudex_server.endpoints.uudex_endpoints import bulk_certificate_operations
        
        mock_session = Mock(spec=AsyncSession)
        mock_session.commit = AsyncMock()
        
        mock_repo = Mock()
        # First call returns endpoint, second call returns None (not found)
        mock_repo.select_participant_by_endpoint_id = AsyncMock(side_effect=[mock_endpoint, None])
        mock_repo_class.return_value = mock_repo
        
        bulk_request = BulkCertificateOperation(
            endpoint_ids=[3, 999],  # 3 exists, 999 doesn't
            operation="activate"
        )
        
        # Call endpoint
        result = await bulk_certificate_operations(
            bulk_request=bulk_request,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, BulkCertificateResult)
        assert len(result.successful) == 1
        assert len(result.failed) == 1
        assert result.total_processed == 2
        assert result.successful[0] == 3
        assert result.failed[0]["endpoint_id"] == 999


# =====================================================
# INTEGRATION TESTS
# =====================================================

class TestCertificateIntegration:
    """Integration tests for certificate management"""

    def test_certificate_workflow_models(self):
        """Test the complete certificate workflow using models"""
        # Test certificate creation request
        cert_request = CertificateCreateRequest(
            certificate_dn="CN=integration-test",
            endpoint_user_name="Integration Test User",
            description="Test certificate for integration testing",
            participant_id=1
        )
        assert cert_request.uudex_administrator_sw == "N"  # Default value
        
        # Test certificate response
        response = CertificateResponse(
            success=True,
            message="Certificate created successfully"
        )
        assert response.success is True
        assert isinstance(response.timestamp, datetime)
        
        # Test bulk operation
        bulk_op = BulkCertificateOperation(
            endpoint_ids=[1, 2, 3],
            operation="activate"
        )
        assert len(bulk_op.endpoint_ids) == 3
        assert bulk_op.operation == "activate"


# =====================================================
# CERTIFICATE DOWNLOAD TESTS
# =====================================================

class TestCertificateDownload:
    """Test certificate download functionality"""

    @patch('uudex_server.endpoints.uudex_endpoints.get_certificate_files')
    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_get_certificate_files_info_success(self, mock_repo_class, mock_get_files, mock_admin_user, mock_endpoint):
        """Test getting certificate files info"""
        from uudex_server.endpoints.uudex_endpoints import get_certificate_files_info
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        # Mock available files
        mock_get_files.return_value = {
            "crt": "/path/to/test-user.crt",
            "key": "/path/to/test-user.key", 
            "p12": "/path/to/test-user.p12",
            "ca": "/path/to/ca.crt"
        }
        
        # Call endpoint
        result = await get_certificate_files_info(
            endpoint_id=3,
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, CertificateFileInfo)
        assert result.endpoint_id == 3
        assert result.certificate_dn == "CN=test-user"
        assert result.client_name == "test-user"
        assert "p12" in result.available_formats
        assert "pem" in result.available_formats
        assert "crt" in result.available_formats

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_get_certificate_files_info_unauthorized(self, mock_repo_class, mock_regular_user, mock_endpoint):
        """Test getting certificate files info with unauthorized access"""
        from uudex_server.endpoints.uudex_endpoints import get_certificate_files_info
        
        # Setup mocks - different endpoint ID from user's endpoint
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_regular_user.endpoint)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        # Call endpoint should raise exception (user trying to access endpoint_id=3 but they own endpoint_id=2)
        with pytest.raises(HTTPException) as exc_info:
            await get_certificate_files_info(
                endpoint_id=3,
                session=mock_session,
                user=mock_regular_user
            )
        
        assert exc_info.value.status_code == 403
        assert "Not authorized to access this certificate" in str(exc_info.value.detail)

    @patch('uudex_server.endpoints.uudex_endpoints.get_certificate_files')
    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @patch('builtins.open', create=True)
    @pytest.mark.asyncio
    async def test_download_certificate_p12_success(self, mock_open, mock_repo_class, mock_get_files, mock_admin_user, mock_endpoint):
        """Test successful P12 certificate download"""
        from uudex_server.endpoints.uudex_endpoints import download_certificate
        from fastapi.responses import FileResponse
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        # Mock available files
        mock_get_files.return_value = {
            "p12": "/path/to/test-user.p12"
        }
        
        # Call endpoint
        result = await download_certificate(
            endpoint_id=3,
            format="p12",
            session=mock_session,
            user=mock_admin_user
        )
        
        # Assertions
        assert isinstance(result, FileResponse)
        # Note: FileResponse properties are not easily testable in unit tests
        # Integration tests would be better for full file download testing

    @patch('uudex_server.endpoints.uudex_endpoints.get_certificate_files')
    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_download_certificate_file_not_found(self, mock_repo_class, mock_get_files, mock_admin_user, mock_endpoint):
        """Test certificate download when file doesn't exist"""
        from uudex_server.endpoints.uudex_endpoints import download_certificate
        
        # Setup mocks
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        # Mock no available files
        mock_get_files.return_value = {}
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await download_certificate(
                endpoint_id=3,
                format="p12",
                session=mock_session,
                user=mock_admin_user
            )
        
        assert exc_info.value.status_code == 404
        assert "PKCS#12 certificate file not found" in str(exc_info.value.detail)

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_download_certificate_unauthorized(self, mock_repo_class, mock_regular_user, mock_endpoint):
        """Test certificate download with unauthorized access"""
        from uudex_server.endpoints.uudex_endpoints import download_certificate
        
        # Setup mocks - different endpoint ID from user's endpoint
        mock_session = Mock(spec=AsyncSession)
        mock_session.merge = AsyncMock(return_value=mock_regular_user.endpoint)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        # Call endpoint should raise exception
        with pytest.raises(HTTPException) as exc_info:
            await download_certificate(
                endpoint_id=3,
                format="p12", 
                session=mock_session,
                user=mock_regular_user
            )
        
        assert exc_info.value.status_code == 403
        assert "Not authorized to download this certificate" in str(exc_info.value.detail)

    @patch('uudex_server.endpoints.uudex_endpoints.EndpointRepository')
    @pytest.mark.asyncio
    async def test_download_certificate_invalid_format(self, mock_repo_class, mock_admin_user, mock_endpoint):
        """Test certificate download with invalid format"""
        from uudex_server.endpoints.uudex_endpoints import download_certificate
        
        mock_session = Mock(spec=AsyncSession)
        
        mock_repo = Mock()
        mock_repo.select_participant_by_endpoint_id = AsyncMock(return_value=mock_endpoint)
        mock_repo_class.return_value = mock_repo
        
        # Call endpoint should raise exception for invalid format
        with pytest.raises(HTTPException) as exc_info:
            await download_certificate(
                endpoint_id=3,
                session=mock_session,
                user=mock_admin_user,
                format="invalid"
            )
        
        assert exc_info.value.status_code == 400
        assert "Unsupported format" in str(exc_info.value.detail)


# =====================================================
# CERTIFICATE FILE UTILITIES TESTS
# =====================================================

class TestCertificateFileUtilities:
    """Test certificate file utility functions"""

    def test_get_certificate_files(self):
        """Test getting certificate files from directory"""
        from uudex_server.endpoints.uudex_endpoints import get_certificate_files
        from pathlib import Path
        
        # Create a mock certificate directory structure
        with patch('pathlib.Path.exists') as mock_exists:
            # Mock that all certificate files exist
            mock_exists.return_value = True
            
            cert_dir = Path("/mock/certs")
            files = get_certificate_files("test-user", cert_dir)
            
            # Should return all file types
            assert "crt" in files
            assert "key" in files
            assert "p12" in files
            assert "ca" in files
            assert files["crt"] == str(cert_dir / "test-user.crt")
            assert files["key"] == str(cert_dir / "test-user.key")
            assert files["p12"] == str(cert_dir / "test-user.p12")
            assert files["ca"] == str(cert_dir / "ca.crt")

    @patch('subprocess.run')
    def test_get_certificate_creation_date_success(self, mock_run):
        """Test successful certificate creation date extraction"""
        from uudex_server.endpoints.uudex_endpoints import get_certificate_creation_date
        
        # Mock successful openssl command
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "notBefore=Dec 19 10:30:00 2024 GMT\nnotAfter=Dec 19 10:30:00 2025 GMT\n"
        mock_run.return_value = mock_result
        
        result = get_certificate_creation_date("/path/to/cert.crt")
        
        # Should parse the date successfully
        assert result is not None
        assert result.year == 2024
        assert result.month == 12
        assert result.day == 19

    @patch('subprocess.run')
    def test_get_certificate_creation_date_failure(self, mock_run):
        """Test certificate creation date extraction failure"""
        from uudex_server.endpoints.uudex_endpoints import get_certificate_creation_date
        
        # Mock failed openssl command
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        
        result = get_certificate_creation_date("/path/to/cert.crt")
        
        # Should return None on failure
        assert result is None


# =====================================================
# VALIDATION TESTS
# =====================================================

class TestValidation:
    """Test input validation for certificate management"""

    def test_certificate_create_request_validation(self):
        """Test CertificateCreateRequest validation"""
        # Valid request
        valid_request = CertificateCreateRequest(
            certificate_dn="CN=valid-user",
            endpoint_user_name="Valid User",
            description="Valid certificate request",
            participant_id=1
        )
        assert valid_request.certificate_dn == "CN=valid-user"
        assert valid_request.uudex_administrator_sw == "N"

    def test_certificate_file_info_validation(self):
        """Test CertificateFileInfo validation"""
        file_info = CertificateFileInfo(
            endpoint_id=1,
            certificate_dn="CN=test-user",
            client_name="test-user",
            available_formats=["p12", "pem", "crt"],
            files={"crt": "test-user.crt", "key": "test-user.key", "p12": "test-user.p12"}
        )
        assert file_info.endpoint_id == 1
        assert len(file_info.available_formats) == 3
        assert "p12" in file_info.available_formats

    def test_bulk_operation_validation(self):
        """Test BulkCertificateOperation validation"""
        # Valid bulk operation
        bulk_op = BulkCertificateOperation(
            endpoint_ids=[1, 2, 3],
            operation="delete"
        )
        assert len(bulk_op.endpoint_ids) == 3
        
        # Empty list should fail validation
        with pytest.raises(ValueError):
            BulkCertificateOperation(endpoint_ids=[], operation="delete")