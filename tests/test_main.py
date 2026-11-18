from fastapi import FastAPI

from app.core.config import Settings
from app.main import create_app


def test_create_app_uses_given_settings() -> None:
    settings = Settings(_env_file=None, app_name="Test App", log_level="WARNING")

    app = create_app(settings)

    assert app.state.settings is settings
    assert app.title == "Test App"


def test_module_level_app_is_importable() -> None:
    from app.main import app

    assert isinstance(app, FastAPI)
