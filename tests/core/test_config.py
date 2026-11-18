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
    "EMBEDDING_REQUESTS_PER_MINUTE",
    "EMBEDDING_TIMEOUT_SECONDS",
    "EMBEDDING_MAX_ATTEMPTS",
    "DATABASE_URL",
    "DB_POOL_SIZE",
    "DB_CONNECT_TIMEOUT_SECONDS",
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
        ("LOG_LEVEL", ""),
        ("ENVIRONMENT", "staging"),
        ("LLM_PROVIDER", "claude"),
        ("LLM_TIMEOUT_SECONDS", "0"),
        ("LLM_MAX_ATTEMPTS", "6"),
        ("GEMINI_THINKING_BUDGET", "-1"),
        ("EMBEDDING_PROVIDER", "cohere"),
        ("EMBEDDING_DIMENSIONS", "4"),
        ("EMBEDDING_BATCH_SIZE", "0"),
        ("EMBEDDING_REQUESTS_PER_MINUTE", "0"),
        ("DB_POOL_SIZE", "0"),
        ("DB_CONNECT_TIMEOUT_SECONDS", "61"),
    ],
)
def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
