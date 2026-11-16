import ipaddress
import json
import logging
import os
import sys
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field, IPvAnyAddress, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

# Resolved from this file so settings load the same from any working directory.
BASE_DIR = Path(__file__).resolve().parents[3]


def _resolve(path: str | Path) -> Path:
    """Anchor a relative settings path at BASE_DIR, not the current directory."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else BASE_DIR / candidate


def _is_development() -> bool:
    return os.environ.get("DEV", "").lower() in ("true", "1", "yes")


def _anchor_sqlite(dsn: str) -> str:
    """Make a relative SQLite file path absolute so no database lands in the cwd."""
    url = make_url(dsn)
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        url = url.set(database=str(_resolve(url.database)))
    return url.render_as_string(hide_password=False)


def _check_trusted_host(index: int, entry: object) -> None:
    """Refuse an entry that would load as a different address or could never match a peer."""
    where = f"trusted_proxy_hosts entry {index}"
    # A number or boolean would be read as an address; only a quoted string is one.
    if not isinstance(entry, str):
        raise ValueError(f"{where} must be an IP address written as a JSON string")
    # The gate compares unscoped addresses, so a scope id (fe80::1%eth0) never matches.
    if "%" in entry:
        raise ValueError(f"{where} must not carry an IPv6 scope id")
    try:
        address = ipaddress.ip_address(entry)
    except ValueError:
        return  # the address type reports the malformed entry
    # Peers reported as ::ffff:a.b.c.d are matched by their IPv4 form, so a mapped entry
    # never matches. Refused rather than rewritten, so the operator sees the setting is wrong.
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        raise ValueError(f"{where} is an IPv4-mapped IPv6 address; write the IPv4 address")


class Settings(BaseSettings):
    x_ssl_cert: str
    db_uri: str = Field(alias="postgres_dsn")
    messagebus_connection: str
    # Peers allowed to supply the identity headers. Empty trusts no peer, so every
    # non-public request is refused. Set as a JSON list, for example '["172.29.77.20"]'.
    trusted_proxy_hosts: list[IPvAnyAddress] = Field(default_factory=list)

    @field_validator("trusted_proxy_hosts", mode="before")
    @classmethod
    def _check_trusted_hosts(cls, value: object) -> object:
        # The test loader passes the raw file text; the environment sources decode it already.
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, list):
            raise ValueError("trusted_proxy_hosts must be a JSON list of IP address strings")
        for index, entry in enumerate(value):
            _check_trusted_host(index, entry)
        return value

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )

    @classmethod
    def get_test_settings(cls) -> "Settings":
        """Settings for tests: values come only from tests/.env.test, never the environment."""
        values = {
            key.lower(): value
            for key, value in dotenv_values(BASE_DIR / "tests" / ".env.test").items()
            if value is not None
        }
        values["postgres_dsn"] = _anchor_sqlite(values["postgres_dsn"])
        return cls(**values)


def _select_env_file(env_file: str | None) -> Path | None:
    """A file named by argument or UUDEX_SETTINGS must exist; the defaults are optional."""
    named = env_file or os.environ.get("UUDEX_SETTINGS")
    if named:
        path = _resolve(named)
        if not path.is_file():
            source = "env_file argument" if env_file else "UUDEX_SETTINGS"
            raise ValueError(f"Settings file not found: {path} (named by {source})")
        return path
    defaults = [".env-develop", ".env"] if _is_development() else [".env"]
    return next((BASE_DIR / name for name in defaults if (BASE_DIR / name).is_file()), None)


def _select_secrets_dir() -> Path | None:
    named = os.environ.get("UUDEX_SECRETS_DIR")
    if named:
        path = _resolve(named)
        if not path.is_dir():
            raise ValueError(f"Secrets directory not found: {path} (named by UUDEX_SECRETS_DIR)")
        return path
    default = BASE_DIR / "secrets"
    return default if default.is_dir() else None


@lru_cache
def get_settings(env_file: str | None = None) -> Settings:
    """Load settings. Precedence: environment variables, then the env file, then the
    secrets directory, then defaults."""
    if "pytest" in sys.modules:
        return Settings.get_test_settings()

    path = _select_env_file(env_file)
    secrets_dir = _select_secrets_dir()
    logger.info(f"Loading settings from: {path or 'environment'}")
    return Settings(_env_file=path, _secrets_dir=secrets_dir)  # type: ignore[call-arg]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print(sorted(get_settings().model_dump()))
