import logging
import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Resolved from this file so settings load the same from any working directory.
BASE_DIR = Path(__file__).resolve().parents[3]

SETTINGS_FILE = Path(os.environ.get("UUDEX_SETTINGS", BASE_DIR / ".env"))
SECRETS_DIR = Path(os.environ.get("UUDEX_SECRETS_DIR", BASE_DIR / "secrets"))

# Check for development environment
IS_DEVELOPMENT = os.environ.get("DEV", "").lower() in ("true", "1", "yes")


def _resolve(path: str | Path) -> Path:
    """Anchor a relative settings path at BASE_DIR, not the current directory."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else BASE_DIR / candidate


class Settings(BaseSettings):
    x_ssl_cert: str
    db_uri: str = Field(alias="postgres_dsn")
    messagebus_connection: str

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / (".env-develop" if IS_DEVELOPMENT else ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
        secrets_dir=SECRETS_DIR,  # Each file in this directory becomes an env var
    )

    @classmethod
    def get_test_settings(cls) -> "Settings":
        """Get settings configured for testing"""
        return cls(
            _env_file=BASE_DIR / "tests" / ".env.test",
            _env_file_encoding="utf-8",
            _secrets_dir=BASE_DIR / "tests" / "no-secrets",
        )


@lru_cache
def get_settings(env_file: str | None = None) -> Settings:
    """Get settings instance, optionally with specific env file"""
    if "pytest" in sys.modules:
        return Settings.get_test_settings()

    # Priority:
    # 1. Explicitly passed env_file
    # 2. UUDEX_SETTINGS environment variable
    # 3. .env-develop if DEV=True
    # 4. .env
    path = _resolve(env_file) if env_file else _resolve(SETTINGS_FILE)

    if not path.exists():
        if IS_DEVELOPMENT and (BASE_DIR / ".env-develop").exists():
            path = BASE_DIR / ".env-develop"
        elif (BASE_DIR / ".env").exists():
            path = BASE_DIR / ".env"
        else:
            raise ValueError(
                f"Settings file not found: {path}\n"
                "Ensure either UUDEX_SETTINGS points to a valid file, "
                "or .env-develop (in dev mode) or .env exists"
            )

    logger.info(f"Loading settings from: {path}")
    return Settings(_env_file=path, _secrets_dir=SECRETS_DIR)


__settings__: Settings | None = None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    settings = get_settings()
    print(settings.model_dump())

    print(f"ENV['DEV'] -> {os.environ.get('DEV')}")
