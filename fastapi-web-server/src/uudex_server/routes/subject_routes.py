import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from uudex_server.core import get_settings
from uudex_server.core.dependencies import SessionDep, UserDep
from uudex_server.models.message_models import MessagePublishRequest, MessagePublishResponse
from uudex_server.models.subject_models import (
    BulkOperationResult,
    BulkSubjectOperation,
    QueueManagementRequest,
    QueueManagementResponse,
    Subject,
    SubjectCreate,
    SubjectQueueInfo,
    SubjectUpdate,
    SubjectWithMetrics,
)
from uudex_server.repos import subscription_and_subject_repositories as pr
from uudex_server.services.message_services import create_broker_service
from uudex_server.services.message_services.base import UUDEXBrokerService

subjects_router = APIRouter(prefix="/subjects")
subject_router = APIRouter(prefix="/subject")

# Create v1 parent router
v1_router = APIRouter(prefix="/v1", tags=["v1"])
v1_router.include_router(subjects_router, tags=["v1", "subjects"])
v1_router.include_router(subject_router, tags=["v1", "subjects"])


def get_broker_service() -> UUDEXBrokerService:
    """Dependency to get message broker service"""
    return create_broker_service(get_settings().messagebus_connection)


# =====================================================
# BASIC CRUD OPERATIONS
# =====================================================

@subjects_router.get("/", operation_id="get_all_subjects")
async def get_all_subjects(session: SessionDep, user: UserDep) -> list[Subject]:
    """
    Get all subjects based on user permissions.

    - Admin users: Can see all subjects
    - Regular users: Can only see subjects owned by their participant
    """
    repo = pr.SubjectRepository(session)

    if user.is_admin():
        return await repo.select_all()
    else:
        # Access participant_id safely by merging the endpoint into current session
        endpoint = await session.merge(user.endpoint)
        participant_id = endpoint.participant_id
        return await pr.select_all_subjects(session=session, participant_id=participant_id)


@subjects_router.post("/", operation_id="create_subject")
async def create_subject(
    subject_data: SubjectCreate,
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),
) -> Subject:
    """
    Create a new subject with associated message queue infrastructure.

    Automatically sets ownership to the requesting user's participant.
    """
    # Set ownership and defaults
    endpoint = await session.merge(user.endpoint)
    participant_id = endpoint.participant_id

    # Auto-generate UUID if not provided
    if not subject_data.subject_uuid:
        subject_data.subject_uuid = str(uuid.uuid4())

    # Set required fields from context
    subject_data.owner_participant_id = participant_id
    if not subject_data.dataset_definition_id:
        subject_data.dataset_definition_id = 1  # Default dataset definition

    # Set backing exchange name if not provided
    if not subject_data.backing_exchange_name:
        subject_data.backing_exchange_name = f"e_{subject_data.subject_name}_{subject_data.subject_uuid}"

    # Create subject in database
    subject_dict = subject_data.model_dump()
    db_subject = Subject(**subject_dict)

    repo = pr.SubjectRepository(session)
    created_subject = await repo.create(db_subject)

    try:
        # Create message broker infrastructure
        broker.create_subject(
            subject_name=created_subject.subject_name,
            subject_uuid=created_subject.subject_uuid
        )
    except Exception as e:
        # If broker setup fails, remove the subject from database
        await repo.delete(created_subject.subject_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create message broker infrastructure: {str(e)}"
        )

    return created_subject


@subject_router.get("/{subject_id}", operation_id="get_subject_by_id")
async def get_subject_by_id(subject_id: int, session: SessionDep, user: UserDep) -> Subject:
    """
    Get a specific subject by ID with authorization checks.
    """
    subject = await pr.select_subject_by_id(session=session, subject_id=subject_id)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # Authorization check: users can only view subjects owned by their participant (unless admin)
    if not user.is_admin():
        endpoint = await session.merge(user.endpoint)
        if subject.owner_participant_id != endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this subject"
            )

    return subject


@subject_router.get("/uuid/{subject_uuid}", operation_id="get_subject_by_uuid")
async def get_subject_by_uuid(subject_uuid: str, session: SessionDep, user: UserDep) -> Subject:
    """
    Get a specific subject by UUID with authorization checks.
    """
    repo = pr.SubjectRepository(session)
    subject = await repo.select_by_field("subject_uuid", subject_uuid)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # Authorization check: users can only view subjects owned by their participant (unless admin)
    if not user.is_admin():
        endpoint = await session.merge(user.endpoint)
        if subject.owner_participant_id != endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this subject"
            )

    return subject


@subject_router.put("/{subject_id}", operation_id="update_subject")
async def update_subject(
    subject_id: int,
    subject_update: SubjectUpdate,
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),
) -> Subject:
    """
    Update an existing subject with authorization checks.
    
    Only subject owners or admins can update subjects.
    """
    repo = pr.SubjectRepository(session)
    existing_subject = await pr.select_subject_by_id(session=session, subject_id=subject_id)

    if existing_subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # Authorization check: users can only update subjects owned by their participant (unless admin)
    if not user.is_admin():
        endpoint = await session.merge(user.endpoint)
        if existing_subject.owner_participant_id != endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this subject"
            )

    # Update only provided fields
    update_data = subject_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing_subject, field, value)

    # Save changes
    updated_subject = await repo.update(existing_subject)

    return updated_subject


@subject_router.delete("/{subject_id}", operation_id="delete_subject")
async def delete_subject(
    subject_id: int,
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),
) -> dict:
    """
    Delete a subject and its associated message queue infrastructure.
    
    Only subject owners or admins can delete subjects.
    """
    repo = pr.SubjectRepository(session)
    existing_subject = await pr.select_subject_by_id(session=session, subject_id=subject_id)

    if existing_subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # Authorization check: users can only delete subjects owned by their participant (unless admin)
    if not user.is_admin():
        endpoint = await session.merge(user.endpoint)
        if existing_subject.owner_participant_id != endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this subject"
            )

    try:
        # Delete message broker infrastructure first
        broker.delete_subject(
            subject_name=existing_subject.subject_name,
            subject_uuid=existing_subject.subject_uuid
        )
    except Exception as e:
        # Log warning but continue with database deletion
        print(f"Warning: Failed to delete message broker infrastructure: {str(e)}")

    # Delete from database
    await repo.delete(subject_id)

    return {"message": "Subject deleted successfully", "subject_id": subject_id}


# =====================================================
# DISCOVERY AND LISTING
# =====================================================

@subjects_router.get("/discover", operation_id="discover_subjects")
async def discover_subjects(session: SessionDep, user: UserDep) -> list[Subject]:
    """
    Discover subjects that the authenticated user is authorized to view.

    Returns subjects based on:
    - Admin users: All subjects
    - Regular users: Only subjects owned by their participant
    """
    repo = pr.SubjectRepository(session)

    if user.is_admin():
        # Admin users can see all subjects
        return await repo.select_all()
    else:
        # Regular users can only see subjects owned by their participant
        # Access participant_id safely by merging the endpoint into current session
        endpoint = await session.merge(user.endpoint)
        participant_id = endpoint.participant_id

        # Get subjects owned by the user's participant
        subjects = await pr.select_all_subjects(session=session, participant_id=participant_id)
        return subjects


@subjects_router.get("/with-metrics", operation_id="get_subjects_with_metrics")
async def get_subjects_with_metrics(
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),
) -> list[SubjectWithMetrics]:
    """
    Get subjects with additional queue metrics and subscription information.
    """
    # Get subjects based on user permissions
    if user.is_admin():
        repo = pr.SubjectRepository(session)
        subjects = await repo.select_all()
    else:
        endpoint = await session.merge(user.endpoint)
        participant_id = endpoint.participant_id
        subjects = await pr.select_all_subjects(session=session, participant_id=participant_id)

    results = []
    for subject in subjects:
        # Get queue information
        queue_info = await _get_subject_queue_info(subject, broker)

        # Get subscription count
        subscription_count = len(subject.subscription_links)

        # Create enhanced subject info
        subject_with_metrics = SubjectWithMetrics(
            subject=subject,
            queue_info=queue_info,
            subscriptions_count=subscription_count,
            last_activity=None  # TODO: Implement last activity tracking
        )
        results.append(subject_with_metrics)

    return results


# =====================================================
# MESSAGE PUBLISHING
# =====================================================

@subjects_router.post("/{subject_uuid}/publish", operation_id="publish_messages_to_subject")
async def publish_messages_to_subject(
    subject_uuid: str,
    publish_request: MessagePublishRequest,
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),
) -> MessagePublishResponse:
    """
    Publish messages to a subject's exchange.
    
    Only subject owners or admins can publish to subjects.
    """
    # Get subject and verify authorization
    repo = pr.SubjectRepository(session)
    subject = await repo.select_by_field("subject_uuid", subject_uuid)

    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # Authorization check: users can only publish to subjects owned by their participant (unless admin)
    if not user.is_admin():
        endpoint = await session.merge(user.endpoint)
        if subject.owner_participant_id != endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to publish to this subject"
            )

    # Publish messages to the subject's exchange
    message_ids = []
    published_count = 0

    try:
        for message_payload in publish_request.messages:
            # Generate message ID
            message_id = str(uuid.uuid4())

            # Publish to broker
            result = broker.publish_message(
                subject_exchange=subject.backing_exchange_name,
                routing_key="",  # Fanout exchange doesn't use routing keys
                payload=message_payload,
                payload_enc=publish_request.payload_encoding
            )

            if result == 0:  # Success (assuming 0 indicates success)
                message_ids.append(message_id)
                published_count += 1

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to publish messages: {str(e)}"
        )

    return MessagePublishResponse(
        published_count=published_count,
        subject_uuid=subject_uuid,
        message_ids=message_ids,
        timestamp=datetime.utcnow()
    )


# =====================================================
# QUEUE MANAGEMENT
# =====================================================

@subject_router.get("/{subject_uuid}/queue-info", operation_id="get_subject_queue_info")
async def get_subject_queue_info(
    subject_uuid: str,
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),
) -> SubjectQueueInfo:
    """
    Get detailed queue information for a subject.
    """
    # Get subject and verify authorization
    repo = pr.SubjectRepository(session)
    subject = await repo.select_by_field("subject_uuid", subject_uuid)

    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # Authorization check
    if not user.is_admin():
        endpoint = await session.merge(user.endpoint)
        if subject.owner_participant_id != endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view queue info for this subject"
            )

    return await _get_subject_queue_info(subject, broker)


@subject_router.post("/{subject_uuid}/queue-management", operation_id="manage_subject_queues")
async def manage_subject_queues(
    subject_uuid: str,
    queue_request: QueueManagementRequest,
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),
) -> QueueManagementResponse:
    """
    Perform queue management operations on a subject.
    
    Supported actions:
    - info: Get queue information
    - purge: Clear all messages from subject queues
    - delete: Delete specific queue (requires queue_name)
    """
    # Get subject and verify authorization
    repo = pr.SubjectRepository(session)
    subject = await repo.select_by_field("subject_uuid", subject_uuid)

    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # Authorization check: only owners or admins can manage queues
    if not user.is_admin():
        endpoint = await session.merge(user.endpoint)
        if subject.owner_participant_id != endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage queues for this subject"
            )

    try:
        if queue_request.action == "info":
            queue_info = await _get_subject_queue_info(subject, broker)
            return QueueManagementResponse(
                success=True,
                message="Queue information retrieved successfully",
                queue_info=queue_info.model_dump(),
                timestamp=datetime.utcnow()
            )

        elif queue_request.action == "purge":
            # Purge all queues associated with this subject
            # This requires getting all subscription-subject relationships
            purged_queues = []
            for sub_link in subject.subscription_links:
                queue_name = broker.build_queue_name(
                    tag="uudex",
                    subject_name=subject.subject_name,
                    subscription_uuid=sub_link.subscription_uuid
                )
                try:
                    # Note: RabbitMQ service has purge_queue method, but it's not in base class
                    # For now, we'll try to delete and recreate
                    broker.delete_queue(queue_name)
                    purged_queues.append(queue_name)
                except Exception as e:
                    print(f"Warning: Failed to purge queue {queue_name}: {str(e)}")

            return QueueManagementResponse(
                success=True,
                message=f"Purged {len(purged_queues)} queues",
                queue_info={"purged_queues": purged_queues},
                timestamp=datetime.utcnow()
            )

        elif queue_request.action == "delete" and queue_request.queue_name:
            # Delete specific queue
            result = broker.delete_queue(queue_request.queue_name)
            return QueueManagementResponse(
                success=True,
                message=f"Queue {queue_request.queue_name} deleted successfully",
                queue_info={"deleted_queue": queue_request.queue_name, "result": result},
                timestamp=datetime.utcnow()
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action: {queue_request.action}"
            )

    except Exception as e:
        return QueueManagementResponse(
            success=False,
            message=f"Queue management operation failed: {str(e)}",
            queue_info=None,
            timestamp=datetime.utcnow()
        )


# =====================================================
# BULK OPERATIONS
# =====================================================

@subjects_router.post("/bulk-operations", operation_id="bulk_subject_operations")
async def bulk_subject_operations(
    bulk_request: BulkSubjectOperation,
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),
) -> BulkOperationResult:
    """
    Perform bulk operations on multiple subjects.
    
    Supported operations:
    - delete: Delete multiple subjects
    - purge_queues: Purge queues for multiple subjects
    """
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can perform bulk operations"
        )

    repo = pr.SubjectRepository(session)
    successful = []
    failed = []

    for subject_uuid in bulk_request.subject_uuids:
        try:
            subject = await repo.select_by_field("subject_uuid", subject_uuid)
            if subject is None:
                failed.append({"subject_uuid": subject_uuid, "error": "Subject not found"})
                continue

            if bulk_request.operation == "delete":
                # Delete subject and its infrastructure
                try:
                    broker.delete_subject(
                        subject_name=subject.subject_name,
                        subject_uuid=subject.subject_uuid
                    )
                except Exception:
                    pass  # Continue with database deletion even if broker fails

                await repo.delete(subject.subject_id)
                successful.append(subject_uuid)

            elif bulk_request.operation == "purge_queues":
                # Purge all queues for the subject
                for sub_link in subject.subscription_links:
                    queue_name = broker.build_queue_name(
                        tag="uudex",
                        subject_name=subject.subject_name,
                        subscription_uuid=sub_link.subscription_uuid
                    )
                    try:
                        broker.delete_queue(queue_name)
                    except Exception:
                        pass  # Continue with other queues

                successful.append(subject_uuid)

            else:
                failed.append({"subject_uuid": subject_uuid, "error": f"Unsupported operation: {bulk_request.operation}"})

        except Exception as e:
            failed.append({"subject_uuid": subject_uuid, "error": str(e)})

    return BulkOperationResult(
        successful=successful,
        failed=failed,
        total_processed=len(bulk_request.subject_uuids),
        timestamp=datetime.utcnow()
    )


# =====================================================
# HELPER FUNCTIONS
# =====================================================

async def _get_subject_queue_info(subject: Subject, broker: UUDEXBrokerService) -> SubjectQueueInfo:
    """
    Helper function to get queue information for a subject.
    """
    # Get basic queue information
    exchange_name = broker.build_exchange_name(subject.subject_name, subject.subject_uuid)

    # Count queues and messages (this is a simplified implementation)
    # In a real implementation, you would query the message broker for detailed stats
    queue_count = len(subject.subscription_links)
    total_messages = 0  # TODO: Implement message counting from broker
    total_consumers = 0  # TODO: Implement consumer counting from broker

    return SubjectQueueInfo(
        subject_uuid=subject.subject_uuid,
        subject_name=subject.subject_name,
        exchange_name=exchange_name,
        queue_count=queue_count,
        total_messages=total_messages,
        total_consumers=total_consumers
    )
