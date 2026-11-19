from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings

SETTING_NAMES = (
    "APP_NAME",
    "ENVIRONMENT",
    "LOG_LEVEL",
    "LLM_PROVIDER",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_THINKING_BUDGET",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "LLM_TIMEOUT_SECONDS",
    "LLM_MAX_ATTEMPTS",
    "EMBEDDING_PROVIDER",
    "GEMINI_EMBEDDING_MODEL",
    "OPENAI_EMBEDDING_MODEL",
    "HF_EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "EMBEDDING_BATCH_SIZE",
    "EMBEDDING_DOCUMENT_TEXTS_PER_MINUTE",
    "EMBEDDING_QUERY_TEXTS_PER_MINUTE",
    "EMBEDDING_TIMEOUT_SECONDS",
    "EMBEDDING_MAX_ATTEMPTS",
    "DATABASE_URL",
    "DB_POOL_SIZE",
    "DB_CONNECT_TIMEOUT_SECONDS",
    "JWT_SECRET_KEY",
    "ACCESS_TOKEN_MINUTES",
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
)


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_llm_defaults_to_gemini_without_requiring_a_key() -> None:
    settings = Settings(_env_file=None)

    assert settings.llm_provider == "gemini"
    assert settings.gemini_api_key is None


def test_api_keys_are_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:db-password-value@h/db")

    settings = Settings(_env_file=None)

    assert "super-secret-value" not in repr(settings)
    assert "db-password-value" not in repr(settings)
    assert settings.gemini_api_key.get_secret_value() == "super-secret-value"


@pytest.mark.parametrize("name", ["LLM_PROVIDER", "EMBEDDING_PROVIDER"])
def test_fake_providers_rejected_in_production(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(name, "fake")

    with pytest.raises(ValidationError, match=f"{name}=fake is not allowed"):
        Settings(_env_file=None)


def test_fake_providers_allowed_outside_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")

    assert Settings(_env_file=None).embedding_provider == "fake"


def test_defaults_without_env() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.app_name
    # -lite models reject any thinking setting, so the two defaults go together.
    assert settings.gemini_model == "gemini-3.5-flash-lite"
    assert settings.gemini_thinking_budget is None


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.log_level == "DEBUG"


def test_reads_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LOG_LEVEL=ERROR\nUNRELATED_KEY=ignored\n", encoding="utf-8")

    assert Settings(_env_file=env_file).log_level == "ERROR"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LOG_LEVEL", "VERBOSE"),
        ("LOG_LEVEL", "debug"),
        ("ENVIRONMENT", "staging"),
        ("LLM_PROVIDER", "claude"),
        ("LLM_TIMEOUT_SECONDS", "0"),
        ("LLM_MAX_ATTEMPTS", "6"),
        ("GEMINI_THINKING_BUDGET", "-1"),
        ("EMBEDDING_PROVIDER", "cohere"),
        ("EMBEDDING_DIMENSIONS", "4"),
        ("EMBEDDING_BATCH_SIZE", "0"),
        ("EMBEDDING_DOCUMENT_TEXTS_PER_MINUTE", "0"),
        ("EMBEDDING_QUERY_TEXTS_PER_MINUTE", "0"),
        ("DB_POOL_SIZE", "0"),
        ("DB_CONNECT_TIMEOUT_SECONDS", "61"),
        ("JWT_SECRET_KEY", "too-short"),
        ("ACCESS_TOKEN_MINUTES", "4"),
        ("ADMIN_PASSWORD", "short"),
    ],
)
def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "pair",
    [{"ADMIN_USERNAME": "admin"}, {"ADMIN_PASSWORD": "long-enough-password"}],
    ids=["username-only", "password-only"],
)
def test_admin_credentials_must_come_in_pairs(
    monkeypatch: pytest.MonkeyPatch, pair: dict[str, str]
) -> None:
    for name, value in pair.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError, match="ADMIN_USERNAME and ADMIN_PASSWORD"):
        Settings(_env_file=None)


def test_jwt_secret_is_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "jwt-secret-value-that-is-long-enough")

    assert "jwt-secret-value" not in repr(Settings(_env_file=None))


def test_copied_env_example_counts_empty_values_as_unset(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[2] / ".env.example"
    env_file = tmp_path / ".env"
    env_file.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.jwt_secret_key is None
    assert settings.admin_username is None
    assert settings.database_url is None


def test_embedding_batch_must_fit_the_minute_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "81")
    monkeypatch.setenv("EMBEDDING_DOCUMENT_TEXTS_PER_MINUTE", "80")

    with pytest.raises(ValidationError, match="EMBEDDING_BATCH_SIZE must not exceed"):
        Settings(_env_file=None)


@pytest.mark.parametrize(("raw", "expected"), [("default", None), ("DEFAULT", None), ("256", 256)])
def test_thinking_budget_accepts_default(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: int | None
) -> None:
    monkeypatch.setenv("GEMINI_THINKING_BUDGET", raw)

    assert Settings(_env_file=None).gemini_thinking_budget == expected


@pytest.mark.parametrize(
    "url",
    ["http://learn.example/{lesson_id}", "https://learn.example/lessons", "ftp://x/{lesson_id}"],
)
def test_platform_url_must_be_an_https_lesson_template(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("PLATFORM_LESSON_URL", url)

    with pytest.raises(ValidationError, match="PLATFORM_LESSON_URL"):
        Settings(_env_file=None)


def test_platform_url_accepts_a_template(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_LESSON_URL", "https://learn.example/l/{lesson_id}")

    assert Settings(_env_file=None).platform_lesson_url == "https://learn.example/l/{lesson_id}"
