"""Application entry point.

Run locally with: uvicorn app.main:app --app-dir backend --reload
"""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import Settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app from explicit settings.

    Tests pass their own `Settings`; production reads the environment once here.
    Settings live on `app.state` instead of a module-level singleton.
    """
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    register_exception_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
