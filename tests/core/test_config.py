from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_NAME", "ENVIRONMENT", "LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)


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
    [("LOG_LEVEL", "VERBOSE"), ("LOG_LEVEL", ""), ("ENVIRONMENT", "staging")],
)
def test_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
