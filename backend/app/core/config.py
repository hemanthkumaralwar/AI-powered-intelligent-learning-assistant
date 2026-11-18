"""Typed application settings loaded from environment variables and `.env`."""

from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LLMProvider = Literal["gemini", "openai", "fake"]


class Settings(BaseSettings):
    """Runtime configuration.

    Secrets are typed as `SecretStr` so they print as `**********` if a settings object
    is ever logged or shown in a traceback. API keys are checked when the provider is
    built (`app.llm.factory`), so tests and tools that never call an LLM need no key.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ArchintX Learning Assistant"
    environment: Environment = "development"
    log_level: LogLevel = "INFO"

    llm_provider: LLMProvider = "gemini"
    gemini_api_key: SecretStr | None = None
    # gemini-2.5-flash returns 404 for new API keys (checked 2026-11-18).
    gemini_model: str = Field(default="gemini-3.8-flash", min_length=1)
    # Tokens Gemini may spend "thinking" before answering, on top of the answer limit.
    # 0 turns thinking off: fastest and lightest on the free-tier quota.
    gemini_thinking_budget: int = Field(default=0, ge=0, le=8192)
    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default="gpt-4o-mini", min_length=1)
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    # Total tries per request, including the first one.
    llm_max_attempts: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def _no_fake_llm_in_production(self) -> Self:
        if self.environment == "production" and self.llm_provider == "fake":
            raise ValueError("LLM_PROVIDER=fake is not allowed when ENVIRONMENT=production")
        return self
