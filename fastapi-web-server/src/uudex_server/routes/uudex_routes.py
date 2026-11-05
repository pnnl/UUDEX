import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from uudex_server.core.dependencies import CurrentUserDep, SessionDep, UserDep
from uudex_server.models import (
    BulkCertificateOperation,
    BulkCertificateResult,
    CertificateCreateRequest,
    CertificateFileInfo,
    CertificateResponse,
    EndPoint,
    EndPointCreate,
    EndPointUpdate,
)
from uudex_server.models.common_types import YNSwitch
from uudex_server.repos.endpoint_repository import EndpointRepository

endpoint_router = APIRouter(prefix="/endpoint")
certificates_router = APIRouter(prefix="/certificates")

# Create v1 parent router
v1_router = APIRouter(prefix="/v1", tags=["v1"])
v1_router.include_router(endpoint_router, tags=["v1", "endpoints"])
v1_router.include_router(certificates_router, tags=["v1", "certificates"])


# =====================================================
# BASIC ENDPOINT OPERATIONS
# =====================================================


@endpoint_router.get("/me")
async def get_endpoint_user(current_user: CurrentUserDep) -> EndPoint:
    """
    Get the current authenticated user's endpoint information.
    Uses the authentication dependency to return the endpoint data.
    """
    return current_user.endpoint


@endpoint_router.get("/", operation_id="get_all_endpoints")
async def get_all_endpoints(session: SessionDep, user: UserDep) -> list[EndPoint]:
    """
    Get all endpoints based on user permissions.

    - Admin users: Can see all endpoints
    - Regular users: Can only see endpoints from their participant
    """
    repo = EndpointRepository(session)

    if user.is_admin():
        return await repo.select_all_endpoints()
    else:
        # Filter by participant - regular users can only see endpoints from their participant
        endpoint = await session.merge(user.endpoint)
        participant_id = endpoint.participant_id
        # TODO: Add participant-filtered endpoint selection to repository
        all_endpoints = await repo.select_all_endpoints()
        return [ep for ep in all_endpoints if ep.participant_id == participant_id]


@endpoint_router.get("/{endpoint_id}", operation_id="get_endpoint_by_id")
async def get_endpoint_by_id(endpoint_id: int, session: SessionDep, user: UserDep) -> EndPoint:
    """
    Get a specific endpoint by ID with authorization checks.
    """
    repo = EndpointRepository(session)
    endpoint = await repo.select_participant_by_endpoint_id(endpoint_id)

    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    # Authorization check: users can only view endpoints from their participant (unless admin)
    if not user.is_admin():
        user_endpoint = await session.merge(user.endpoint)
        if endpoint.participant_id != user_endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this endpoint"
            )

    return endpoint


@endpoint_router.post("/", operation_id="create_endpoint")
async def create_endpoint(
    endpoint_create: EndPointCreate,
    session: SessionDep,
    user: UserDep | None = Depends(lambda: None),
) -> EndPoint:
    """
    Create a new endpoint.

    Authorization rules:
    - If no endpoints exist in the system, the first endpoint automatically becomes a UUDEX administrator
    - If endpoints exist but no admins exist, the new endpoint becomes a UUDEX administrator
    - Otherwise, only UUDEX administrators can create new endpoints
    """
    repo = EndpointRepository(session)

    # Check if this is the first endpoint or if no admins exist
    endpoint_count = await repo.count_endpoints()
    has_admin = await repo.has_any_admin_endpoints()

    is_first_endpoint = endpoint_count == 0
    needs_admin = not has_admin

    # Authorization check - allow creation if:
    # 1. This is the first endpoint (bootstrap case)
    # 2. No admin exists (recovery case)
    # 3. User is an authenticated admin
    if not (is_first_endpoint or needs_admin) and (user is None or not user.is_admin()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only UUDEX administrators can create endpoints",
        )

    # Check if certificate DN already exists
    if endpoint_create.certificate_dn:
        existing_endpoint = await repo.select_endpoint_by_certificate_dn(
            endpoint_create.certificate_dn
        )
        if existing_endpoint:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Endpoint with certificate DN '{endpoint_create.certificate_dn}' already exists",
            )

    # Auto-generate UUID if not provided
    if not endpoint_create.endpoint_uuid:
        endpoint_create.endpoint_uuid = str(uuid.uuid4())

    # If this is the first endpoint or no admin exists, make it a UUDEX administrator
    if is_first_endpoint or needs_admin:
        endpoint_create.uudex_administrator_sw = "Y"
        endpoint_create.participant_administrator_sw = "Y"

    # Convert to database model and create
    db_endpoint = EndPoint(**endpoint_create.model_dump())
    created_endpoint = await repo.create_endpoint(db_endpoint)

    return created_endpoint


# =====================================================
# ADMIN CERTIFICATE MANAGEMENT
# =====================================================


def get_certs_directory() -> Path:
    """Get the certificates directory path"""
    # Check environment variable first, then default to infrastructure/caddy/certs
    certs_env = os.environ.get("UUDEX_CERTS")
    if certs_env:
        return Path(certs_env)

    # Default to infrastructure/caddy/certs relative to project root
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "infrastructure" / "caddy" / "certs"


def generate_client_certificate(client_name: str, org: str, cert_dir: Path) -> tuple[bool, str]:
    """
    Generate a client certificate using the existing CA infrastructure

    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        # Path to the certificate generation script
        script_path = cert_dir.parent / "generate-certs.sh"

        if not script_path.exists():
            return False, f"Certificate generation script not found at {script_path}"

        # Run the certificate generation script
        result = subprocess.run(
            [str(script_path), client_name, org, "--output-dir", str(cert_dir)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, f"Certificate generated successfully for {client_name}"
        else:
            return False, f"Certificate generation failed: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Certificate generation timed out"
    except Exception as e:
        return False, f"Certificate generation error: {str(e)}"


def extract_cn_from_dn(certificate_dn: str) -> str:
    """Extract the CN (Common Name) from a Distinguished Name"""
    # Handle various DN formats like "CN=alice" or "/CN=alice/O=Org"
    import re

    cn_match = re.search(r"CN=([^,/]+)", certificate_dn)
    if cn_match:
        return cn_match.group(1).strip()
    else:
        # If no CN found, use the whole DN (but clean it up)
        return certificate_dn.replace("CN=", "").replace("/", "").replace(",", "_").strip()


@certificates_router.post("/", operation_id="create_certificate")
async def create_certificate(
    cert_request: CertificateCreateRequest, session: SessionDep, user: UserDep
) -> CertificateResponse:
    """
    Create a new client certificate and register it as an endpoint.

    Only UUDEX administrators can create certificates.
    """
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only UUDEX administrators can create certificates",
        )

    repo = EndpointRepository(session)

    # Check if certificate DN already exists
    existing_endpoint = await repo.select_endpoint_by_certificate_dn(cert_request.certificate_dn)
    if existing_endpoint:
        return CertificateResponse(
            success=False,
            message=f"Certificate with DN '{cert_request.certificate_dn}' already exists",
            timestamp=datetime.utcnow(),
        )

    # Extract client name from DN for certificate generation
    client_name = extract_cn_from_dn(cert_request.certificate_dn)

    # Get certificates directory
    certs_dir = get_certs_directory()
    certs_dir.mkdir(parents=True, exist_ok=True)

    # Generate the actual certificate files
    success, message = generate_client_certificate(client_name, "UUDEX", certs_dir)

    if not success:
        return CertificateResponse(
            success=False,
            message=f"Failed to generate certificate: {message}",
            timestamp=datetime.utcnow(),
        )

    try:
        # Create endpoint record in database
        endpoint_data = EndPointCreate(
            endpoint_uuid=str(uuid.uuid4()),
            endpoint_user_name=cert_request.endpoint_user_name,
            certificate_dn=cert_request.certificate_dn,
            description=cert_request.description,
            uudex_administrator_sw=cert_request.uudex_administrator_sw,
            participant_administrator_sw=cert_request.participant_administrator_sw,
            participant_id=cert_request.participant_id,
        )

        # Convert to database model
        db_endpoint = EndPoint(**endpoint_data.model_dump())
        created_endpoint = await repo.create_endpoint(db_endpoint)

        return CertificateResponse(
            success=True,
            message=f"Certificate and endpoint created successfully for '{client_name}'",
            endpoint=created_endpoint,
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        return CertificateResponse(
            success=False,
            message=f"Database error while creating endpoint: {str(e)}",
            timestamp=datetime.utcnow(),
        )


@certificates_router.get("/", operation_id="list_certificates")
async def list_certificates(session: SessionDep, user: UserDep) -> list[EndPoint]:
    """
    List all registered certificates/endpoints.

    Admin users see all certificates, regular users see only their participant's certificates.
    """
    return await get_all_endpoints(session, user)


@certificates_router.put("/{endpoint_id}", operation_id="update_certificate")
async def update_certificate(
    endpoint_id: int, endpoint_update: EndPointUpdate, session: SessionDep, user: UserDep
) -> CertificateResponse:
    """
    Update an existing certificate/endpoint.

    Only UUDEX administrators can update certificates.
    """
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only UUDEX administrators can update certificates",
        )

    repo = EndpointRepository(session)
    existing_endpoint = await repo.select_participant_by_endpoint_id(endpoint_id)

    if existing_endpoint is None:
        return CertificateResponse(
            success=False, message="Certificate/endpoint not found", timestamp=datetime.utcnow()
        )

    try:
        # Update only provided fields
        update_data = endpoint_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing_endpoint, field, value)

        # Save changes
        await session.commit()
        await session.refresh(existing_endpoint)

        return CertificateResponse(
            success=True,
            message="Certificate/endpoint updated successfully",
            endpoint=existing_endpoint,
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        await session.rollback()
        return CertificateResponse(
            success=False,
            message=f"Failed to update certificate/endpoint: {str(e)}",
            timestamp=datetime.utcnow(),
        )


@certificates_router.delete("/{endpoint_id}", operation_id="delete_certificate")
async def delete_certificate(
    endpoint_id: int, session: SessionDep, user: UserDep
) -> CertificateResponse:
    """
    Delete a certificate/endpoint.

    Only UUDEX administrators can delete certificates.
    This removes the database record but does not delete certificate files.
    """
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only UUDEX administrators can delete certificates",
        )

    repo = EndpointRepository(session)
    existing_endpoint = await repo.select_participant_by_endpoint_id(endpoint_id)

    if existing_endpoint is None:
        return CertificateResponse(
            success=False, message="Certificate/endpoint not found", timestamp=datetime.utcnow()
        )

    try:
        # Delete from database using the endpoint object
        await repo.delete(existing_endpoint)

        return CertificateResponse(
            success=True,
            message=f"Certificate/endpoint deleted successfully (ID: {endpoint_id})",
            timestamp=datetime.utcnow(),
        )

    except Exception as e:
        return CertificateResponse(
            success=False,
            message=f"Failed to delete certificate/endpoint: {str(e)}",
            timestamp=datetime.utcnow(),
        )


# =====================================================
# CERTIFICATE DOWNLOAD
# =====================================================


def get_certificate_files(client_name: str, cert_dir: Path) -> dict[str, str]:
    """Get available certificate files for a client"""
    files = {}

    # Certificate file (.crt)
    cert_file = cert_dir / f"{client_name}.crt"
    if cert_file.exists():
        files["crt"] = str(cert_file)

    # Private key file (.key)
    key_file = cert_dir / f"{client_name}.key"
    if key_file.exists():
        files["key"] = str(key_file)

    # PKCS#12 file (.p12)
    p12_file = cert_dir / f"{client_name}.p12"
    if p12_file.exists():
        files["p12"] = str(p12_file)

    # CA certificate
    ca_file = cert_dir / "ca.crt"
    if ca_file.exists():
        files["ca"] = str(ca_file)

    return files


def get_certificate_creation_date(cert_file_path: str) -> datetime | None:
    """Get certificate creation date from the certificate file"""
    try:
        import subprocess

        result = subprocess.run(
            ["openssl", "x509", "-in", cert_file_path, "-noout", "-dates"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            # Parse the output to get the "notBefore" date
            for line in result.stdout.split("\n"):
                if line.startswith("notBefore="):
                    date_str = line.replace("notBefore=", "")
                    # Parse the date format: "Dec 19 10:30:00 2024 GMT"
                    from datetime import datetime

                    return datetime.strptime(date_str.strip(), "%b %d %H:%M:%S %Y %Z")
    except Exception:
        pass  # Return None if parsing fails

    return None


@certificates_router.get("/{endpoint_id}/files", operation_id="get_certificate_files_info")
async def get_certificate_files_info(
    endpoint_id: int, session: SessionDep, user: UserDep
) -> CertificateFileInfo:
    """
    Get information about available certificate files for an endpoint.

    Users can only access their own certificates unless they are admins.
    """
    repo = EndpointRepository(session)
    endpoint = await repo.select_participant_by_endpoint_id(endpoint_id)

    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    # Authorization check: users can only access their own certificates (unless admin)
    if not user.is_admin():
        user_endpoint = await session.merge(user.endpoint)
        if endpoint.endpoint_id != user_endpoint.endpoint_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this certificate",
            )

    # Extract client name and get certificate directory
    client_name = extract_cn_from_dn(endpoint.certificate_dn)
    certs_dir = get_certs_directory()

    # Get available files
    files = get_certificate_files(client_name, certs_dir)

    # Determine available formats
    available_formats = []
    if "p12" in files:
        available_formats.append("p12")
    if "crt" in files and "key" in files:
        available_formats.append("pem")
    if "crt" in files:
        available_formats.append("crt")

    # Get creation date
    creation_date = None
    if "crt" in files:
        creation_date = get_certificate_creation_date(files["crt"])

    return CertificateFileInfo(
        endpoint_id=endpoint.endpoint_id,
        certificate_dn=endpoint.certificate_dn,
        client_name=client_name,
        available_formats=available_formats,
        files={k: Path(v).name for k, v in files.items()},  # Return just filenames for security
        created_date=creation_date,
    )


@certificates_router.get("/{endpoint_id}/download", operation_id="download_certificate")
async def download_certificate(
    endpoint_id: int, session: SessionDep, user: UserDep, format: str = "p12"
):
    """
    Download a certificate file for authentication.

    Supported formats:
    - p12: PKCS#12 format (includes private key, password: changeme)
    - crt: Certificate only (PEM format)
    - pem: Certificate + private key in PEM format
    - ca: CA certificate for validation

    Users can only download their own certificates unless they are admins.
    """
    repo = EndpointRepository(session)
    endpoint = await repo.select_participant_by_endpoint_id(endpoint_id)

    if endpoint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    # Authorization check: users can only download their own certificates (unless admin)
    if not user.is_admin():
        user_endpoint = await session.merge(user.endpoint)
        if endpoint.endpoint_id != user_endpoint.endpoint_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to download this certificate",
            )

    # Extract client name and get certificate directory
    client_name = extract_cn_from_dn(endpoint.certificate_dn)
    certs_dir = get_certs_directory()

    # Get available files
    files = get_certificate_files(client_name, certs_dir)

    if format == "p12":
        if "p12" not in files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="PKCS#12 certificate file not found"
            )
        file_path = files["p12"]
        media_type = "application/x-pkcs12"
        filename = f"{client_name}.p12"

    elif format == "crt":
        if "crt" not in files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Certificate file not found"
            )
        file_path = files["crt"]
        media_type = "application/x-x509-ca-cert"
        filename = f"{client_name}.crt"

    elif format == "pem":
        if "crt" not in files or "key" not in files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate or private key file not found",
            )

        # For PEM format, we need to combine cert and key into a single file
        # Create a temporary combined file
        import tempfile

        try:
            # Read certificate and key files
            with open(files["crt"]) as cert_file:
                cert_content = cert_file.read()

            with open(files["key"]) as key_file:
                key_content = key_file.read()

            # Create temporary combined file
            combined_content = cert_content + "\n" + key_content

            # Write to a temporary file that will be cleaned up automatically
            temp_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".pem", delete=False)
            temp_file.write(combined_content)
            temp_file.close()

            file_path = temp_file.name
            media_type = "application/x-pem-file"
            filename = f"{client_name}.pem"

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create PEM file: {str(e)}",
            )

    elif format == "ca":
        if "ca" not in files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="CA certificate file not found"
            )
        file_path = files["ca"]
        media_type = "application/x-x509-ca-cert"
        filename = "ca.crt"

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Use: p12, crt, pem, or ca",
        )

    # Return the file
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@certificates_router.post("/bulk-operations", operation_id="bulk_certificate_operations")
async def bulk_certificate_operations(
    bulk_request: BulkCertificateOperation, session: SessionDep, user: UserDep
) -> BulkCertificateResult:
    """
    Perform bulk operations on multiple certificates/endpoints.

    Supported operations:
    - activate: Set active_sw to 'Y'
    - deactivate: Set active_sw to 'N'
    - delete: Remove from database
    - grant_admin: Set uudex_administrator_sw to 'Y'
    - revoke_admin: Set uudex_administrator_sw to 'N'
    """
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only UUDEX administrators can perform bulk certificate operations",
        )

    repo = EndpointRepository(session)
    successful = []
    failed = []

    for endpoint_id in bulk_request.endpoint_ids:
        try:
            endpoint = await repo.select_participant_by_endpoint_id(endpoint_id)
            if endpoint is None:
                failed.append({"endpoint_id": endpoint_id, "error": "Endpoint not found"})
                continue

            if bulk_request.operation == "activate":
                endpoint.active_sw = YNSwitch.Y
                await session.commit()
                successful.append(endpoint_id)

            elif bulk_request.operation == "deactivate":
                endpoint.active_sw = YNSwitch.N
                await session.commit()
                successful.append(endpoint_id)

            elif bulk_request.operation == "delete":
                await repo.delete(endpoint)
                successful.append(endpoint_id)

            elif bulk_request.operation == "grant_admin":
                endpoint.uudex_administrator_sw = YNSwitch.Y
                await session.commit()
                successful.append(endpoint_id)

            elif bulk_request.operation == "revoke_admin":
                endpoint.uudex_administrator_sw = YNSwitch.N
                await session.commit()
                successful.append(endpoint_id)

            else:
                failed.append(
                    {
                        "endpoint_id": endpoint_id,
                        "error": f"Unsupported operation: {bulk_request.operation}",
                    }
                )

        except Exception as e:
            failed.append({"endpoint_id": endpoint_id, "error": str(e)})

    return BulkCertificateResult(
        successful=successful,
        failed=failed,
        total_processed=len(bulk_request.endpoint_ids),
        timestamp=datetime.utcnow(),
    )
