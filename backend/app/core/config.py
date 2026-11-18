"""Typed application settings loaded from environment variables and `.env`."""

from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LLMProvider = Literal["gemini", "openai", "fake"]
EmbeddingProvider = Literal["gemini", "openai", "huggingface", "fake"]


class Settings(BaseSettings):
    """Runtime configuration.

    Secrets are typed as `SecretStr` so they print as `**********` if a settings object
    is ever logged or shown in a traceback. API keys are checked when a provider is
    built (`app.llm.factory`, `app.embeddings.factory`), so tests and tools that never
    call a provider need no key.
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

    embedding_provider: EmbeddingProvider = "gemini"
    # gemini-embedding-2 merges a batch into one vector, so it cannot be used for chunks.
    gemini_embedding_model: str = Field(default="gemini-embedding-001", min_length=1)
    openai_embedding_model: str = Field(default="text-embedding-3-small", min_length=1)
    hf_embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", min_length=1)
    # 768 is supported by Gemini and OpenAI, so switching between them needs no re-index.
    # Smaller than the 3072 maximum to keep Chroma within Render's 512 MB.
    embedding_dimensions: int = Field(default=768, ge=8, le=3072)
    embedding_batch_size: int = Field(default=100, ge=1, le=2048)
    embedding_requests_per_minute: int = Field(default=60, ge=1, le=10_000)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    embedding_max_attempts: int = Field(default=3, ge=1, le=5)

    @model_validator(mode="after")
    def _no_fakes_in_production(self) -> Self:
        if self.environment != "production":
            return self
        if self.llm_provider == "fake":
            raise ValueError("LLM_PROVIDER=fake is not allowed when ENVIRONMENT=production")
        if self.embedding_provider == "fake":
            raise ValueError("EMBEDDING_PROVIDER=fake is not allowed when ENVIRONMENT=production")
        return self
