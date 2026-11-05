import uuid

import pytest

import uudex_server.models as m
import uudex_server.repos as r


@pytest.mark.asyncio
async def setup_participant(participant_repo: r.ParticipantRepository) -> m.Participant:
    participant = m.ParticipantCreate(
        participant_uuid=str(uuid.uuid4()),
        participant_short_name="short1",
        participant_long_name="long1",
        description="desc1",
        root_org_sw="Y",
        active_sw="Y",
    )

    created_participant = await participant_repo.create(participant)

    return created_participant


@pytest.mark.asyncio
async def test_create_subscription(
    subscription_repo: r.SubscriptionRepository, participant_repo: r.ParticipantRepository
):
    created_participant = await setup_participant(participant_repo=participant_repo)
    subscription = m.SubscriptionCreate(
        subscription_uuid="uuid1",
        subscription_name="name1",
        subscription_state="active",
        owner_endpoint_id=created_participant.participant_id,
    )
    result = await subscription_repo.create(subscription)
    assert result.subscription_uuid == "uuid1"


@pytest.mark.asyncio
async def test_select_subscription_by_id(
    subscription_repo: r.SubscriptionRepository, participant_repo: r.ParticipantRepository
):
    created_participant = await setup_participant(participant_repo=participant_repo)
    subscription = m.SubscriptionCreate(
        subscription_uuid="uuid1",
        subscription_name="name1",
        subscription_state="active",
        owner_endpoint_id=created_participant.participant_id,
    )
    created_subscription = await subscription_repo.create(subscription)
    result = await subscription_repo.select_by_id(created_subscription.subscription_id)
    assert result is not None
    assert result.subscription_uuid == "uuid1"


@pytest.mark.asyncio
async def test_update_subscription(
    subscription_repo: r.SubscriptionRepository, participant_repo: r.ParticipantRepository
):
    created_participant = await setup_participant(participant_repo=participant_repo)
    subscription = m.SubscriptionCreate(
        subscription_uuid="uuid1",
        subscription_name="name1",
        subscription_state="active",
        owner_endpoint_id=created_participant.participant_id,
    )
    created_subscription = await subscription_repo.create(subscription)
    created_subscription.subscription_name = "updated_name"
    result = await subscription_repo.update(created_subscription)
    assert result.subscription_name == "updated_name"


@pytest.mark.asyncio
async def test_delete_subscription(
    subscription_repo: r.SubscriptionRepository, participant_repo: r.ParticipantRepository
):
    created_participant = await setup_participant(participant_repo=participant_repo)
    subscription = m.SubscriptionCreate(
        subscription_uuid="uuid1",
        subscription_name="name1",
        subscription_state="active",
        owner_endpoint_id=created_participant.participant_id,
    )
    created_subscription = await subscription_repo.create(subscription)
    subscription_remove = m.SubscriptionDelete(subscription_id=created_subscription.subscription_id)
    await subscription_repo.delete(subscription_remove)
    result = await subscription_repo.select_by_id(created_subscription.subscription_id)
    assert result is None


@pytest.mark.asyncio
async def test_select_user_subscriptions(
    authenticated_user: m.AuthenticatedUser, subscription_repo: r.SubscriptionRepository
):
    subscription = m.SubscriptionCreate(
        subscription_uuid="uuid1",
        subscription_name="name1",
        subscription_state="active",
        owner_endpoint_id=authenticated_user.endpoint.endpoint_id,
    )
    await subscription_repo.create(subscription)
    result = await subscription_repo.select_user_subscriptions(authenticated_user)
    assert len(result) > 0
    assert result[0].subscription_uuid == "uuid1"
    assert result[0].owner_endpoint_id == authenticated_user.endpoint.endpoint_id


@pytest.mark.asyncio
async def test_select_admin_subscriptions(
    subscription_repo: r.SubscriptionRepository, participant_repo: r.ParticipantRepository
):
    created_participant = await setup_participant(participant_repo=participant_repo)
    subscription = m.SubscriptionCreate(
        subscription_uuid="uuid1",
        subscription_name="name1",
        subscription_state="active",
        owner_endpoint_id=created_participant.participant_id,
    )
    await subscription_repo.create(subscription)
    result = await subscription_repo.select_admin_subscriptions()
    assert len(result) > 0
    assert result[0].subscription_uuid == "uuid1"


@pytest.mark.asyncio
async def test_select_subscription_by_uuid(
    subscription_repo: r.SubscriptionRepository, participant_repo: r.ParticipantRepository
):
    created_participant = await setup_participant(participant_repo=participant_repo)
    subscription = m.SubscriptionCreate(
        subscription_uuid="uuid1",
        subscription_name="name1",
        subscription_state="active",
        owner_endpoint_id=created_participant.participant_id,
    )
    await subscription_repo.create(subscription)
    result = await subscription_repo.select_subscription_by_uuid("uuid1")
    assert result is not None
    assert result.subscription_uuid == "uuid1"
