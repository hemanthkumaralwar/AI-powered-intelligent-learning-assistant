"""Application entry point.

Run locally with:
    uvicorn app.main:app --app-dir backend --loop asyncio:SelectorEventLoop

`--loop asyncio:SelectorEventLoop` matters on Windows: uvicorn otherwise picks the
ProactorEventLoop, which psycopg's async driver cannot use. It is harmless on Linux.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.auth.seed import seed_admin
from app.auth.service import AuthService, build_auth_service
from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import Database, build_database


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    auth: AuthService | None = None,
) -> FastAPI:
    """Build the app from explicit settings.

    Tests pass their own `Settings`, `Database` and `AuthService`; production reads the
    environment once here. Shared services live on `app.state`, set up in `lifespan`.
    """
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Fail fast at startup if DATABASE_URL or JWT_SECRET_KEY is missing.
        app.state.auth = auth or build_auth_service(settings)
        app.state.database = database or build_database(settings)
        try:
            if settings.admin_username and settings.admin_password:
                await seed_admin(
                    app.state.database,
                    app.state.auth,
                    settings.admin_username,
                    settings.admin_password,
                )
            yield
        finally:
            # Only dispose what we created; an injected database belongs to the caller.
            if database is None:
                await app.state.database.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    return app


app = create_app()
