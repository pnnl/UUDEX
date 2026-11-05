from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from uudex_server.core.dependencies import SessionDep, UserDep
from uudex_server.core.settings import get_settings
from uudex_server.models import Subscription
from uudex_server.models.message_models import (
    MessageConsumeRequest,
    MessageConsumeResponse,
    MessageContent,
)
from uudex_server.models.subscription_models import SubscriptionCreate
from uudex_server.models.subscription_subject_models import SubscriptionSubject
from uudex_server.repos import subscription_and_subject_repositories as ssr
from uudex_server.services.message_services.message_broker_common import message_broker_factory

subscriptions_router = APIRouter(prefix="/subscriptions")
subscription_router = APIRouter(prefix="/subscription")

# Create v1 parent router
v1_router = APIRouter(prefix="/v1", tags=["v1"])
v1_router.include_router(subscriptions_router, tags=["v1", "subscriptions"])
v1_router.include_router(subscription_router, tags=["v1", "subscriptions"])


@subscription_router.get("/{subscription_uuid}/subjects")
async def get_subscription_subjects(
    subscription_uuid: str, session: SessionDep, user: UserDep
) -> list[SubscriptionSubject]:
    repo = ssr.SubscriptionSubjectRepository(session)
    subscription_subjects: list[
        SubscriptionSubject
    ] = await repo.select_subjects_by_subscription_uuid(
        session=session, subscription_uuid=subscription_uuid
    )

    if not user.is_admin():
        subscription_subjects = [
            sub
            for sub in subscription_subjects
            if sub.subscription.owner_endpoint_id == user.endpoint.endpoint_id
        ]

    return subscription_subjects


@subscriptions_router.get("/admin", operation_id="get_admin_subscriptions")
async def get_admin_subscriptions(session: SessionDep, user: UserDep) -> list[Subscription]:
    repo = ssr.SubscriptionRepository(session)
    return await repo.select_admin_subscriptions()


@subscriptions_router.get("/", operation_id="get_user_subscriptions")
async def get_user_subscriptions(session: SessionDep, user: UserDep) -> list[Subscription]:
    repo = ssr.SubscriptionRepository(session)
    return await repo.select_user_subscriptions(user=user)


@subscription_router.post("/", operation_id="create_subscription")
async def create_subscription(
    subscription: SubscriptionCreate, session: SessionDep, user: UserDep
) -> Subscription:
    # TODO: Implement create_subscription method in repository
    # For now, use a direct creation approach
    sub: Subscription = await ssr.create_subscription(
        session=session, user=user, subscription_add=subscription
    )
    return sub


@subscription_router.get("/{subscription_uuid}", operation_id="get_subscription_by_uuid")
async def get_subscription_by_uuid(subscription_uuid: str, session: SessionDep) -> Subscription:
    repo = ssr.SubscriptionRepository(session)
    sub: Subscription | None = await repo.select_subscription_by_uuid(
        subscription_uuid=subscription_uuid
    )
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    return sub


@subscription_router.post("/{subscription_uuid}/consume", operation_id="consume_messages")
async def consume_messages(
    subscription_uuid: str,
    consume_request: MessageConsumeRequest,
    session: SessionDep,
    user: UserDep
) -> MessageConsumeResponse:
    """
    Consume messages from a subscription's queue.

    Users can only consume messages from their own subscriptions unless they are admin.
    """
    # Get the subscription to verify it exists and check ownership
    repo = ssr.SubscriptionRepository(session)
    subscription: Subscription | None = await repo.select_subscription_by_uuid(
        subscription_uuid=subscription_uuid
    )
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found"
        )

    # Check authorization - users can only consume from their own subscriptions
    if not user.is_admin():
        # Access endpoint safely by merging into current session
        endpoint = await session.merge(user.endpoint)
        if subscription.owner_endpoint_id != endpoint.endpoint_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to consume messages from this subscription"
            )

    # Get subscription subjects to find the queue names
    sub_subject_repo = ssr.SubscriptionSubjectRepository(session)
    subscription_subjects = await sub_subject_repo.select_subjects_by_subscription_uuid(
        session=session, subscription_uuid=subscription_uuid
    )

    if not subscription_subjects:
        # No subjects attached to subscription, return empty response
        return MessageConsumeResponse(
            messages=[],
            total_consumed=0,
            subscription_uuid=subscription_uuid,
            timestamp=datetime.utcnow()
        )

    # Get the message broker service
    settings = get_settings()
    broker_service = message_broker_factory(settings.messagebus_connection)

    all_messages: list[MessageContent] = []
    messages_per_subject = max(1, consume_request.count // len(subscription_subjects))
    remaining_messages = consume_request.count

    # Consume messages from each subject queue
    for sub_subject in subscription_subjects:
        if remaining_messages <= 0:
            break

        # Build queue name using the same pattern as creation
        queue_name = broker_service.build_queue_name(
            tag="uudex",  # Default tag used in UUDEX
            subject_name=sub_subject.subject.subject_name,
            subscription_uuid=subscription_uuid
        )

        # Consume messages from this queue
        messages_to_get = min(messages_per_subject, remaining_messages)
        raw_messages = broker_service.get_messages(queue_name, count=messages_to_get)

        # Convert raw messages to MessageContent objects
        if raw_messages:
            for raw_msg in raw_messages:
                message_content = MessageContent(
                    payload=raw_msg.get('payload', ''),
                    message_id=raw_msg.get('message_id'),
                    timestamp=raw_msg.get('timestamp'),
                    properties=raw_msg.get('properties')
                )
                all_messages.append(message_content)
                remaining_messages -= 1

                if remaining_messages <= 0:
                    break

    return MessageConsumeResponse(
        messages=all_messages,
        total_consumed=len(all_messages),
        subscription_uuid=subscription_uuid,
        timestamp=datetime.utcnow()
    )
