import httpx2
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


@pytest.mark.anyio
async def test_lifespan_builds_and_disposes_its_own_services(
    test_database_url: str, migrated_schema: str, fake_embeddings: dict
) -> None:
    # The app builds its own Database from DATABASE_URL; `options` points it at the
    # throwaway schema the test run migrated. Async (not TestClient) so Windows uses the
    # selector event loop that psycopg needs.
    separator = "&" if "?" in test_database_url else "?"
    url = f"{test_database_url}{separator}options=-csearch_path%3D{migrated_schema}"
    settings = Settings(
        _env_file=None, jwt_secret_key="k" * 32, database_url=url, **fake_embeddings
    )
    app = create_app(settings)

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get("/health")).status_code == 200
        engine = app.state.database.engine
        embedder_model = app.state.indexing._embedder._model
        assert app.state.indexing.index.size == 0

    assert engine.pool.checkedout() == 0
    assert embedder_model.closed is True
