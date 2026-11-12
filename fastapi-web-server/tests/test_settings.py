import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect

from uudex_server import main as main_module
from uudex_server.core import settings as settings_module
from uudex_server.core.settings import BASE_DIR, Settings
from uudex_server.main import app
from uudex_server.services import database_service

ASYNC_SCHEMES = ("postgresql+asyncpg", "sqlite+aiosqlite")
CERT_VALUE = "-----BEGIN%20CERTIFICATE-----%0Aplaceholder%0A-----END%20CERTIFICATE-----%0A"
SENTINEL = "sentinel-secret-7f3a"
DSN = "postgresql+asyncpg://user:password@localhost:5432/uudex"
BUS = "rabbitmq://localhost:15672?username=u&password=p"

PROBE = (
    "from uudex_server.core.settings import get_settings\n"
    "s = get_settings()\n"
    "print('CERT=' + s.x_ssl_cert)\n"
    "print('DSN=' + s.db_uri)\n"
)


def _scheme(dsn: str) -> str:
    return dsn.split("://", 1)[0]


def _run(code: str, cwd: Path, **env: str) -> subprocess.CompletedProcess[str]:
    """Run code in a fresh interpreter (no pytest loaded) from another directory."""
    base = {"PATH": os.environ["PATH"], "PYTHONPATH": str(BASE_DIR / "src")}
    if "PYTHONPYCACHEPREFIX" in os.environ:
        base["PYTHONPYCACHEPREFIX"] = os.environ["PYTHONPYCACHEPREFIX"]
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env={**base, **env},
        capture_output=True,
        text=True,
        timeout=60,
    )


def _values(probe: subprocess.CompletedProcess[str]) -> dict[str, str]:
    assert probe.returncode == 0, probe.stdout + probe.stderr
    return dict(line.split("=", 1) for line in probe.stdout.splitlines() if "=" in line)


def _write_env(path: Path, header_name: str = "X_SSL_CERT", dsn: str = DSN) -> Path:
    path.write_text(
        f"{header_name}={CERT_VALUE}\npostgres_dsn={dsn}\nmessagebus_connection={BUS}\n",
        encoding="utf-8",
    )
    return path


def _secrets(path: Path, dsn: str = DSN) -> Path:
    path.mkdir()
    (path / "postgres_dsn").write_text(dsn, encoding="utf-8")
    (path / "messagebus_connection").write_text(BUS, encoding="utf-8")
    return path


def test_cert_setting_loads_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("POSTGRES_DSN", "X_SSL_CERT", "MESSAGEBUS_CONNECTION"):
        monkeypatch.delenv(name, raising=False)
    env_file = _write_env(tmp_path / "settings.env")
    settings = Settings(_env_file=str(env_file), _secrets_dir=None)
    assert settings.x_ssl_cert == CERT_VALUE
    assert settings.db_uri == DSN


def test_dev_fixture_uses_the_same_cert_name() -> None:
    fixture = (BASE_DIR / "tests" / "fixtures" / "dev_env_file").read_text(encoding="utf-8")
    names = {line.split("=", 1)[0] for line in fixture.splitlines() if "=" in line}
    assert "X_SSL_CERT" in names
    assert "X-SSL-CERT" not in names


def test_example_dsn_uses_async_driver() -> None:
    example = (BASE_DIR / "secrets" / "example.postgres_dsn").read_text(encoding="utf-8").strip()
    assert _scheme(example) in ASYNC_SCHEMES


def test_test_settings_use_async_driver() -> None:
    assert _scheme(Settings.get_test_settings().db_uri) in ASYNC_SCHEMES


def test_test_settings_ignore_the_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql+asyncpg://real:real@prod:5432/real")
    monkeypatch.setenv("X_SSL_CERT", "from-the-environment")
    settings = Settings.get_test_settings()
    assert _scheme(settings.db_uri) == "sqlite+aiosqlite"
    assert settings.x_ssl_cert != "from-the-environment"


def test_test_database_path_is_absolute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    path = Settings.get_test_settings().db_uri.split(":///", 1)[1]
    assert Path(path).is_absolute()
    assert Path(path).parent == BASE_DIR / "tests"


def test_named_file_and_secrets_dir_load_from_another_directory(tmp_path: Path) -> None:
    env_file = _write_env(tmp_path / "named.env", dsn="sqlite+aiosqlite:///x.db")
    secrets = _secrets(tmp_path / "sec")
    other = tmp_path / "elsewhere"
    other.mkdir()
    got = _values(_run(PROBE, other, UUDEX_SETTINGS=str(env_file), UUDEX_SECRETS_DIR=str(secrets)))
    assert got["CERT"] == CERT_VALUE
    assert got["DSN"] == "sqlite+aiosqlite:///x.db"


def test_secrets_directory_alone_supplies_the_dsn(tmp_path: Path) -> None:
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    secrets = _secrets(tmp_path / "sec")
    got = _values(
        _run(
            PROBE,
            tmp_path,
            UUDEX_SETTINGS=str(empty),
            UUDEX_SECRETS_DIR=str(secrets),
            X_SSL_CERT=CERT_VALUE,
        )
    )
    assert got["DSN"] == DSN
    assert _scheme(got["DSN"]) in ASYNC_SCHEMES


def test_default_secrets_dir_is_not_taken_from_the_current_directory(tmp_path: Path) -> None:
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    _secrets(tmp_path / "secrets", dsn=f"sqlite+aiosqlite:///{SENTINEL}.db")
    probe = _run(
        PROBE, tmp_path, UUDEX_SETTINGS=str(empty), X_SSL_CERT=CERT_VALUE, messagebus_connection=BUS
    )
    assert SENTINEL not in probe.stdout


def test_environment_alone_starts_with_no_file(tmp_path: Path) -> None:
    got = _values(
        _run(
            PROBE,
            tmp_path,
            X_SSL_CERT=CERT_VALUE,
            postgres_dsn=DSN,
            messagebus_connection=BUS,
            UUDEX_SECRETS_DIR=str(tmp_path),
        )
    )
    assert got["DSN"] == DSN


def test_environment_beats_file_and_file_beats_secrets(tmp_path: Path) -> None:
    file_dsn = "sqlite+aiosqlite:///from-file.db"
    env_file = _write_env(tmp_path / "named.env", dsn=file_dsn)
    secrets = _secrets(tmp_path / "sec", dsn="sqlite+aiosqlite:///from-secrets.db")
    common = {"UUDEX_SETTINGS": str(env_file), "UUDEX_SECRETS_DIR": str(secrets)}
    assert _values(_run(PROBE, tmp_path, **common))["DSN"] == file_dsn
    env_dsn = "sqlite+aiosqlite:///from-env.db"
    assert _values(_run(PROBE, tmp_path, postgres_dsn=env_dsn, **common))["DSN"] == env_dsn


def test_missing_named_settings_file_is_an_error(tmp_path: Path) -> None:
    missing = tmp_path / "prod.env"
    probe = _run(PROBE, tmp_path, UUDEX_SETTINGS=str(missing), postgres_dsn=DSN)
    assert probe.returncode != 0
    assert str(missing) in probe.stderr


def test_named_file_never_falls_back_to_the_default_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_env(tmp_path / ".env")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)
    monkeypatch.setenv("UUDEX_SETTINGS", "prod.env")
    with pytest.raises(ValueError, match="prod.env"):
        settings_module._select_env_file(None)
    with pytest.raises(ValueError, match="other.env"):
        settings_module._select_env_file("other.env")
    monkeypatch.delenv("UUDEX_SETTINGS")
    assert settings_module._select_env_file(None) == tmp_path / ".env"


def test_relative_settings_file_is_anchored_at_the_package(tmp_path: Path) -> None:
    probe = _run(PROBE, tmp_path, UUDEX_SETTINGS="no-such-file.env")
    assert probe.returncode != 0
    assert str(BASE_DIR / "no-such-file.env") in probe.stderr


def test_missing_named_secrets_dir_is_an_error(tmp_path: Path) -> None:
    probe = _run(PROBE, tmp_path, UUDEX_SECRETS_DIR="no-such-secrets", X_SSL_CERT="x")
    assert probe.returncode != 0
    assert str(BASE_DIR / "no-such-secrets") in probe.stderr


def test_invalid_settings_log_field_names_not_values(tmp_path: Path) -> None:
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    probe = _run(
        "import uudex_server.main",
        tmp_path,
        UUDEX_SETTINGS=str(empty),
        UUDEX_SECRETS_DIR=str(tmp_path),
        postgres_dsn=DSN,
        messagebus_connection=f"rabbitmq://h?password={SENTINEL}",
    )
    output = probe.stdout + probe.stderr
    assert probe.returncode != 0
    assert "x_ssl_cert" in output
    assert SENTINEL not in output


@pytest.fixture
def temp_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Point the database service at a throwaway SQLite file, whatever the environment says."""
    dsn = f"sqlite+aiosqlite:///{tmp_path / 'lifespan.db'}"
    monkeypatch.setattr(database_service, "get_settings", lambda: SimpleNamespace(db_uri=dsn))
    monkeypatch.setattr(database_service, "_engine", None)
    monkeypatch.setattr(database_service, "_async_session", None)
    return dsn


async def _table_names() -> set[str]:
    async with database_service.get_engine().connect() as conn:
        return await conn.run_sync(lambda c: set(inspect(c).get_table_names()))


async def test_lifespan_creates_tables(temp_database: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql+asyncpg://real:real@prod:5432/real")
    async with app.router.lifespan_context(app):
        tables = await _table_names()
        assert str(database_service.get_engine().url).startswith(temp_database.split(":///")[0])

    assert tables
    assert tables == set(database_service.SQLModel.metadata.tables)


async def test_second_lifespan_binds_sessions_to_the_new_engine(temp_database: str) -> None:
    async with app.router.lifespan_context(app):
        database_service.get_async_session()
    assert database_service._engine is None
    assert database_service._async_session is None

    async with app.router.lifespan_context(app):
        bind = database_service.get_async_session().kw["bind"]
        assert bind is database_service.get_engine()


async def test_failed_startup_still_disposes_the_engine(
    temp_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_init() -> None:
        database_service.get_engine()
        raise RuntimeError("create_all failed")

    monkeypatch.setattr(main_module, "init_db", failing_init)
    with pytest.raises(RuntimeError):
        async with app.router.lifespan_context(app):
            pass
    assert database_service._engine is None


def test_example_env_file_loads_with_placeholders_and_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("POSTGRES_DSN", "X_SSL_CERT", "MESSAGEBUS_CONNECTION"):
        monkeypatch.delenv(name, raising=False)
    secrets = _secrets(tmp_path / "sec")
    settings = Settings(_env_file=str(BASE_DIR / ".env.example"), _secrets_dir=str(secrets))
    assert settings.x_ssl_cert
    assert settings.db_uri == DSN
