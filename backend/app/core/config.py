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

    # env_ignore_empty: "KEY=" (as in .env.example) means "not set", not an empty value.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True
    )

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

    # Use a direct (Neon) or session-pooler (Supabase) URL, not a transaction pooler.
    database_url: SecretStr | None = None
    # Kept small: free tiers cap connections, and one Render instance needs few.
    db_pool_size: int = Field(default=5, ge=1, le=20)
    db_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)

    # Signs access tokens; at least 32 characters (256 bits for HS256). Generate with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    jwt_secret_key: SecretStr | None = Field(default=None, min_length=32)
    access_token_minutes: int = Field(default=60, ge=5, le=1440)
    # Optional first admin, created at startup only if that username does not exist yet.
    admin_username: str | None = Field(default=None, min_length=3, max_length=50)
    admin_password: SecretStr | None = Field(default=None, min_length=12, max_length=128)

    @model_validator(mode="after")
    def _admin_credentials_come_in_pairs(self) -> Self:
        if (self.admin_username is None) != (self.admin_password is None):
            raise ValueError("set both ADMIN_USERNAME and ADMIN_PASSWORD, or neither")
        return self

    @model_validator(mode="after")
    def _no_fakes_in_production(self) -> Self:
        if self.environment != "production":
            return self
        if self.llm_provider == "fake":
            raise ValueError("LLM_PROVIDER=fake is not allowed when ENVIRONMENT=production")
        if self.embedding_provider == "fake":
            raise ValueError("EMBEDDING_PROVIDER=fake is not allowed when ENVIRONMENT=production")
        return self
