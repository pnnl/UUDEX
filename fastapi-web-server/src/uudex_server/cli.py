"""Operator commands, run from inside the server container: `uudex-server bootstrap-admin`.

Nothing imports this module at app startup and no route reaches it; it runs only when an
operator starts the console script.
"""

import argparse
import asyncio
import logging
import sys
import uuid
from collections.abc import Sequence

from pydantic import ValidationError
from sqlalchemy import text

from uudex_server.core import client_cert
from uudex_server.core.settings import get_settings
from uudex_server.models import EndPoint, Participant
from uudex_server.repos.endpoint_repository import EndpointRepository
from uudex_server.services.database_service import get_db_session, shutdown_db

__all__ = ["Refused", "bootstrap_admin", "check_common_name", "main"]

# Serializes concurrent bootstrap runs on PostgreSQL. Arbitrary but fixed; it only has to be
# the same in every run of this command.
_BOOTSTRAP_LOCK_KEY = 0x55554458


class Refused(Exception):
    """The command declined to write anything; the message is safe to print."""


class Progress:
    """The step a run has reached, so a failure can say what it was doing and what it left."""

    stage = "settings"


# What to tell the operator for an unexpected failure, by the stage it happened in. The text is
# fixed: settings and driver errors can quote the DSN or its password, so none is ever printed.
_FAILURES = {
    "settings": "could not load the settings; nothing was written",
    "connecting": "could not connect to the database; nothing was written",
    "checking": (
        "could not read the existing endpoints and participant (is the schema created, is "
        "the database locked?); nothing was written"
    ),
    "writing": (
        "failed while writing the administrator; the outcome is unknown: look for an endpoint "
        "with that certificate DN before running again"
    ),
    "closing": (
        "failed after the administrator was written, while closing the database; the outcome "
        "is unknown: look for an endpoint with that certificate DN before running again"
    ),
}


def check_common_name(cn: str) -> None:
    """Apply the CN rules the server applies to a certificate, as a refusal."""
    try:
        client_cert.check_common_name(cn)
    except client_cert.ClientCertError as error:
        if error.reason == "no_cn":
            raise Refused("the common name is empty") from None
        raise Refused(
            "the common name has edge whitespace or control or format characters"
        ) from None


async def bootstrap_admin(cn: str, participant_id: int, progress: Progress | None = None) -> str:
    """Create the first administrator endpoint and return its uuid.

    The checks and the insert share one transaction, so a refusal or a failure writes no row.
    """
    progress = progress or Progress()
    check_common_name(cn)
    progress.stage = "settings"
    get_settings()
    progress.stage = "connecting"
    async with get_db_session() as session:
        await session.connection()
        progress.stage = "checking"
        # Two runs must not both see "no administrator". Each backend takes a lock before the
        # checks, so the second run waits and then sees the first one's row.
        dialect = session.bind.dialect.name
        if dialect == "sqlite":
            # A SQLite transaction takes the write lock only at its first write, which is after
            # the checks, so take it now. A waiting run gives up after the driver's timeout.
            await session.execute(text("BEGIN IMMEDIATE"))
        elif dialect == "postgresql":
            # UNVERIFIED (#39): no test runs this branch; there is no PostgreSQL test setup yet.
            # READ COMMITTED gives the checks a fresh snapshot after the lock wait, so they see
            # the first run's row; REPEATABLE READ would keep a snapshot taken before the wait.
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BOOTSTRAP_LOCK_KEY}
            )
        repo = EndpointRepository(session)
        if await repo.has_any_admin_endpoints():
            raise Refused("an active administrator already exists")
        participant = await session.get(Participant, participant_id)
        if participant is None or participant.active_sw.upper() != "Y":
            raise Refused(f"participant {participant_id} does not exist or is not active")
        # No database constraint keeps certificate_dn unique yet (pnnl/UUDEX#46).
        if await repo.certificate_dn_exists(cn):
            raise Refused("an endpoint with that certificate DN already exists")
        progress.stage = "writing"
        endpoint = EndPoint(
            endpoint_uuid=str(uuid.uuid4()),
            endpoint_user_name=cn,
            certificate_dn=cn,
            description="First administrator, created by bootstrap-admin",
            uudex_administrator_sw="Y",
            participant_administrator_sw="Y",
            active_sw="Y",
            participant_id=participant_id,
            create_datetime=None,
        )
        session.add(endpoint)
    progress.stage = "closing"
    return endpoint.endpoint_uuid


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uudex-server")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser(
        "bootstrap-admin",
        help="create the first administrator; refuses when an active administrator exists",
    )
    bootstrap.add_argument("--cn", required=True, help="common name of the administrator")
    bootstrap.add_argument(
        "--participant-id", required=True, type=int, help="id of an active participant"
    )
    return parser


async def _run(cn: str, participant_id: int, progress: Progress) -> str:
    try:
        return await bootstrap_admin(cn, participant_id, progress)
    finally:
        await shutdown_db()


def _quiet_logging() -> None:
    """Undo the import-time root logger setup in core.logger.

    That module sends DEBUG output, SQL statements and their parameters included, to stdout. An
    operator command prints only its result on stdout and nothing below a warning on stderr,
    except the one line that names the settings source.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("uudex-server: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.WARNING)
    # The settings loader logs which file it read, a path and no secret: the operator needs it
    # to know which database received the administrator.
    logging.getLogger("uudex_server.core.settings").setLevel(logging.INFO)


def _failure_message(error: Exception, stage: str) -> str:
    message = f"uudex-server: failed: {_FAILURES[stage]} ({type(error).__name__})"
    if stage == "settings" and isinstance(error, ValidationError):
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        message += f"; invalid or missing: {', '.join(fields)}"
    return message


def main(argv: Sequence[str] | None = None) -> int:
    _quiet_logging()
    args = _parser().parse_args(argv)
    progress = Progress()
    try:
        endpoint_uuid = asyncio.run(_run(args.cn, args.participant_id, progress))
    except Refused as refusal:
        print(f"uudex-server: refused: {refusal}", file=sys.stderr)
        return 1
    except Exception as error:
        print(_failure_message(error, progress.stage), file=sys.stderr)
        return 1
    print(endpoint_uuid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
