"""Typed application settings loaded from environment variables and `.env`."""

from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LLMProvider = Literal["gemini", "openai", "fake"]
EmbeddingProvider = Literal["gemini", "openai", "huggingface", "fake"]
RunnerName = Literal["judge0", "godbolt", "fake"]


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
    # gemini-2.5-flash returns 404 for new API keys (checked 2026-11-18). On 2026-11-19
    # gemini-3.8-flash timed out (504) and gemini-3.5-flash was overloaded (503), while
    # the -lite models answered in about a second, so lite is the default.
    gemini_model: str = Field(default="gemini-3.5-flash-lite", min_length=1)
    # Tokens Gemini may spend "thinking" before answering, on top of the answer limit.
    # None ("default" in the environment) sends no thinking setting: required by -lite
    # models, which answer 400 INVALID_ARGUMENT even to a budget of 0. With a thinking
    # model such as gemini-3.8-flash, set 0 to turn thinking off (fastest, and thinking
    # cannot cut answers short).
    gemini_thinking_budget: int | None = Field(default=None, ge=0, le=8192)
    openai_api_key: SecretStr | None = None
    openai_model: str = Field(default="gpt-4o-mini", min_length=1)
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    # Total tries per request, including the first one.
    llm_max_attempts: int = Field(default=3, ge=1, le=5)

    # Grounded answers (Step 12). Both values were measured in eval/reports (Step 11):
    # top-3 already holds the right lesson for every answerable question, and 0.63 sits
    # between in-course (>= 0.640) and out-of-course (<= 0.624) top scores. The threshold
    # only holds for gemini-embedding-001 at 768 dimensions: re-run eval/run_eval.py
    # after changing the embedding model.
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_min_score: float = Field(default=0.63, ge=0.0, le=1.0)
    # Each question costs one embedding and one LLM call from the shared free tier.
    chat_questions_per_user_per_minute: int = Field(default=5, ge=1, le=1000)
    chat_questions_global_per_minute: int = Field(default=20, ge=1, le=10_000)

    embedding_provider: EmbeddingProvider = "gemini"
    # gemini-embedding-2 merges a batch into one vector, so it cannot be used for chunks.
    gemini_embedding_model: str = Field(default="gemini-embedding-001", min_length=1)
    openai_embedding_model: str = Field(default="text-embedding-3-small", min_length=1)
    hf_embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", min_length=1)
    # 768 is supported by Gemini and OpenAI, so switching between them needs no re-index.
    # Smaller than the 3072 maximum to keep the FAISS index and Postgres rows small.
    embedding_dimensions: int = Field(default=768, ge=8, le=3072)
    # Gemini's free tier meters every *text* (not call): ~100 per minute and ~1,000 per
    # day per project. Indexing and student questions get separate per-minute budgets
    # that together stay under 100, so questions never wait behind an indexing batch.
    embedding_batch_size: int = Field(default=40, ge=1, le=2048)
    embedding_document_texts_per_minute: int = Field(default=80, ge=1, le=100_000)
    embedding_query_texts_per_minute: int = Field(default=20, ge=1, le=100_000)
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

    # Remote sandboxes tried in order; a runner failure falls through to the next.
    # Comma-separated in the environment, e.g. CODE_RUNNERS=judge0,godbolt
    code_runners: Annotated[tuple[RunnerName, ...], NoDecode] = ("judge0", "godbolt")
    judge0_base_url: str = "https://ce.judge0.com"
    godbolt_base_url: str = "https://godbolt.org"
    # Wait for the runner service itself (the program's own limits are below).
    code_runner_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    code_cpu_seconds: float = Field(default=5.0, gt=0, le=15)
    code_wall_seconds: float = Field(default=10.0, gt=0, le=20)
    code_runs_per_user_per_minute: int = Field(default=10, ge=1, le=1000)
    code_runs_per_user_per_day: int = Field(default=200, ge=1, le=100_000)
    code_runs_global_per_minute: int = Field(default=30, ge=1, le=10_000)

    @field_validator("gemini_thinking_budget", mode="before")
    @classmethod
    def _model_default_thinking(cls, value: object) -> object:
        if isinstance(value, str) and value.strip().lower() == "default":
            return None
        return value

    @field_validator("code_runners", mode="before")
    @classmethod
    def _split_runner_list(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator("code_runners")
    @classmethod
    def _runner_list_not_empty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("CODE_RUNNERS needs at least one runner")
        return value

    @model_validator(mode="after")
    def _batch_fits_the_minute_budget(self) -> Self:
        if self.embedding_batch_size > self.embedding_document_texts_per_minute:
            raise ValueError(
                "EMBEDDING_BATCH_SIZE must not exceed EMBEDDING_DOCUMENT_TEXTS_PER_MINUTE"
            )
        return self

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
        if "fake" in self.code_runners:
            raise ValueError("CODE_RUNNERS=fake is not allowed when ENVIRONMENT=production")
        return self
