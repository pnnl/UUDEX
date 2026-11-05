import logging
import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Get settings file from UUDEX_SETTINGS env var, fallback to .env
SETTINGS_FILE = Path(os.environ.get("UUDEX_SETTINGS", ".env")).resolve().as_posix()

# Check for development environment
IS_DEVELOPMENT = os.environ.get("DEV", "").lower() in ("true", "1", "yes")


class Settings(BaseSettings):
    # dev: bool = Field(alias="DEV", default=False)
    x_ssl_cert: str = Field(alias="X-SSL-CERT")
    db_uri: str = Field(alias="postgres_dsn")
    messagebus_connection: str = Field(alias="messagebus_connection")

    model_config = SettingsConfigDict(
        env_file=".env-develop" if IS_DEVELOPMENT else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
        secrets_dir="secrets",  # Each file in this directory becomes an env var
    )

    @classmethod
    def get_test_settings(cls) -> "Settings":
        """Get settings configured for testing"""
        return cls(_env_file="tests/.env.test", _env_file_encoding="utf-8")


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
    if env_file:
        path = Path(env_file)
    else:
        path = Path(SETTINGS_FILE)

    if not path.exists():
        if IS_DEVELOPMENT and Path(".env-develop").exists():
            path = Path(".env-develop")
        elif Path(".env").exists():
            path = Path(".env")
        else:
            raise ValueError(
                f"Settings file not found: {path}\n"
                "Ensure either UUDEX_SETTINGS points to a valid file, "
                "or .env-develop (in dev mode) or .env exists"
            )

    logger.info(f"Loading settings from: {path}")
    return Settings(_env_file=str(path), _secrets_dir="secrets")


__settings__: Settings | None = None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    settings = get_settings()
    print(settings.model_dump())

    print(f"ENV['DEV'] -> {os.environ.get('DEV')}")
