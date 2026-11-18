"""Engine and session management."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.db.errors import DatabaseConfigurationError

_SCHEME = re.compile(r"^postgres(?:ql)?(?:\+psycopg)?://")
_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def to_sqlalchemy_url(raw_url: str) -> str:
    """Point a provider's `postgresql://` URL at the psycopg 3 driver.

    The URL contains the password, so errors never include it.
    """
    url = raw_url.strip()
    if not _SCHEME.match(url):
        raise DatabaseConfigurationError("DATABASE_URL must start with postgresql://")
    return _SCHEME.sub("postgresql+psycopg://", url, count=1)


class Database:
    """Owns the connection pool. Create one per process and `dispose()` it at shutdown."""

    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 5,
        connect_timeout_seconds: int = 10,
        schema: str | None = None,
    ) -> None:
        connect_args: dict[str, object] = {"connect_timeout": connect_timeout_seconds}
        if schema is not None:
            # Interpolated into a connection option, so only plain identifiers are allowed.
            if not _SCHEMA_NAME.match(schema):
                raise DatabaseConfigurationError("schema must be a lowercase identifier")
            connect_args["options"] = f"-csearch_path={schema}"
        self.engine: AsyncEngine = create_async_engine(
            to_sqlalchemy_url(url),
            pool_size=pool_size,
            max_overflow=0,
            # Neon closes idle connections when it scales to zero; check before reuse.
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        self._sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """One unit of work: commits if the block succeeds, rolls back if it raises."""
        async with self._sessions() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        await self.engine.dispose()


def build_database(settings: Settings) -> Database:
    return Database(
        require_database_url(settings.database_url),
        pool_size=settings.db_pool_size,
        connect_timeout_seconds=settings.db_connect_timeout_seconds,
    )


def require_database_url(url: SecretStr | None) -> str:
    value = url.get_secret_value().strip() if url else ""
    if not value:
        raise DatabaseConfigurationError("DATABASE_URL is required")
    return value
