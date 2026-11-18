import logging
from collections.abc import Iterator

import pytest

from app.core.logging import configure_logging


@pytest.fixture(autouse=True)
def restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    level, handlers = root.level, root.handlers[:]
    yield
    root.setLevel(level)
    root.handlers[:] = handlers


def test_sets_root_level() -> None:
    configure_logging("ERROR")

    assert logging.getLogger().level == logging.ERROR


def test_writes_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")

    logging.getLogger("app.test").info("hello")

    assert "INFO app.test: hello" in capsys.readouterr().out


def test_keeps_existing_loggers_enabled() -> None:
    existing = logging.getLogger("uvicorn.error")

    configure_logging("INFO")

    assert existing.disabled is False
