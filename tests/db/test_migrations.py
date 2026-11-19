"""The migrations produce exactly the schema the models describe, and can be undone."""

from types import SimpleNamespace

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, pool, text

from app.db.models import Base
from app.db.session import to_sqlalchemy_url

EXPECTED_TABLES = {
    "chat_sessions",
    "exercise_attempts",
    "chat_messages",
    "quiz_questions",
    "exercises",
    "alembic_version",
    "users",
    "courses",
    "modules",
    "lessons",
    "documents",
    "document_files",
    "chunks",
}


def connect(url: str, schema: str):
    return create_engine(
        to_sqlalchemy_url(url),
        poolclass=pool.NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )


def test_migrated_schema_matches_models(test_database_url: str, migrated_schema: str) -> None:
    engine = connect(test_database_url, migrated_schema)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        differences = compare_metadata(context, Base.metadata)
    engine.dispose()

    assert differences == []


def test_row_level_security_is_on_for_every_table(
    test_database_url: str, migrated_schema: str
) -> None:
    engine = connect(test_database_url, migrated_schema)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT c.relname, c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = :schema AND c.relkind = 'r'"
            ),
            {"schema": migrated_schema},
        ).all()
    engine.dispose()

    assert {name for name, _ in rows} == EXPECTED_TABLES
    assert all(rls for _, rls in rows)


def test_downgrade_then_upgrade_round_trips(
    test_database_url: str, schema_tools: SimpleNamespace
) -> None:
    schema = schema_tools.create(test_database_url)
    try:
        schema_tools.migrate(test_database_url, schema, "head")
        schema_tools.migrate(test_database_url, schema, "base", downgrade=True)
        engine = connect(test_database_url, schema)
        with engine.connect() as connection:
            remaining = (
                connection.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": schema}
                )
                .scalars()
                .all()
            )
        engine.dispose()
        assert remaining == ["alembic_version"]

        schema_tools.migrate(test_database_url, schema, "head")
    finally:
        schema_tools.drop(test_database_url, schema)


def test_0003_refuses_to_run_while_notes_exist(
    test_database_url: str, schema_tools: SimpleNamespace
) -> None:
    schema = schema_tools.create(test_database_url)
    try:
        schema_tools.migrate(test_database_url, schema, "0002")
        engine = connect(test_database_url, schema)
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO courses (id, title, language) VALUES ('c1', 'C1', 'python')")
            )
            connection.execute(
                text(
                    "INSERT INTO documents (id, course_id, kind, filename, content_type,"
                    " size_bytes, sha256, status)"
                    " VALUES (gen_random_uuid(), 'c1', 'notes', 'n.txt',"
                    " 'text/plain', 1, 'x', 'pending')"
                )
            )
        engine.dispose()

        with pytest.raises(RuntimeError, match="1 notes document"):
            schema_tools.migrate(test_database_url, schema, "head")
    finally:
        schema_tools.drop(test_database_url, schema)
