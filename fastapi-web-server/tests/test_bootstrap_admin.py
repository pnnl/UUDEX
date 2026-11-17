"""`uudex-server bootstrap-admin` creates the first administrator, and only the first."""

import asyncio
import os
import subprocess
import sys
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel, select

import uudex_server.models as m
from uudex_server.cli import Refused, check_common_name

SECRET = "topsecretpw"
CONSOLE_SCRIPT = Path(sys.executable).parent / "uudex-server"


class Database:
    """A SQLite file the command under test reaches through the settings, as in production."""

    def __init__(self, path: Path) -> None:
        self.dsn = f"sqlite+aiosqlite:///{path}"

    def run(self, work: Callable[[AsyncSession], object]) -> object:
        async def go() -> object:
            engine = create_async_engine(self.dsn)
            try:
                async with AsyncSession(engine, expire_on_commit=False) as session:
                    result = await work(session)
                    await session.commit()
                    return result
            finally:
                await engine.dispose()

        return asyncio.run(go())

    def create_tables(self) -> None:
        async def go() -> None:
            engine = create_async_engine(self.dsn)
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
            await engine.dispose()

        asyncio.run(go())

    def add_participant(self, *, active: bool = True, active_sw: str | None = None) -> int:
        async def work(session: AsyncSession) -> int:
            participant = m.Participant(
                participant_uuid=str(uuid.uuid4()),
                participant_short_name="p",
                participant_long_name="p",
                root_org_sw="N",
                active_sw=active_sw or ("Y" if active else "N"),
                create_datetime=None,
            )
            session.add(participant)
            await session.flush()
            return participant.participant_id

        return self.run(work)

    def add_endpoint(
        self,
        cn: str,
        participant_id: int,
        *,
        admin: bool,
        active: bool = True,
        active_sw: str | None = None,
    ):
        """Seed an endpoint; active_sw stores exactly that text when given."""

        async def work(session: AsyncSession) -> None:
            session.add(
                m.EndPoint(
                    endpoint_uuid=str(uuid.uuid4()),
                    endpoint_user_name=cn,
                    certificate_dn=cn,
                    description="seeded",
                    uudex_administrator_sw="Y" if admin else "N",
                    participant_administrator_sw="Y" if admin else "N",
                    active_sw=active_sw or ("Y" if active else "N"),
                    participant_id=participant_id,
                    create_datetime=None,
                )
            )

        self.run(work)

    def endpoints(self) -> list[m.EndPoint]:
        async def work(session: AsyncSession) -> list[m.EndPoint]:
            return list((await session.execute(select(m.EndPoint))).scalars().all())

        return self.run(work)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "bootstrap.db")
    database.create_tables()
    return database


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the project's own .env and secrets directory out of every subprocess."""
    settings_file = tmp_path / "empty.env"
    settings_file.write_text("")
    secrets_dir = tmp_path / "empty-secrets"
    secrets_dir.mkdir()
    monkeypatch.setenv("UUDEX_SETTINGS", str(settings_file))
    monkeypatch.setenv("UUDEX_SECRETS_DIR", str(secrets_dir))


def settings_env(dsn: str) -> dict[str, str]:
    """The only environment the subprocess gets: the settings the server requires.

    UUDEX_SETTINGS and UUDEX_SECRETS_DIR point at empty paths, so a developer's own .env or
    secrets directory cannot change what a test sees.
    """
    return {
        "PATH": str(CONSOLE_SCRIPT.parent),
        "UUDEX_SETTINGS": os.environ["UUDEX_SETTINGS"],
        "UUDEX_SECRETS_DIR": os.environ["UUDEX_SECRETS_DIR"],
        "POSTGRES_DSN": dsn,
        "X_SSL_CERT": "placeholder",
        "MESSAGEBUS_CONNECTION": f"amqp://user:{SECRET}@127.0.0.1:1/",
    }


def run_command(dsn: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the console script as an operator would, with only the settings it needs."""
    assert CONSOLE_SCRIPT.exists(), f"console script not installed: {CONSOLE_SCRIPT}"
    return subprocess.run(
        [str(CONSOLE_SCRIPT), "bootstrap-admin", *args],
        capture_output=True,
        text=True,
        env=settings_env(dsn),
        cwd="/",
        timeout=120,
        check=False,
    )


def test_two_runs_started_together_create_exactly_one_admin(db: Database) -> None:
    participant_id = db.add_participant()
    assert CONSOLE_SCRIPT.exists(), f"console script not installed: {CONSOLE_SCRIPT}"

    runs = [
        subprocess.Popen(
            [str(CONSOLE_SCRIPT), "bootstrap-admin", "--cn", cn, "--participant-id"]
            + [str(participant_id)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=settings_env(db.dsn),
            cwd="/",
        )
        for cn in ("admin-a", "admin-b")
    ]
    outputs = [run.communicate(timeout=120) for run in runs]

    codes = sorted(run.returncode for run in runs)
    assert codes == [0, 1], outputs
    refused = [err for _, err in outputs if "refused" in err]
    assert len(refused) == 1
    assert "an active administrator already exists" in refused[0]
    rows = db.endpoints()
    assert len(rows) == 1
    assert rows[0].uudex_administrator_sw == "Y"
    assert rows[0].active_sw == "Y"


def assert_refused(result: subprocess.CompletedProcess[str], message: str) -> None:
    assert result.returncode == 1
    assert result.stdout == ""
    assert "refused" in result.stderr
    assert message in result.stderr
    assert SECRET not in result.stdout + result.stderr


def test_first_run_creates_an_admin_and_the_second_run_refuses(db: Database) -> None:
    participant_id = db.add_participant()

    first = run_command(db.dsn, "--cn", "first-admin", "--participant-id", str(participant_id))

    assert first.returncode == 0, first.stderr
    assert first.stderr == ""
    rows = db.endpoints()
    assert len(rows) == 1
    row = rows[0]
    assert first.stdout.strip() == row.endpoint_uuid
    assert str(uuid.UUID(row.endpoint_uuid)) == row.endpoint_uuid
    assert row.certificate_dn == "first-admin"
    assert row.endpoint_user_name == "first-admin"
    assert row.uudex_administrator_sw == "Y"
    assert row.participant_administrator_sw == "Y"
    assert row.active_sw == "Y"
    assert row.participant_id == participant_id
    assert row.create_datetime is not None
    assert SECRET not in first.stdout + first.stderr

    second = run_command(db.dsn, "--cn", "second-admin", "--participant-id", str(participant_id))

    assert_refused(second, "an active administrator already exists")
    assert [(e.endpoint_uuid, e.certificate_dn) for e in db.endpoints()] == [
        (row.endpoint_uuid, "first-admin")
    ]


def test_an_inactive_admin_does_not_block_the_first_active_one(db: Database) -> None:
    participant_id = db.add_participant()
    db.add_endpoint("retired", participant_id, admin=True, active=False)

    result = run_command(db.dsn, "--cn", "new-admin", "--participant-id", str(participant_id))

    assert result.returncode == 0, result.stderr
    by_cn = {e.certificate_dn: e for e in db.endpoints()}
    assert set(by_cn) == {"retired", "new-admin"}
    assert by_cn["retired"].active_sw == "N"
    assert by_cn["new-admin"].uudex_administrator_sw == "Y"
    assert by_cn["new-admin"].active_sw == "Y"


def test_refuses_when_an_active_admin_was_seeded_directly(db: Database) -> None:
    participant_id = db.add_participant()
    db.add_endpoint("existing-admin", participant_id, admin=True)
    before = [e.endpoint_uuid for e in db.endpoints()]

    result = run_command(db.dsn, "--cn", "other", "--participant-id", str(participant_id))

    assert_refused(result, "an active administrator already exists")
    assert [e.endpoint_uuid for e in db.endpoints()] == before


def test_refuses_when_the_active_switch_is_lower_case(db: Database) -> None:
    # Login compares the switch case-insensitively, so this admin can log in. The admin switch
    # is an enum column that stores only Y or N, so only the active switch can differ in case.
    participant_id = db.add_participant()
    db.add_endpoint("lower-admin", participant_id, admin=True, active_sw="y")
    before = [e.endpoint_uuid for e in db.endpoints()]

    result = run_command(db.dsn, "--cn", "other", "--participant-id", str(participant_id))

    assert_refused(result, "an active administrator already exists")
    assert [e.endpoint_uuid for e in db.endpoints()] == before


def test_a_lower_case_inactive_admin_does_not_block_the_first_active_one(db: Database) -> None:
    participant_id = db.add_participant()
    db.add_endpoint("retired", participant_id, admin=True, active_sw="n")

    result = run_command(db.dsn, "--cn", "new-admin", "--participant-id", str(participant_id))

    assert result.returncode == 0, result.stderr
    assert {e.certificate_dn for e in db.endpoints()} == {"retired", "new-admin"}


def test_a_participant_whose_active_switch_is_lower_case_is_active(db: Database) -> None:
    participant_id = db.add_participant(active_sw="y")

    result = run_command(db.dsn, "--cn", "an-admin", "--participant-id", str(participant_id))

    assert result.returncode == 0, result.stderr
    assert [e.certificate_dn for e in db.endpoints()] == ["an-admin"]


@pytest.mark.parametrize("state", ["missing", "inactive"])
def test_refuses_a_participant_that_is_missing_or_inactive(db: Database, state: str) -> None:
    participant_id = 9999 if state == "missing" else db.add_participant(active=False)

    result = run_command(db.dsn, "--cn", "an-admin", "--participant-id", str(participant_id))

    assert_refused(result, f"participant {participant_id} does not exist or is not active")
    assert db.endpoints() == []


def test_refuses_a_certificate_dn_that_is_already_taken(db: Database) -> None:
    participant_id = db.add_participant()
    db.add_endpoint("taken", participant_id, admin=False)
    before = [e.endpoint_uuid for e in db.endpoints()]

    result = run_command(db.dsn, "--cn", "taken", "--participant-id", str(participant_id))

    assert_refused(result, "an endpoint with that certificate DN already exists")
    after = db.endpoints()
    assert [e.endpoint_uuid for e in after] == before
    assert after[0].uudex_administrator_sw == "N"


EMPTY_CN = "the common name is empty"
BAD_CN = "the common name has edge whitespace or control or format characters"


@pytest.mark.parametrize(
    ("cn", "reason"),
    [
        ("", EMPTY_CN),
        ("   ", EMPTY_CN),
        (" padded", BAD_CN),
        ("padded ", BAD_CN),
        ("tab\there", BAD_CN),
        ("new\nline", BAD_CN),
        ("zero\u200bwidth", BAD_CN),
    ],
    ids=["empty", "blank", "leading", "trailing", "tab", "newline", "format-char"],
)
def test_refuses_a_common_name_the_server_would_refuse(db: Database, cn: str, reason: str) -> None:
    participant_id = db.add_participant()

    result = run_command(db.dsn, "--cn", cn, "--participant-id", str(participant_id))

    assert_refused(result, reason)
    assert db.endpoints() == []


def test_a_nul_in_the_common_name_is_refused() -> None:
    # An operating system cannot pass a NUL in an argument, so the check is called directly.
    with pytest.raises(Refused, match="control or format"):
        check_common_name("nul\x00byte")


def test_an_unreachable_database_fails_without_printing_the_secret() -> None:
    dsn = f"postgresql+asyncpg://user:{SECRET}@127.0.0.1:1/uudex"

    result = run_command(dsn, "--cn", "an-admin", "--participant-id", "1")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "failed" in result.stderr
    assert "nothing was written" in result.stderr
    assert SECRET not in result.stdout + result.stderr


def test_missing_arguments_are_a_usage_error(db: Database) -> None:
    result = run_command(db.dsn, "--cn", "an-admin")

    assert result.returncode == 2
    assert "--participant-id" in result.stderr
    assert db.endpoints() == []


def test_nothing_at_app_startup_imports_the_command(db: Database) -> None:
    code = "import sys, uudex_server.main; print('uudex_server.cli' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=settings_env(db.dsn),
        cwd="/",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == "False"
