from pathlib import Path

import pytest
from sqlalchemy import inspect

from uudex_server.core.settings import BASE_DIR, Settings, get_settings
from uudex_server.main import app
from uudex_server.services import database_service

CERT_VALUE = "-----BEGIN%20CERTIFICATE-----%0Aplaceholder%0A-----END%20CERTIFICATE-----%0A"


def _write_env(path: Path, header_name: str) -> Path:
    path.write_text(
        f"{header_name}={CERT_VALUE}\n"
        "postgres_dsn=postgresql+asyncpg://user:password@localhost:5432/uudex\n"
        "messagebus_connection=rabbitmq://localhost:15672?username=u&password=p\n",
        encoding="utf-8",
    )
    return path


def test_cert_setting_loads_from_env_file(tmp_path: Path) -> None:
    env_file = _write_env(tmp_path / "settings.env", "X_SSL_CERT")
    settings = Settings(_env_file=str(env_file), _secrets_dir=str(tmp_path / "none"))
    assert settings.x_ssl_cert == CERT_VALUE
    assert settings.db_uri == "postgresql+asyncpg://user:password@localhost:5432/uudex"


def test_dev_fixture_uses_the_same_cert_name() -> None:
    fixture = (BASE_DIR / "tests" / "fixtures" / "dev_env_file").read_text(encoding="utf-8")
    names = {line.split("=", 1)[0] for line in fixture.splitlines() if "=" in line}
    assert "X_SSL_CERT" in names
    assert "X-SSL-CERT" not in names


def test_example_dsn_uses_async_driver() -> None:
    example = (BASE_DIR / "secrets" / "example.postgres_dsn").read_text(encoding="utf-8").strip()
    assert example.startswith("postgresql+asyncpg://")
    assert "psycopg2" not in example


def test_test_env_file_holds_async_placeholders() -> None:
    settings = Settings.get_test_settings()
    assert "psycopg2" not in settings.db_uri
    assert settings.x_ssl_cert


def test_settings_do_not_depend_on_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.x_ssl_cert
    assert settings.db_uri.startswith(("sqlite+aiosqlite:", "postgresql+asyncpg:"))


async def test_lifespan_creates_tables() -> None:
    await database_service.shutdown_db()
    async with database_service.get_engine().begin() as conn:
        await conn.run_sync(database_service.SQLModel.metadata.drop_all)

    async with app.router.lifespan_context(app):
        async with database_service.get_engine().connect() as conn:
            tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))

    assert tables >= set(database_service.SQLModel.metadata.tables)
    assert tables
