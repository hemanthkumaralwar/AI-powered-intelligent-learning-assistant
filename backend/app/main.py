"""Application entry point.

Run locally with:
    uvicorn app.main:app --app-dir backend --loop asyncio:SelectorEventLoop

`--loop asyncio:SelectorEventLoop` matters on Windows: uvicorn otherwise picks the
ProactorEventLoop, which psycopg's async driver cannot use. It is harmless on Linux.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin_documents import router as admin_documents_router
from app.api.auth import router as auth_router
from app.api.code_run import router as code_router
from app.api.health import router as health_router
from app.api.materials import router as materials_router
from app.auth.seed import seed_admin
from app.auth.service import AuthService, build_auth_service
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import Database, build_database
from app.indexing.factory import build_indexing_service
from app.indexing.service import IndexingService
from app.ingestion.files import MAX_UPLOAD_BYTES
from app.runner.factory import build_code_runner_service
from app.runner.service import CodeRunnerService

DEFAULT_BODY_LIMIT = 64 * 1024
MULTIPART_OVERHEAD = 64 * 1024


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    auth: AuthService | None = None,
    code_runner: CodeRunnerService | None = None,
    indexing: IndexingService | None = None,
) -> FastAPI:
    """Build the app from explicit settings.

    Tests pass their own `Settings` and services; production reads the environment
    once here. Shared services live on `app.state`, set up in `lifespan`.
    """
    settings = settings or Settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Fail fast at startup if DATABASE_URL or JWT_SECRET_KEY is missing.
        app.state.auth = auth or build_auth_service(settings)
        app.state.database = database or build_database(settings)
        app.state.code_runner = code_runner or build_code_runner_service(settings)
        app.state.indexing = indexing or build_indexing_service(settings, app.state.database)
        try:
            if settings.admin_username and settings.admin_password:
                await seed_admin(
                    app.state.database,
                    app.state.auth,
                    settings.admin_username,
                    settings.admin_password,
                )
            # Rebuild the vector index from Postgres before serving any request, so the
            # first question after a cold start already sees every course.
            await app.state.indexing.start()
            yield
        finally:
            # Only close what we created; injected services belong to the caller.
            if indexing is None:
                await app.state.indexing.aclose()
            else:
                await app.state.indexing.stop()
            if code_runner is None:
                await app.state.code_runner.aclose()
            if database is None:
                await app.state.database.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.settings = settings
    # JSON APIs need little; only the upload endpoint may receive a file (plus form overhead).
    app.add_middleware(
        BodySizeLimitMiddleware,
        default_limit=DEFAULT_BODY_LIMIT,
        path_limits={"/admin/documents": MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD},
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(code_router)
    app.include_router(materials_router)
    app.include_router(admin_documents_router)
    return app


app = create_app()
