"""Queue management delete only reaches queues built from the subject's own subscriptions (#69)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.models.endpoint_models import EndPoint
from uudex_server.models.subject_models import QueueManagementRequest
from uudex_server.routes import subject_routes
from uudex_server.services.message_services.base import UUDEXBrokerService


@pytest.fixture
def owner_user():
    endpoint = EndPoint(
        endpoint_id=3,
        participant_id=1,
        endpoint_name="owner-endpoint",
        certificate_dn="CN=owner",
        uudex_administrator_sw="N",
    )
    return AuthenticatedUser(endpoint=endpoint)


@pytest.fixture
def session(owner_user):
    s = Mock(spec=AsyncSession)
    s.merge = AsyncMock(return_value=owner_user.endpoint)
    return s


def make_subject():
    return SimpleNamespace(
        subject_id=7,
        subject_uuid="subj-uuid",
        subject_name="subj",
        owner_participant_id=1,
        subscription_links=[SimpleNamespace(subscription_uuid="sub-a")],
    )


def make_broker():
    broker = Mock()
    broker.build_queue_name = Mock(side_effect=UUDEXBrokerService.build_queue_name)
    broker.delete_queue = Mock(return_value=0)
    return broker


async def delete(queue_name, session, user, broker, subject):
    repo = Mock()
    repo.select_by_field = AsyncMock(return_value=subject)
    with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
        return await subject_routes.manage_subject_queues(
            "subj-uuid",
            QueueManagementRequest(action="delete", queue_name=queue_name),
            session,
            user,
            broker,
        )


async def test_owner_cannot_delete_another_participants_queue(session, owner_user):
    broker = make_broker()
    foreign = UUDEXBrokerService.build_queue_name("uudex", "other-subject", "other-sub")

    with pytest.raises(HTTPException) as exc:
        await delete(foreign, session, owner_user, broker, make_subject())

    assert exc.value.status_code == 404
    assert exc.value.detail == "Subject not found"
    broker.delete_queue.assert_not_called()


async def test_owner_deletes_own_subscription_queue(session, owner_user):
    broker = make_broker()
    own = UUDEXBrokerService.build_queue_name("uudex", "subj", "sub-a")

    result = await delete(own, session, owner_user, broker, make_subject())

    assert result.success is True
    assert result.queue_info["deleted_queue"] == own
    broker.delete_queue.assert_called_once_with(own)


async def test_unknown_queue_name_is_404_and_not_deleted(session, owner_user):
    broker = make_broker()

    with pytest.raises(HTTPException) as exc:
        await delete("no-such-queue", session, owner_user, broker, make_subject())

    assert exc.value.status_code == 404
    assert exc.value.detail == "Subject not found"
    broker.delete_queue.assert_not_called()
