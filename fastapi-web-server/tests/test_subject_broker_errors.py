"""Broker failures in the subject routes are logged and reported, never swallowed (#61)."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from pyrabbit2 import http as pyrabbit_http
from pyrabbit2.api import APIError
from sqlalchemy.ext.asyncio import AsyncSession

from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.models.endpoint_models import EndPoint
from uudex_server.models.message_models import MessagePublishRequest
from uudex_server.models.subject_models import (
    BulkSubjectOperation,
    QueueManagementRequest,
    SubjectCreate,
)
from uudex_server.routes import subject_routes
from uudex_server.services.message_services.base import BrokerError
from uudex_server.services.message_services.rabbit_mq import RabbitMqService

ROUTES_LOGGER = "uudex_server.routes.subject_routes"


@pytest.fixture
def admin_user():
    endpoint = EndPoint(
        endpoint_id=2,
        participant_id=1,
        endpoint_name="admin-endpoint",
        certificate_dn="CN=admin-user",
        uudex_administrator_sw="Y",
    )
    return AuthenticatedUser(endpoint=endpoint)


@pytest.fixture
def session(admin_user):
    s = Mock(spec=AsyncSession)
    s.merge = AsyncMock(return_value=admin_user.endpoint)
    return s


def make_subject(links=("sub-a", "sub-b")):
    return SimpleNamespace(
        subject_id=7,
        subject_uuid="subj-uuid",
        subject_name="subj",
        owner_participant_id=1,
        backing_exchange_name="e_subj_subj-uuid",
        subscription_links=[SimpleNamespace(subscription_uuid=u) for u in links],
    )


def make_broker():
    broker = Mock()
    broker.build_queue_name = Mock(
        side_effect=lambda tag, subject_name, subscription_uuid: f"q_{subscription_uuid}"
    )
    broker.build_exchange_name = Mock(return_value="e_subj_subj-uuid")
    return broker


def make_repo(subject):
    repo = Mock()
    repo.select_by_field = AsyncMock(return_value=subject)
    repo.create = AsyncMock(return_value=subject)
    repo.delete = AsyncMock()
    return repo


def error_records(caplog):
    return [r for r in caplog.records if r.name == ROUTES_LOGGER and r.levelno >= logging.ERROR]


class TestBulkDelete:
    async def test_broker_failure_is_logged_reported_and_keeps_row(
        self, session, admin_user, caplog
    ):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()
        broker.delete_subject.side_effect = BrokerError("exchange delete refused")

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=["subj-uuid"], operation="delete"),
                session,
                admin_user,
                broker,
            )

        assert result.successful == []
        assert len(result.failed) == 1
        assert result.failed[0]["subject_uuid"] == "subj-uuid"
        assert "exchange delete refused" in result.failed[0]["error"]
        repo.delete.assert_not_called()
        records = error_records(caplog)
        assert len(records) == 1
        assert "subj-uuid" in records[0].getMessage()
        assert isinstance(records[0].exc_info[1], BrokerError)

    async def test_success_response_is_unchanged(self, session, admin_user, caplog):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=["subj-uuid"], operation="delete"),
                session,
                admin_user,
                broker,
            )

        assert result.successful == ["subj-uuid"]
        assert result.failed == []
        assert result.total_processed == 1
        repo.delete.assert_awaited_once_with(7)
        assert error_records(caplog) == []

    async def test_non_broker_error_is_logged_and_reported(self, session, admin_user, caplog):
        subject = make_subject()
        repo = make_repo(subject)
        repo.delete.side_effect = RuntimeError("db down")

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=["subj-uuid"], operation="delete"),
                session,
                admin_user,
                make_broker(),
            )

        assert result.failed == [{"subject_uuid": "subj-uuid", "error": "db down"}]
        records = error_records(caplog)
        assert len(records) == 1
        assert isinstance(records[0].exc_info[1], RuntimeError)


class TestBulkPurge:
    async def test_queue_failure_is_logged_reported_and_others_still_purged(
        self, session, admin_user, caplog
    ):
        subject = make_subject(links=("sub-a", "sub-b"))
        repo = make_repo(subject)
        broker = make_broker()
        broker.delete_queue.side_effect = [BrokerError("queue gone"), 0]

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=["subj-uuid"], operation="purge_queues"),
                session,
                admin_user,
                broker,
            )

        assert result.successful == []
        assert result.failed == [
            {"subject_uuid": "subj-uuid", "error": "Failed to purge queues: q_sub-a"}
        ]
        assert [c.args[0] for c in broker.delete_queue.call_args_list] == ["q_sub-a", "q_sub-b"]
        records = error_records(caplog)
        assert len(records) == 1
        assert "q_sub-a" in records[0].getMessage()
        assert isinstance(records[0].exc_info[1], BrokerError)

    async def test_success_response_is_unchanged(self, session, admin_user, caplog):
        repo = make_repo(make_subject())

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=["subj-uuid"], operation="purge_queues"),
                session,
                admin_user,
                make_broker(),
            )

        assert result.successful == ["subj-uuid"]
        assert result.failed == []
        assert error_records(caplog) == []


class TestOtherHandlersLog:
    async def test_single_delete_logs_and_still_deletes_row(self, session, admin_user, caplog):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()
        broker.delete_subject.side_effect = BrokerError("exchange delete refused")

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            patch.object(
                subject_routes.pr, "select_subject_by_id", new=AsyncMock(return_value=subject)
            ),
        ):
            result = await subject_routes.delete_subject(7, session, admin_user, broker)

        assert result == {"message": "Subject deleted successfully", "subject_id": 7}
        repo.delete.assert_awaited_once_with(7)
        records = error_records(caplog)
        assert len(records) == 1
        assert isinstance(records[0].exc_info[1], BrokerError)

    async def test_create_logs_and_rolls_back(self, session, admin_user, caplog):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()
        broker.create_subject.side_effect = BrokerError("exchange create refused")
        data = SubjectCreate(
            subject_uuid="subj-uuid",
            subject_name="subj",
            dataset_instance_key="k",
            subscription_type="pull",
            fulfillment_types_available="immediate",
            full_queue_behavior="NO_CONSTRAINT",
            max_queue_size_kb=None,
            max_message_count=None,
            priority=None,
            backing_exchange_name="e_subj_subj-uuid",
            owner_participant_id=1,
            dataset_definition_id=1,
        )

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.create_subject(data, session, admin_user, broker)

        assert exc_info.value.status_code == 500
        assert "exchange create refused" in exc_info.value.detail
        repo.delete.assert_awaited_once_with(7)
        assert len(error_records(caplog)) == 1

    async def test_publish_logs(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        broker = make_broker()
        broker.publish_message.side_effect = BrokerError("publish refused")

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.publish_messages_to_subject(
                "subj-uuid", MessagePublishRequest(messages=["m"]), session, admin_user, broker
            )

        assert exc_info.value.status_code == 500
        records = error_records(caplog)
        assert len(records) == 1
        assert isinstance(records[0].exc_info[1], BrokerError)

    async def test_single_purge_logs_each_failed_queue(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        broker = make_broker()
        broker.delete_queue.side_effect = BrokerError("queue gone")

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.manage_subject_queues(
                "subj-uuid", QueueManagementRequest(action="purge"), session, admin_user, broker
            )

        assert result.queue_info == {"purged_queues": []}
        assert len(error_records(caplog)) == 2

    async def test_queue_management_catch_all_logs(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        broker = make_broker()
        broker.delete_queue.side_effect = RuntimeError("boom")

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.manage_subject_queues(
                "subj-uuid",
                QueueManagementRequest(action="delete", queue_name="q"),
                session,
                admin_user,
                broker,
            )

        assert result.success is False
        records = error_records(caplog)
        assert len(records) == 1
        assert isinstance(records[0].exc_info[1], RuntimeError)


class TestRabbitMqErrorTranslation:
    @pytest.mark.parametrize(
        "library_error",
        [
            pyrabbit_http.HTTPError({"reason": "nope"}, status=500, reason="Server Error"),
            pyrabbit_http.NetworkError("unreachable"),
            APIError("no vhost"),
            PermissionError("401"),
        ],
    )
    def test_library_errors_become_broker_error(self, library_error):
        with patch("uudex_server.services.message_services.rabbit_mq.Client") as client_cls:
            client_cls.return_value.delete_exchange.side_effect = library_error
            service = RabbitMqService("amqp://host:15672?username=u&password=p")

        with pytest.raises(BrokerError) as exc_info:
            service.delete_subject("subj", "subj-uuid")

        assert exc_info.value.__cause__ is library_error
        assert "delete_subject" in str(exc_info.value)

    def test_unrelated_errors_are_not_translated(self):
        with patch("uudex_server.services.message_services.rabbit_mq.Client") as client_cls:
            client_cls.return_value.delete_exchange.side_effect = KeyError("bug")
            service = RabbitMqService("amqp://host:15672?username=u&password=p")

        with pytest.raises(KeyError):
            service.delete_subject("subj", "subj-uuid")

    def test_return_value_passes_through(self):
        with patch("uudex_server.services.message_services.rabbit_mq.Client") as client_cls:
            client_cls.return_value.delete_queue.return_value = True
            service = RabbitMqService("amqp://host:15672?username=u&password=p")

        assert service.delete_queue("q") is True
        client_cls.return_value.delete_queue.assert_called_once_with("/", "q")
