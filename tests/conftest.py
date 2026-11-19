"""Shared fixtures. Tests never read the developer's `.env` for app settings.

Database fixtures: every test run migrates a brand-new schema (`test_<random>`) on the Neon
*test* branch and drops it afterwards, so local runs and CI never see each other's data.
Without TEST_DATABASE_URL the database tests are skipped, not failed.
"""

import asyncio
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, pool, text

from app.core.config import Settings
from app.db.models import Base
from app.db.session import Database, to_sqlalchemy_url
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, environment="test", log_level="WARNING")


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


class _TestDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    test_database_url: SecretStr | None = None


@pytest.fixture
def anyio_backend() -> object:
    # psycopg's async mode cannot run on Windows' default ProactorEventLoop.
    if sys.platform == "win32":
        return ("asyncio", {"loop_factory": asyncio.SelectorEventLoop})
    return "asyncio"


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = _TestDatabaseSettings().test_database_url
    if url is None or not url.get_secret_value().strip():
        pytest.skip("TEST_DATABASE_URL is not set; database tests skipped")
    return url.get_secret_value().strip()


def run_alembic(url: str, schema: str, revision: str, *, downgrade: bool = False) -> None:
    engine = create_engine(
        to_sqlalchemy_url(url),
        poolclass=pool.NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        with engine.begin() as connection:
            config = Config(str(ALEMBIC_INI))
            config.attributes["connection"] = connection
            (command.downgrade if downgrade else command.upgrade)(config, revision)
    finally:
        engine.dispose()


def create_schema(url: str) -> str:
    schema = f"test_{uuid.uuid4().hex[:12]}"
    engine = create_engine(to_sqlalchemy_url(url), poolclass=pool.NullPool)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine.dispose()
    return schema


def drop_schema(url: str, schema: str) -> None:
    engine = create_engine(to_sqlalchemy_url(url), poolclass=pool.NullPool)
    with engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    engine.dispose()


@pytest.fixture
def schema_tools() -> SimpleNamespace:
    """Helpers for tests that need their own throwaway schema (e.g. downgrade tests)."""
    return SimpleNamespace(create=create_schema, drop=drop_schema, migrate=run_alembic)


@pytest.fixture(scope="session")
def migrated_schema(test_database_url: str) -> Iterator[str]:
    schema = create_schema(test_database_url)
    try:
        run_alembic(test_database_url, schema, "head")
        yield schema
    finally:
        drop_schema(test_database_url, schema)


@pytest.fixture
async def database(test_database_url: str, migrated_schema: str) -> AsyncIterator[Database]:
    db = Database(test_database_url, pool_size=2, schema=migrated_schema)
    try:
        yield db
    finally:
        tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
        async with db.engine.begin() as connection:
            await connection.execute(text(f"TRUNCATE {tables} CASCADE"))
        await db.dispose()


# ---- indexing --------------------------------------------------------------------------

# Settings for tests that let the app build its own services on a test database:
# deterministic fake embeddings and LLM, and no client-side throttling of the fake.
FAKE_PROVIDERS = {
    "llm_provider": "fake",
    "embedding_provider": "fake",
    "embedding_document_texts_per_minute": 100_000,
    "embedding_query_texts_per_minute": 100_000,
}


class NullIndexing:
    """Stands in for IndexingService where a test has no database or vectors."""

    embedding_id = "null"

    async def search(self, query: str, k: int, course_id: str | None = None) -> list:
        return []

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def aclose(self) -> None:
        return None

    def enqueue(self, document_id: object) -> None:
        return None

    def remove_course(self, course_id: str) -> None:
        return None


@pytest.fixture
def null_indexing() -> NullIndexing:
    return NullIndexing()


@pytest.fixture
def fake_providers() -> dict:
    return dict(FAKE_PROVIDERS)
