"""Session and URL handling that needs no database."""

import pytest

from app.core.config import Settings
from app.db.errors import DatabaseConfigurationError
from app.db.repositories.users import normalize_username
from app.db.session import Database, build_database, to_sqlalchemy_url

SAMPLE_DB_URL = "postgresql://app:hunter2-not-real@db.example.com/app?sslmode=require"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        (
            "  postgresql://u:p@h/db?sslmode=require  ",
            "postgresql+psycopg://u:p@h/db?sslmode=require",
        ),
    ],
)
def test_url_is_pointed_at_psycopg(raw: str, expected: str) -> None:
    assert to_sqlalchemy_url(raw) == expected


@pytest.mark.parametrize("raw", ["mysql://u:p@h/db", "", "sqlite:///x.db"])
def test_non_postgres_url_is_rejected_without_echoing_it(raw: str) -> None:
    with pytest.raises(DatabaseConfigurationError) as excinfo:
        to_sqlalchemy_url(raw)
    assert "u:p" not in str(excinfo.value)


@pytest.mark.parametrize("schema", ["Public", "drop table x", "a;b", "1abc", "x" * 64])
def test_schema_name_must_be_a_plain_identifier(schema: str) -> None:
    with pytest.raises(DatabaseConfigurationError, match="identifier"):
        Database(SAMPLE_DB_URL, schema=schema)


def test_build_database_requires_url() -> None:
    with pytest.raises(DatabaseConfigurationError, match="DATABASE_URL is required"):
        build_database(Settings(_env_file=None))


def test_build_database_does_not_connect_or_leak_password() -> None:
    database = build_database(Settings(_env_file=None, database_url=SAMPLE_DB_URL, db_pool_size=3))

    assert database.engine.pool.size() == 3
    assert "hunter2-not-real" not in repr(database.engine.url)


@pytest.mark.parametrize(("raw", "expected"), [("Asha", "asha"), ("  RAVI ", "ravi")])
def test_usernames_are_case_insensitive(raw: str, expected: str) -> None:
    assert normalize_username(raw) == expected
