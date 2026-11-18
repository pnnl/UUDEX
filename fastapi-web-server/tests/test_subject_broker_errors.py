"""Broker failures in the subject routes are logged and reported, never swallowed (#61)."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from pyrabbit2 import api as pyrabbit_api
from pyrabbit2 import http as pyrabbit_http
from sqlalchemy.ext.asyncio import AsyncSession

from uudex_server.models.authenticated_user import AuthenticatedUser
from uudex_server.models.endpoint_models import EndPoint
from uudex_server.models.message_models import MessagePublishRequest
from uudex_server.models.subject_models import (
    BulkSubjectOperation,
    QueueManagementRequest,
    Subject,
    SubjectCreate,
)
from uudex_server.routes import subject_routes
from uudex_server.services.database_service import get_db_session
from uudex_server.services.message_services.base import BrokerError
from uudex_server.services.message_services.rabbit_mq import RabbitMqService

ROUTES_LOGGER = "uudex_server.routes.subject_routes"
# A canonical uuid: stored exchange names are only trusted when tied to one.
SUBJ_UUID = "0b3f1c52-6a1e-4d0e-9b8e-3f2a7c9d4e11"


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
        subject_uuid=SUBJ_UUID,
        subject_name="subj",
        owner_participant_id=1,
        backing_exchange_name=f"e_{SUBJ_UUID}",
        subscription_links=[
            SimpleNamespace(subscription_uuid=u, backing_queue_name=f"q_{u}") for u in links
        ],
    )


def make_broker():
    broker = Mock()
    broker.build_queue_name = Mock(
        side_effect=lambda tag, subject_name, subscription_uuid: f"q_{subscription_uuid}"
    )
    return broker


def make_repo(subject):
    repo = Mock()
    repo.select_by_field = AsyncMock(return_value=subject)
    repo.select_by_uuid_with_links = AsyncMock(return_value=subject)
    repo.create = AsyncMock(return_value=subject)
    # Mirrors Repository.delete, which reads the id fields off the object it is given.
    repo.delete = AsyncMock(side_effect=lambda obj, **_kwargs: obj.subject_id)
    return repo


def unshared_queues():
    """Patch the link repository so the delete path finds no other subject storing the name."""
    link_repo = Mock()
    link_repo.count_other_subjects_storing_queue = AsyncMock(return_value=0)
    return patch.object(subject_routes.pr, "SubscriptionSubjectRepository", return_value=link_repo)


def make_subject_create():
    return SubjectCreate(
        subject_uuid=SUBJ_UUID,
        subject_name="subj",
        dataset_instance_key="k",
        subscription_type="pull",
        fulfillment_types_available="immediate",
        full_queue_behavior="NO_CONSTRAINT",
        max_queue_size_kb=None,
        max_message_count=None,
        priority=None,
        backing_exchange_name=f"e_{SUBJ_UUID}",
        owner_participant_id=1,
        dataset_definition_id=1,
    )


def error_records(caplog):
    return [r for r in caplog.records if r.name == ROUTES_LOGGER and r.levelno >= logging.ERROR]


class TestRealRepository:
    async def test_single_delete_removes_the_row(self, setup_test_env, admin_user):
        async with get_db_session() as session:
            repo = subject_routes.pr.SubjectRepository(session)
            created = await repo.create(
                Subject(
                    **make_subject_create().model_dump(exclude={"subject_uuid"}),
                    subject_uuid="real",
                )
            )

            await subject_routes.delete_subject(
                created.subject_id, session, admin_user, make_broker()
            )

            assert await subject_routes.pr.select_subject_by_id(session, created.subject_id) is None


BROKER_SECRET = "brokeruser"
SECRET_ERROR_TEXT = f"401 Unauthorized with user {BROKER_SECRET} :401"


def assert_logged_not_returned(caplog, response_text):
    assert BROKER_SECRET not in response_text
    records = error_records(caplog)
    assert any(BROKER_SECRET in str(r.exc_info[1]) for r in records)


class TestLibraryTextStaysOutOfResponses:
    async def test_create(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        broker = make_broker()
        broker.create_exchange.side_effect = BrokerError(SECRET_ERROR_TEXT)

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.create_subject(make_subject_create(), session, admin_user, broker)

        assert_logged_not_returned(caplog, str(exc_info.value.detail))

    async def test_single_delete(self, session, admin_user, caplog):
        subject = make_subject()
        broker = make_broker()
        broker.delete_exchange.side_effect = BrokerError(SECRET_ERROR_TEXT)

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=make_repo(subject)),
            patch.object(
                subject_routes.pr, "select_subject_by_id", new=AsyncMock(return_value=subject)
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.delete_subject(7, session, admin_user, broker)

        assert_logged_not_returned(caplog, str(exc_info.value.detail))

    async def test_publish(self, session, admin_user, caplog):
        broker = make_broker()
        broker.publish_message.side_effect = BrokerError(SECRET_ERROR_TEXT)

        with (
            patch.object(
                subject_routes.pr, "SubjectRepository", return_value=make_repo(make_subject())
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.publish_messages_to_subject(
                SUBJ_UUID, MessagePublishRequest(messages=["m"]), session, admin_user, broker
            )

        assert exc_info.value.detail == "Failed to publish messages"
        assert_logged_not_returned(caplog, str(exc_info.value.detail))

    async def test_bulk_delete_broker_error(self, session, admin_user, caplog):
        broker = make_broker()
        broker.delete_exchange.side_effect = BrokerError(SECRET_ERROR_TEXT)

        with patch.object(
            subject_routes.pr, "SubjectRepository", return_value=make_repo(make_subject())
        ):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=[SUBJ_UUID], operation="delete"),
                session,
                admin_user,
                broker,
            )

        assert_logged_not_returned(caplog, result.model_dump_json())

    async def test_bulk_unexpected_error(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        repo.select_by_uuid_with_links.side_effect = RuntimeError(SECRET_ERROR_TEXT)

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=[SUBJ_UUID], operation="delete"),
                session,
                admin_user,
                make_broker(),
            )

        assert_logged_not_returned(caplog, result.model_dump_json())

    async def test_queue_management_catch_all(self, session, admin_user, caplog):
        broker = make_broker()
        broker.delete_queue.side_effect = RuntimeError(SECRET_ERROR_TEXT)

        with (
            patch.object(
                subject_routes.pr, "SubjectRepository", return_value=make_repo(make_subject())
            ),
            unshared_queues(),
        ):
            result = await subject_routes.manage_subject_queues(
                SUBJ_UUID,
                QueueManagementRequest(action="delete", queue_name="q_sub-a"),
                session,
                admin_user,
                broker,
            )

        assert result.message == "Queue management operation failed"
        assert_logged_not_returned(caplog, result.model_dump_json())


class TestBulkDelete:
    async def test_broker_failure_is_logged_reported_and_keeps_row(
        self, session, admin_user, caplog
    ):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()
        broker.delete_exchange.side_effect = BrokerError("exchange delete refused")

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=[SUBJ_UUID], operation="delete"),
                session,
                admin_user,
                broker,
            )

        assert result.successful == []
        assert len(result.failed) == 1
        assert result.failed[0]["subject_uuid"] == SUBJ_UUID
        assert result.failed[0]["error"] == "Broker delete failed"
        repo.delete.assert_awaited_once_with(subject, commit=False)
        session.rollback.assert_awaited_once()
        session.commit.assert_not_called()
        records = error_records(caplog)
        assert len(records) == 1
        assert SUBJ_UUID in records[0].getMessage()
        assert isinstance(records[0].exc_info[1], BrokerError)

    async def test_success_response_is_unchanged(self, session, admin_user, caplog):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=[SUBJ_UUID], operation="delete"),
                session,
                admin_user,
                broker,
            )

        assert result.successful == [SUBJ_UUID]
        assert result.failed == []
        assert result.total_processed == 1
        repo.delete.assert_awaited_once_with(subject, commit=False)
        session.commit.assert_awaited_once()
        assert error_records(caplog) == []

    async def test_non_broker_error_is_logged_and_reported(self, session, admin_user, caplog):
        subject = make_subject()
        repo = make_repo(subject)
        repo.delete.side_effect = RuntimeError("db down")

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.bulk_subject_operations(
                BulkSubjectOperation(subject_uuids=[SUBJ_UUID], operation="delete"),
                session,
                admin_user,
                make_broker(),
            )

        assert result.failed == [{"subject_uuid": SUBJ_UUID, "error": "Operation failed"}]
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
                BulkSubjectOperation(subject_uuids=[SUBJ_UUID], operation="purge_queues"),
                session,
                admin_user,
                broker,
            )

        assert result.successful == []
        assert result.failed == [
            {"subject_uuid": SUBJ_UUID, "error": "Failed to purge queues: q_sub-a"}
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
                BulkSubjectOperation(subject_uuids=[SUBJ_UUID], operation="purge_queues"),
                session,
                admin_user,
                make_broker(),
            )

        assert result.successful == [SUBJ_UUID]
        assert result.failed == []
        assert error_records(caplog) == []


class TestOtherHandlersLog:
    async def test_single_delete_logs_keeps_row_and_reports_error(
        self, session, admin_user, caplog
    ):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()
        broker_error = BrokerError("exchange delete refused")
        broker.delete_exchange.side_effect = broker_error

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            patch.object(
                subject_routes.pr, "select_subject_by_id", new=AsyncMock(return_value=subject)
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.delete_subject(7, session, admin_user, broker)

        assert exc_info.value.status_code == 500
        assert exc_info.value.__cause__ is broker_error
        assert exc_info.value.detail == "Failed to delete message broker infrastructure"
        repo.delete.assert_awaited_once_with(subject, commit=False)
        session.rollback.assert_awaited_once()
        session.commit.assert_not_called()
        records = error_records(caplog)
        assert len(records) == 1
        assert SUBJ_UUID in records[0].getMessage()
        assert isinstance(records[0].exc_info[1], BrokerError)

    async def test_single_delete_success_deletes_row(self, session, admin_user, caplog):
        subject = make_subject()
        repo = make_repo(subject)

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            patch.object(
                subject_routes.pr, "select_subject_by_id", new=AsyncMock(return_value=subject)
            ),
        ):
            result = await subject_routes.delete_subject(7, session, admin_user, make_broker())

        assert result == {"message": "Subject deleted successfully", "subject_id": 7}
        repo.delete.assert_awaited_once_with(subject, commit=False)
        session.commit.assert_awaited_once()
        assert error_records(caplog) == []

    async def test_create_logs_and_rolls_back(self, session, admin_user, caplog):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()
        broker_error = BrokerError("exchange create refused")
        broker.create_exchange.side_effect = broker_error
        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.create_subject(make_subject_create(), session, admin_user, broker)

        assert exc_info.value.status_code == 500
        assert exc_info.value.__cause__ is broker_error
        assert exc_info.value.detail == "Failed to create message broker infrastructure"
        repo.delete.assert_awaited_once_with(subject)
        assert len(error_records(caplog)) == 1

    async def test_create_rolls_back_and_reraises_non_broker_error(
        self, session, admin_user, caplog
    ):
        subject = make_subject()
        repo = make_repo(subject)
        broker = make_broker()
        bug = RuntimeError("unexpected library bug")
        broker.create_exchange.side_effect = bug

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            pytest.raises(RuntimeError) as exc_info,
        ):
            await subject_routes.create_subject(make_subject_create(), session, admin_user, broker)

        assert exc_info.value is bug
        repo.delete.assert_awaited_once_with(subject)
        records = error_records(caplog)
        assert len(records) == 1
        assert records[0].exc_info[1] is bug

    async def test_create_rollback_failure_is_logged_and_original_error_raised(
        self, session, admin_user, caplog
    ):
        subject = make_subject()
        repo = make_repo(subject)
        repo.delete.side_effect = RuntimeError("rollback failed")
        broker = make_broker()
        broker_error = BrokerError("exchange create refused")
        broker.create_exchange.side_effect = broker_error

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.create_subject(make_subject_create(), session, admin_user, broker)

        assert exc_info.value.status_code == 500
        assert exc_info.value.__cause__ is broker_error
        causes = [r.exc_info[1] for r in error_records(caplog)]
        assert causes[0] is broker_error
        assert isinstance(causes[1], RuntimeError)
        assert "Rollback" in error_records(caplog)[1].getMessage()
        assert len(causes) == 2

    async def test_create_rollback_failure_keeps_non_broker_error(
        self, session, admin_user, caplog
    ):
        repo = make_repo(make_subject())
        repo.delete.side_effect = RuntimeError("rollback failed")
        broker = make_broker()
        bug = ValueError("unexpected library bug")
        broker.create_exchange.side_effect = bug

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            pytest.raises(ValueError) as exc_info,
        ):
            await subject_routes.create_subject(make_subject_create(), session, admin_user, broker)

        assert exc_info.value is bug

    async def test_publish_logs(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        broker = make_broker()
        broker.publish_message.side_effect = BrokerError("publish refused")

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            pytest.raises(HTTPException) as exc_info,
        ):
            await subject_routes.publish_messages_to_subject(
                SUBJ_UUID, MessagePublishRequest(messages=["m"]), session, admin_user, broker
            )

        assert exc_info.value.status_code == 500
        records = error_records(caplog)
        assert len(records) == 1
        assert isinstance(records[0].exc_info[1], BrokerError)

    async def test_single_purge_reports_every_failed_queue(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        broker = make_broker()
        broker.delete_queue.side_effect = BrokerError("queue gone")

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.manage_subject_queues(
                SUBJ_UUID, QueueManagementRequest(action="purge"), session, admin_user, broker
            )

        assert result.success is False
        assert "q_sub-a" in result.message
        assert "q_sub-b" in result.message
        assert result.queue_info == {
            "purged_queues": [],
            "failed_queues": ["q_sub-a", "q_sub-b"],
        }
        assert len(error_records(caplog)) == 2

    async def test_single_purge_partial_failure_is_not_a_success(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        broker = make_broker()
        broker.delete_queue.side_effect = [BrokerError("queue gone"), 0]

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.manage_subject_queues(
                SUBJ_UUID, QueueManagementRequest(action="purge"), session, admin_user, broker
            )

        assert result.success is False
        assert result.queue_info == {"purged_queues": ["q_sub-b"], "failed_queues": ["q_sub-a"]}
        assert len(error_records(caplog)) == 1

    async def test_single_purge_success_response_is_unchanged(self, session, admin_user, caplog):
        repo = make_repo(make_subject())

        with patch.object(subject_routes.pr, "SubjectRepository", return_value=repo):
            result = await subject_routes.manage_subject_queues(
                SUBJ_UUID,
                QueueManagementRequest(action="purge"),
                session,
                admin_user,
                make_broker(),
            )

        assert result.success is True
        assert result.message == "Purged 2 queues"
        assert result.queue_info == {"purged_queues": ["q_sub-a", "q_sub-b"]}
        assert error_records(caplog) == []

    async def test_queue_management_catch_all_logs(self, session, admin_user, caplog):
        repo = make_repo(make_subject())
        broker = make_broker()
        broker.delete_queue.side_effect = RuntimeError("boom")

        with (
            patch.object(subject_routes.pr, "SubjectRepository", return_value=repo),
            unshared_queues(),
        ):
            result = await subject_routes.manage_subject_queues(
                SUBJ_UUID,
                QueueManagementRequest(action="delete", queue_name="q_sub-a"),
                session,
                admin_user,
                broker,
            )

        assert result.success is False
        records = error_records(caplog)
        assert len(records) == 1
        assert isinstance(records[0].exc_info[1], RuntimeError)


BROKER_URL = "amqp://host:15672?username=u&password=p"

# One call per decorated RabbitMqService method, with arguments that reach the HTTP layer.
BROKER_CALLS = {
    "create_subscription_subject": ("q_x", "e_x"),
    "create_subscription_subject_with_performance_constraints": ("q_x", "e_x"),
    "delete_subscription_subject": ("q_x",),
    "create_exchange": ("e_x",),
    "delete_exchange": ("e_x",),
    "delete_queue": ("q",),
    "publish_message": ("e_subj", "key", "payload"),
    "get_messages": ("q",),
}


def real_service_failing_at_http(http_error):
    """A RabbitMqService with the real pyrabbit2 client whose HTTP layer raises http_error."""
    service = RabbitMqService(BROKER_URL)
    service._client.http.do_call = Mock(side_effect=http_error)
    return service


class TestRabbitMqErrorTranslation:
    @pytest.mark.parametrize(
        ("http_error", "expected_cause"),
        [
            pytest.param(
                pyrabbit_http.HTTPError({}, status=401, reason="Unauthorized"),
                pyrabbit_api.PermissionError,
                id="http-401",
            ),
            pytest.param(
                pyrabbit_http.HTTPError({}, status=500, reason="Server Error"),
                pyrabbit_http.HTTPError,
                id="http-500",
            ),
            pytest.param(
                pyrabbit_http.NetworkError("unreachable"),
                pyrabbit_http.NetworkError,
                id="network",
            ),
        ],
    )
    @pytest.mark.parametrize("method_name", sorted(BROKER_CALLS))
    def test_real_client_failures_become_broker_error(
        self, method_name, http_error, expected_cause
    ):
        service = real_service_failing_at_http(http_error)

        with pytest.raises(BrokerError) as exc_info:
            getattr(service, method_name)(*BROKER_CALLS[method_name])

        assert type(exc_info.value.__cause__) is expected_cause
        assert method_name in str(exc_info.value)

    def test_every_service_method_is_covered_by_the_cases(self):
        public = {
            name
            for name, value in vars(RabbitMqService).items()
            if callable(value) and not name.startswith("_")
        }

        assert public == set(BROKER_CALLS)

    @pytest.mark.parametrize("bug", [KeyError("bug"), PermissionError("filesystem")])
    def test_unrelated_errors_are_not_translated(self, bug):
        with patch("uudex_server.services.message_services.rabbit_mq.Client") as client_cls:
            client_cls.return_value.delete_exchange.side_effect = bug
            service = RabbitMqService(BROKER_URL)

        with pytest.raises(type(bug)) as exc_info:
            service.delete_exchange("e_x")

        assert exc_info.value is bug

    def test_return_value_passes_through(self):
        with patch("uudex_server.services.message_services.rabbit_mq.Client") as client_cls:
            client_cls.return_value.delete_queue.return_value = True
            service = RabbitMqService(BROKER_URL)

        assert service.delete_queue("q") is True
        client_cls.return_value.delete_queue.assert_called_once_with("/", "q")
