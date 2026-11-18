import pytest

from app.llm.base import ChatMessage, CompletionRequest, GenerationOptions
from app.llm.errors import ProviderError
from app.llm.fake import DEFAULT_REPLY, FakeChatModel

pytestmark = pytest.mark.anyio

REQUEST = CompletionRequest(
    messages=(ChatMessage(role="user", content="hi"),), options=GenerationOptions()
)


async def test_replays_script_then_default() -> None:
    model = FakeChatModel(["first"])

    assert (await model.complete(REQUEST)).text == "first"
    assert (await model.complete(REQUEST)).text == DEFAULT_REPLY
    assert model.requests == [REQUEST, REQUEST]


async def test_raises_scripted_exceptions() -> None:
    model = FakeChatModel([ProviderError("boom")])

    with pytest.raises(ProviderError, match="boom"):
        await model.complete(REQUEST)
