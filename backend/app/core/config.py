"""Typed application settings loaded from environment variables and `.env`."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Runtime configuration.

    Secrets added in later steps must be typed as `SecretStr` so they print as
    `**********` if a settings object is ever logged or shown in a traceback.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ArchintX Learning Assistant"
    environment: Environment = "development"
    log_level: LogLevel = "INFO"
