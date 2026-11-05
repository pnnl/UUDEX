import base64
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from uudex_server.core.dependencies import get_current_user
from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.models.dataset_models import Dataset, DatasetCreate, DatasetRead
from uudex_server.models.subject_models import Subject
from uudex_server.repos import subscription_and_subject_repositories as pr
from uudex_server.repos.dataset_repositories import DatasetRepository
from uudex_server.services.database_service import get_db

_log = logging.getLogger(__name__)

# Create v1 routers
subjects_router = APIRouter(prefix="/subjects")
subject_router = APIRouter(prefix="/subject")
datasets_router = APIRouter(prefix="/datasets")
dataset_router = APIRouter(prefix="/dataset")

# Create v1 parent router
v1_router = APIRouter(prefix="/v1", tags=["v1"])
v1_router.include_router(subjects_router, tags=["v1", "subjects"])
v1_router.include_router(subject_router, tags=["v1", "subjects"])
v1_router.include_router(datasets_router, tags=["v1", "datasets"])
v1_router.include_router(dataset_router, tags=["v1", "datasets"])


@subjects_router.get("/")
async def get_all_subjects(session: Annotated[AsyncSession, Depends(get_db)]) -> list[Subject]:
    subjects: list[Subject] = await pr.select_all_subjects(session=session)
    return subjects


@subject_router.get("/{subject_id}")
async def get_subject_by_id(
    subject_id: int, session: Annotated[AsyncSession, Depends(get_db)]
) -> Subject:
    subject: Subject | None = await pr.select_subject_by_id(session=session, subject_id=subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@datasets_router.post("/", operation_id="create_dataset")
async def create_dataset(
    dataset: DatasetCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DatasetRead:
    """
    Create a new dataset.

    The dataset will be owned by the authenticated user's participant.
    Returns metadata only, use download endpoint for payload.
    """
    # Set the owner to the authenticated user's participant
    # Access the participant_id safely to avoid SQLAlchemy DetachedInstanceError
    try:
        # Merge the endpoint object into the current session to avoid detachment issues
        endpoint = await session.merge(user.endpoint)
        participant_id = endpoint.participant_id
    except Exception as e:
        # If we can't access participant_id due to session issues,
        # we need to handle this more gracefully
        _log.error(f"Error accessing participant_id: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")

    dataset.owner_participant_id = participant_id

    # Verify the subject exists and the user has access to it
    subject = await pr.select_subject_by_id(session=session, subject_id=dataset.subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Convert DatasetCreate to Dataset instance
    # Handle payload conversion from string (base64) to bytes
    dataset_dict = dataset.model_dump()

    # Convert base64 string payload to bytes for database storage
    if dataset_dict.get("payload"):
        try:
            dataset_dict["payload"] = base64.b64decode(dataset_dict["payload"])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 payload: {str(e)}")

    # Set the create_datetime explicitly since server default might not work
    dataset_dict["create_datetime"] = datetime.utcnow()

    dataset_instance = Dataset(**dataset_dict)

    # Create the dataset using the repository
    repo = DatasetRepository(session)
    created_dataset = await repo.create(dataset_instance)

    # Return DatasetRead (metadata only, no payload)
    return DatasetRead(
        dataset_id=created_dataset.dataset_id,
        dataset_uuid=created_dataset.dataset_uuid,
        dataset_name=created_dataset.dataset_name,
        description=created_dataset.description,
        properties=created_dataset.properties,
        payload_size=created_dataset.payload_size,
        payload_md5_hash=created_dataset.payload_md5_hash,
        payload_compression_algorithm=created_dataset.payload_compression_algorithm,
        version_number=created_dataset.version_number,
        owner_participant_id=created_dataset.owner_participant_id,
        subject_id=created_dataset.subject_id,
        create_datetime=created_dataset.create_datetime,
    )


@datasets_router.get("/")
async def get_all_datasets(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> list[DatasetRead]:
    """
    Get all datasets owned by the authenticated user's participant.
    Returns metadata only, use download endpoint for payload.
    """
    try:
        # Merge the endpoint object into the current session to avoid detachment issues
        endpoint = await session.merge(user.endpoint)
        participant_id = endpoint.participant_id
    except Exception as e:
        _log.error(f"Error accessing participant_id in get_all_datasets: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")

    repo = DatasetRepository(session)
    datasets = await repo.select_datasets_by_participant(
        session=session, participant_id=participant_id
    )

    # Convert to DatasetRead (metadata only, no payload)
    return [
        DatasetRead(
            dataset_id=dataset.dataset_id,
            dataset_uuid=dataset.dataset_uuid,
            dataset_name=dataset.dataset_name,
            description=dataset.description,
            properties=dataset.properties,
            payload_size=dataset.payload_size,
            payload_md5_hash=dataset.payload_md5_hash,
            payload_compression_algorithm=dataset.payload_compression_algorithm,
            version_number=dataset.version_number,
            owner_participant_id=dataset.owner_participant_id,
            subject_id=dataset.subject_id,
            create_datetime=dataset.create_datetime,
        )
        for dataset in datasets
    ]


@dataset_router.get("/{dataset_id}")
async def get_dataset_by_id(
    dataset_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> DatasetRead:
    """
    Get a specific dataset by ID.
    Returns metadata only, use download endpoint for payload.
    Only returns datasets owned by the authenticated user's participant.
    """
    try:
        # Merge the endpoint object into the current session to avoid detachment issues
        endpoint = await session.merge(user.endpoint)
        participant_id = endpoint.participant_id
    except Exception as e:
        _log.error(f"Error accessing participant_id in get_dataset_by_id: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")

    repo = DatasetRepository(session)
    dataset = await repo.select_by_id(dataset_id)

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Check if the user owns this dataset
    if dataset.owner_participant_id != participant_id:
        raise HTTPException(status_code=403, detail="Access denied to this dataset")

    # Return DatasetRead (metadata only, no payload)
    return DatasetRead(
        dataset_id=dataset.dataset_id,
        dataset_uuid=dataset.dataset_uuid,
        dataset_name=dataset.dataset_name,
        description=dataset.description,
        properties=dataset.properties,
        payload_size=dataset.payload_size,
        payload_md5_hash=dataset.payload_md5_hash,
        payload_compression_algorithm=dataset.payload_compression_algorithm,
        version_number=dataset.version_number,
        owner_participant_id=dataset.owner_participant_id,
        subject_id=dataset.subject_id,
        create_datetime=dataset.create_datetime,
    )


@dataset_router.get("/{dataset_id}/download")
async def download_dataset(
    dataset_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> Response:
    """
    Download the dataset payload as binary data.
    Only allows downloads for datasets owned by the authenticated user's participant.
    """
    try:
        # Merge the endpoint object into the current session to avoid detachment issues
        endpoint = await session.merge(user.endpoint)
        participant_id = endpoint.participant_id
    except Exception as e:
        _log.error(f"Error accessing participant_id in download_dataset: {e}")
        raise HTTPException(status_code=500, detail="Authentication error")

    repo = DatasetRepository(session)
    dataset = await repo.select_by_id(dataset_id)

    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Check if the user owns this dataset
    if dataset.owner_participant_id != participant_id:
        raise HTTPException(status_code=403, detail="Access denied to this dataset")

    # Return the payload as binary data
    return Response(
        content=dataset.payload,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=dataset_{dataset_id}_payload",
            "Content-MD5": dataset.payload_md5_hash,
            "X-Compression-Algorithm": dataset.payload_compression_algorithm,
        },
    )
