from types import SimpleNamespace

import pytest

from app.llm.gemini import GeminiChatModel
from app.llm.openai import OpenAIChatModel

pytestmark = pytest.mark.anyio


async def test_gemini_and_openai_release_their_clients() -> None:
    closed: list[str] = []

    async def gemini_close() -> None:
        closed.append("gemini")

    async def openai_close() -> None:
        closed.append("openai")

    await GeminiChatModel(SimpleNamespace(aio=SimpleNamespace(aclose=gemini_close)), "m").aclose()
    await OpenAIChatModel(SimpleNamespace(close=openai_close), "m").aclose()

    assert closed == ["gemini", "openai"]
