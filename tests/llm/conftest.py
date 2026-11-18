"""Async tests run on asyncio via the anyio pytest plugin (installed with FastAPI)."""

import pytest

from app.llm.base import ChatMessage


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def conversation() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="You are a tutor."),
        ChatMessage(role="user", content="What is a variable?"),
    ]
