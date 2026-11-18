import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
from uudex_server.services.message_services.base import (
    BrokerError,
    UntrustedBrokerName,
    UUDEXBrokerService,
    exchange_name,
    trusted_exchange_name,
)

_log = logging.getLogger(__name__)

subjects_router = APIRouter(prefix="/subjects")
subject_router = APIRouter(prefix="/subject")


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

    # The server owns the uuid: a client-chosen one could alias another subject's exchange.
    subject_data.subject_uuid = str(uuid.uuid4())

    # Set required fields from context
    subject_data.owner_participant_id = participant_id
    if not subject_data.dataset_definition_id:
        subject_data.dataset_definition_id = 1  # Default dataset definition

    # Minted once here and stored; publish and delete read it back from the row.
    subject_data.backing_exchange_name = exchange_name(subject_data.subject_uuid)

    # Create subject in database
    subject_dict = subject_data.model_dump()
    db_subject = Subject(**subject_dict)

    repo = pr.SubjectRepository(session)
    created_subject = await repo.create(db_subject)

    try:
        # Create message broker infrastructure
        broker.create_exchange(created_subject.backing_exchange_name)
    except Exception as e:
        # Any failure, not only BrokerError, must remove the row: otherwise it is left with no
        # exchange behind it.
        _log.exception("Broker create_exchange failed for subject %s", created_subject.subject_uuid)
        try:
            await repo.delete(created_subject)
        except Exception:
            # The caller must still see the original failure, not the rollback's.
            _log.exception("Rollback of subject %s failed", created_subject.subject_uuid)
        if isinstance(e, BrokerError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create message broker infrastructure",
            ) from e
        raise

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
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this subject"
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
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this subject"
            )

    return subject


@subject_router.put("/{subject_id}", operation_id="update_subject")
async def update_subject(
    subject_id: int,
    subject_update: SubjectUpdate,
    session: SessionDep,
    user: UserDep,
    broker: UUDEXBrokerService = Depends(get_broker_service),  # noqa: ARG001  (dependency kept)
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
                detail="Not authorized to update this subject",
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
                detail="Not authorized to delete this subject",
            )

    # The row goes first, uncommitted: a subject still linked to a subscription fails here,
    # before the exchange is touched.
    # A rollback expires the loaded row, so read what the handlers below need first.
    subject_uuid = existing_subject.subject_uuid
    exchange = _exchange_to_delete(existing_subject)
    try:
        await repo.delete(existing_subject, commit=False)
    except IntegrityError as e:
        await session.rollback()
        _log.warning("Subject %s not deleted: still linked", subject_uuid)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Subject is still linked to a subscription",
        ) from e

    try:
        if exchange is not None:
            broker.delete_exchange(exchange)
    except BrokerError as e:
        # Roll the row back so the subject stays visible and the delete can be retried instead
        # of orphaning the exchange. 500 matches create_subject and publish.
        await session.rollback()
        _log.exception("Broker delete_exchange failed for subject %s", subject_uuid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message broker infrastructure",
        ) from e

    await session.commit()

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
            last_activity=None,  # TODO: Implement last activity tracking
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
                detail="Not authorized to publish to this subject",
            )

    exchange = _trusted_exchange_or_409(subject)

    # Publish messages to the subject's exchange
    message_ids = []
    published_count = 0

    try:
        for message_payload in publish_request.messages:
            # Generate message ID
            message_id = str(uuid.uuid4())

            # Publish to broker
            result = broker.publish_message(
                subject_exchange=exchange,
                routing_key="",  # Fanout exchange doesn't use routing keys
                payload=message_payload,
                payload_enc=publish_request.payload_encoding,
            )

            if result == 0:  # Success (assuming 0 indicates success)
                message_ids.append(message_id)
                published_count += 1

    except BrokerError:
        _log.exception("Broker publish failed for subject %s", subject_uuid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish messages",
        )

    return MessagePublishResponse(
        published_count=published_count,
        subject_uuid=subject_uuid,
        message_ids=message_ids,
        timestamp=datetime.utcnow(),
    )


# =====================================================
# QUEUE MANAGEMENT
# =====================================================


@subject_router.get("/{subject_uuid}/queue-info", operation_id="get_subject_queue_info")
async def get_subject_queue_info(
    subject_uuid: str, session: SessionDep, user: UserDep
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
                detail="Not authorized to view queue info for this subject",
            )

    return await _get_subject_queue_info(subject, _trusted_exchange_or_409(subject))


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
    subject = await repo.select_by_uuid_with_links(subject_uuid)

    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")

    # Authorization check: only owners or admins can manage queues
    if not user.is_admin():
        endpoint = await session.merge(user.endpoint)
        if subject.owner_participant_id != endpoint.participant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage queues for this subject",
            )

    # Outside the try below, which turns every exception into a 200 with success False.
    info_exchange = _trusted_exchange_or_409(subject) if queue_request.action == "info" else ""

    if queue_request.action == "delete" and queue_request.queue_name:
        await _require_owned_queue(session, subject, queue_request.queue_name)

    try:
        if queue_request.action == "info":
            queue_info = await _get_subject_queue_info(subject, info_exchange)
            return QueueManagementResponse(
                success=True,
                message="Queue information retrieved successfully",
                queue_info=queue_info.model_dump(),
                timestamp=datetime.utcnow(),
            )

        elif queue_request.action == "purge":
            # Purge all queues associated with this subject
            # This requires getting all subscription-subject relationships
            purged_queues = []
            failed_queues = []
            shared = await _queues_shared_with_other_subjects(session, subject)
            for sub_link in subject.subscription_links:
                queue_name = sub_link.backing_queue_name
                if queue_name in shared:
                    failed_queues.append(queue_name)
                    continue
                try:
                    # Note: RabbitMQ service has purge_queue method, but it's not in base class
                    # For now, we'll try to delete and recreate
                    broker.delete_queue(queue_name)
                    purged_queues.append(queue_name)
                except BrokerError:
                    _log.exception("Broker failed to purge queue %s", queue_name)
                    failed_queues.append(queue_name)

            if failed_queues:
                return QueueManagementResponse(
                    success=False,
                    message=(
                        f"Purged {len(purged_queues)} queues; "
                        f"failed to purge: {', '.join(failed_queues)}"
                        f"{_shared_reason(shared)}"
                    ),
                    queue_info={"purged_queues": purged_queues, "failed_queues": failed_queues},
                    timestamp=datetime.utcnow(),
                )

            return QueueManagementResponse(
                success=True,
                message=f"Purged {len(purged_queues)} queues",
                queue_info={"purged_queues": purged_queues},
                timestamp=datetime.utcnow(),
            )

        elif queue_request.action == "delete" and queue_request.queue_name:
            # Delete specific queue
            result = broker.delete_queue(queue_request.queue_name)
            return QueueManagementResponse(
                success=True,
                message=f"Queue {queue_request.queue_name} deleted successfully",
                queue_info={"deleted_queue": queue_request.queue_name, "result": result},
                timestamp=datetime.utcnow(),
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action: {queue_request.action}",
            )

    except HTTPException:
        raise
    except Exception:
        # Wraps repository and model code as well as the broker, so it cannot name BrokerError.
        _log.exception("Queue management action %s failed", queue_request.action)
        return QueueManagementResponse(
            success=False,
            message="Queue management operation failed",
            queue_info=None,
            timestamp=datetime.utcnow(),
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
            detail="Only administrators can perform bulk operations",
        )

    repo = pr.SubjectRepository(session)
    successful = []
    failed = []

    for subject_uuid in bulk_request.subject_uuids:
        try:
            subject = await repo.select_by_uuid_with_links(subject_uuid)
            if subject is None:
                failed.append({"subject_uuid": subject_uuid, "error": "Subject not found"})
                continue

            if bulk_request.operation == "delete":
                exchange = _exchange_to_delete(subject)
                # Row first, uncommitted, as in the single delete: a linked subject fails
                # before the exchange is touched, and a broker failure rolls the row back.
                try:
                    await repo.delete(subject, commit=False)
                except IntegrityError:
                    await session.rollback()
                    _log.warning("Subject %s not deleted: still linked", subject_uuid)
                    failed.append(
                        {
                            "subject_uuid": subject_uuid,
                            "error": "Subject is still linked to a subscription",
                        }
                    )
                    continue

                try:
                    if exchange is not None:
                        broker.delete_exchange(exchange)
                except BrokerError:
                    await session.rollback()
                    _log.exception("Broker delete_exchange failed for subject %s", subject_uuid)
                    failed.append({"subject_uuid": subject_uuid, "error": "Broker delete failed"})
                    continue

                await session.commit()
                successful.append(subject_uuid)

            elif bulk_request.operation == "purge_queues":
                # Purge all queues for the subject
                failed_queues = []
                shared = await _queues_shared_with_other_subjects(session, subject)
                for sub_link in subject.subscription_links:
                    queue_name = sub_link.backing_queue_name
                    if queue_name in shared:
                        failed_queues.append(queue_name)
                        continue
                    # Continue with other queues
                    try:
                        broker.delete_queue(queue_name)
                    except BrokerError:
                        _log.exception("Broker failed to purge queue %s", queue_name)
                        failed_queues.append(queue_name)

                if failed_queues:
                    failed.append(
                        {
                            "subject_uuid": subject_uuid,
                            "error": (
                                f"Failed to purge queues: {', '.join(failed_queues)}"
                                f"{_shared_reason(shared)}"
                            ),
                        }
                    )
                else:
                    successful.append(subject_uuid)

            else:
                failed.append(
                    {
                        "subject_uuid": subject_uuid,
                        "error": f"Unsupported operation: {bulk_request.operation}",
                    }
                )

        except Exception:
            # Wraps repository calls as well as the broker, so it cannot name BrokerError.
            _log.exception(
                "Bulk operation %s failed for subject %s", bulk_request.operation, subject_uuid
            )
            await session.rollback()
            failed.append({"subject_uuid": subject_uuid, "error": "Operation failed"})

    return BulkOperationResult(
        successful=successful,
        failed=failed,
        total_processed=len(bulk_request.subject_uuids),
        timestamp=datetime.utcnow(),
    )


# =====================================================
# HELPER FUNCTIONS
# =====================================================


async def _require_owned_queue(session: AsyncSession, subject: Subject, queue_name: str) -> None:
    """Raise unless `queue_name` is stored on one of the subject's own links.

    Raised outside the caller's try, whose catch-all would turn it into a 200 failure body. An
    unowned name gets the unknown-subject answer so it does not confirm the queue exists.
    """
    if queue_name not in {link.backing_queue_name for link in subject.subscription_links}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    shared = await pr.SubscriptionSubjectRepository(session).count_other_subjects_storing_queue(
        queue_name, subject.subject_id
    )
    if shared:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Queue is shared with another subject"
        )


async def _queues_shared_with_other_subjects(session: AsyncSession, subject: Subject) -> set[str]:
    """The stored queue names on `subject`'s links that another subject's link also stores.

    Delete refuses these with 409; purge must not delete them either, since the other subject
    still reads from the queue.
    """
    links = pr.SubscriptionSubjectRepository(session)
    return {
        link.backing_queue_name
        for link in subject.subscription_links
        if await links.count_other_subjects_storing_queue(
            link.backing_queue_name, subject.subject_id
        )
    }


def _shared_reason(shared: set[str]) -> str:
    """Message suffix naming the queues a purge skipped because another subject stores them."""
    if not shared:
        return ""
    return f"; shared with another subject, not purged: {', '.join(sorted(shared))}"


def _trusted_exchange_or_409(subject: Subject) -> str:
    """The subject's stored exchange, or 409 when the row's name cannot be trusted.

    Call only after the caller is authorized, so the answer reveals nothing about a row the
    caller cannot see.
    """
    try:
        return trusted_exchange_name(subject)
    except UntrustedBrokerName as e:
        _log.warning("Subject %s has an untrusted exchange name: %s", subject.subject_uuid, e)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Subject broker name needs repair"
        ) from e


def _exchange_to_delete(subject: Subject) -> str | None:
    """The stored exchange to delete, or None when the name is untrusted.

    The named exchange may belong to another subject, so an untrusted row is deleted without
    touching the broker.
    """
    try:
        return trusted_exchange_name(subject)
    except UntrustedBrokerName as e:
        _log.warning(
            "Subject %s deleted without a broker call: %s; stored exchange %r",
            subject.subject_uuid,
            e,
            subject.backing_exchange_name,
        )
        return None


async def _get_subject_queue_info(subject: Subject, exchange: str) -> SubjectQueueInfo:
    """
    Helper function to get queue information for a subject.
    """
    # Count queues and messages (this is a simplified implementation)
    # In a real implementation, you would query the message broker for detailed stats
    queue_count = len(subject.subscription_links)
    total_messages = 0  # TODO: Implement message counting from broker
    total_consumers = 0  # TODO: Implement consumer counting from broker

    return SubjectQueueInfo(
        subject_uuid=subject.subject_uuid,
        subject_name=subject.subject_name,
        exchange_name=exchange,
        queue_count=queue_count,
        total_messages=total_messages,
        total_consumers=total_consumers,
    )
