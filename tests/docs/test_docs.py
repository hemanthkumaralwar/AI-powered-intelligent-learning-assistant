"""The docs cannot drift from the code: every API route is listed in docs/api.md, and every
setting is in the README's configuration table and in .env.example."""

import re
from pathlib import Path

import pytest

from app.core.config import Settings
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
API_DOC = (ROOT / "docs" / "api.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")


def routes() -> list[str]:
    """Every endpoint as Swagger shows it ("GET /courses"), from the OpenAPI spec."""
    paths = create_app(Settings(_env_file=None, environment="test")).openapi()["paths"]
    return sorted(f"{method.upper()} {path}" for path, ops in paths.items() for method in ops)


def test_the_route_list_is_read() -> None:
    # Guards the parametrised test below: an empty list would make it pass vacuously.
    assert len(routes()) >= 25 and "POST /chat/ask" in routes()


def setting_names() -> list[str]:
    return sorted(name.upper() for name in Settings.model_fields)


def configuration_section() -> str:
    """The README's "## Configuration" section, up to the next level-2 heading."""
    match = re.search(r"^## Configuration\n(.*?)(?=^## )", README, re.MULTILINE | re.DOTALL)
    assert match, "README has no Configuration section"
    return match.group(1)


@pytest.mark.parametrize("route", routes())
def test_every_route_is_in_the_api_doc(route: str) -> None:
    assert f"`{route}`" in API_DOC


@pytest.mark.parametrize("name", setting_names())
def test_every_setting_is_documented_and_in_the_env_example(name: str) -> None:
    assert f"`{name}`" in configuration_section()
    assert re.search(rf"^{name}=", ENV_EXAMPLE, re.MULTILINE), f"{name} missing in .env.example"
