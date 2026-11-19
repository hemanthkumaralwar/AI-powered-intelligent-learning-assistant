import pytest

from app.llm.base import ChatMessage, CompletionRequest, GenerationOptions
from app.llm.fake import DEFAULT_REPLY, FakeChatModel
from app.providers.errors import ProviderRequestError

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
    model = FakeChatModel([ProviderRequestError("boom")])

    with pytest.raises(ProviderRequestError, match="boom"):
        await model.complete(REQUEST)


async def test_push_queues_more_replies() -> None:
    model = FakeChatModel(["first"])
    model.push("second", "third")

    replies = [(await model.complete(REQUEST)).text for _ in range(4)]

    assert replies == ["first", "second", "third", DEFAULT_REPLY]
