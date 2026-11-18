"""Alembic environment.

- `alembic upgrade head` migrates the database in DATABASE_URL.
- `alembic upgrade head --sql` prints the SQL without connecting (for review).
- Tests pass an open connection via `config.attributes["connection"]`.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine, pool

from app.core.config import Settings
from app.db.models import Base
from app.db.session import require_database_url, to_sqlalchemy_url

config = context.config
if config.config_file_name is not None and not config.attributes.get("connection"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _migrate(connection)
        return
    settings = Settings()
    engine = create_engine(
        to_sqlalchemy_url(require_database_url(settings.database_url)),
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": settings.db_connect_timeout_seconds},
    )
    try:
        with engine.connect() as connection:
            _migrate(connection)
    finally:
        engine.dispose()


def _migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
