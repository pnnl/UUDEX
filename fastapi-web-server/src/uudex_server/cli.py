"""Operator commands, run from inside the server container: `uudex-server bootstrap-admin`.

Nothing imports this module at app startup and no route reaches it; it runs only when an
operator starts the console script.
"""

import argparse
import asyncio
import logging
import sys
import unicodedata
import uuid
from collections.abc import Sequence

from sqlalchemy import text

from uudex_server.core.client_cert import _BAD_CN_CATEGORIES
from uudex_server.models import EndPoint, Participant
from uudex_server.repos.endpoint_repository import EndpointRepository
from uudex_server.services.database_service import get_db_session, shutdown_db

# Serializes concurrent bootstrap runs on PostgreSQL. Arbitrary but fixed; it only has to be
# the same in every run of this command.
_BOOTSTRAP_LOCK_KEY = 0x55554458


class Refused(Exception):
    """The command declined to write anything; the message is safe to print."""


def check_common_name(cn: str) -> None:
    """Apply the CN rules the server applies to a certificate (core.client_cert)."""
    if not cn.strip():
        raise Refused("the common name is empty")
    if cn != cn.strip() or any(unicodedata.category(char) in _BAD_CN_CATEGORIES for char in cn):
        raise Refused("the common name has edge whitespace or control or format characters")


async def bootstrap_admin(cn: str, participant_id: int) -> str:
    """Create the first administrator endpoint and return its uuid.

    The checks and the insert share one transaction, so a refusal or a failure writes no row.
    """
    check_common_name(cn)
    async with get_db_session() as session:
        # PostgreSQL does not serialize two readers that both see no admin; the lock makes the
        # second run wait and then see the first one's row. SQLite serializes writers itself.
        if session.bind.dialect.name == "postgresql":
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": _BOOTSTRAP_LOCK_KEY}
            )
        repo = EndpointRepository(session)
        if await repo.has_any_admin_endpoints():
            raise Refused("an active administrator already exists")
        participant = await session.get(Participant, participant_id)
        if participant is None or participant.active_sw != "Y":
            raise Refused(f"participant {participant_id} does not exist or is not active")
        # No database constraint keeps certificate_dn unique yet (pnnl/UUDEX#46).
        if await repo.certificate_dn_exists(cn):
            raise Refused("an endpoint with that certificate DN already exists")
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


async def _run(cn: str, participant_id: int) -> str:
    try:
        return await bootstrap_admin(cn, participant_id)
    finally:
        await shutdown_db()


def _quiet_logging() -> None:
    """Undo the import-time root logger setup in core.logger.

    That module sends DEBUG output, SQL statements and their parameters included, to stdout. An
    operator command prints only its result on stdout and nothing below a warning at all.
    """
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(logging.StreamHandler(sys.stderr))
    root.setLevel(logging.WARNING)


def main(argv: Sequence[str] | None = None) -> int:
    _quiet_logging()
    args = _parser().parse_args(argv)
    try:
        endpoint_uuid = asyncio.run(_run(args.cn, args.participant_id))
    except Refused as refusal:
        print(f"uudex-server: refused: {refusal}", file=sys.stderr)
        return 1
    except Exception as error:
        # Only the type is printed: settings and driver errors can quote the DSN or its password.
        print(
            f"uudex-server: failed: could not read the settings or use the database "
            f"({type(error).__name__}); nothing was written",
            file=sys.stderr,
        )
        return 1
    print(endpoint_uuid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
