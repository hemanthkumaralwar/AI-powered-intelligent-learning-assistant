import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.errors import AuthConfigurationError
from app.core.config import Settings
from app.db.errors import DatabaseConfigurationError
from app.main import create_app


def test_create_app_uses_given_settings() -> None:
    settings = Settings(_env_file=None, app_name="Test App", log_level="WARNING")

    app = create_app(settings)

    assert app.state.settings is settings
    assert app.title == "Test App"


def test_module_level_app_is_importable() -> None:
    from app.main import app

    assert isinstance(app, FastAPI)


def test_startup_fails_fast_without_jwt_secret() -> None:
    app = create_app(Settings(_env_file=None, database_url="postgresql://u:p@h/db"))

    with pytest.raises(AuthConfigurationError, match="JWT_SECRET_KEY is required"), TestClient(app):
        pass


def test_startup_fails_fast_without_database_url() -> None:
    app = create_app(Settings(_env_file=None, jwt_secret_key="k" * 32))

    with (
        pytest.raises(DatabaseConfigurationError, match="DATABASE_URL is required"),
        TestClient(app),
    ):
        pass


def test_lifespan_builds_and_disposes_its_own_database() -> None:
    # Creating the engine does not connect, so no real database is needed here.
    settings = Settings(
        _env_file=None, jwt_secret_key="k" * 32, database_url="postgresql://u:p@localhost/db"
    )
    app = create_app(settings)

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        engine = app.state.database.engine

    assert engine.pool.checkedout() == 0
