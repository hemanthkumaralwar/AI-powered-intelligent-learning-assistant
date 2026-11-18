import pytest

from app.llm.base import ChatMessage


@pytest.fixture
def conversation() -> list[ChatMessage]:
    return [
        ChatMessage(role="system", content="You are a tutor."),
        ChatMessage(role="user", content="What is a variable?"),
    ]
