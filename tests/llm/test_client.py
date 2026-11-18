import logging

import pytest
from pydantic import BaseModel

from app.llm.base import ChatMessage, GenerationOptions, LLMResponse
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.providers.errors import (
    InvalidResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.retry import RetryPolicy

pytestmark = pytest.mark.anyio


class Answer(BaseModel):
    answer: str
    confidence: float


async def no_sleep(_: float) -> None:
    return None


def make_client(model: FakeChatModel, timeout_seconds: float = 5.0) -> LLMClient:
    return LLMClient(
        model,
        timeout_seconds=timeout_seconds,
        retry_policy=RetryPolicy(max_attempts=3),
        sleep=no_sleep,
    )


async def test_chat_returns_reply_and_sends_messages(conversation: list[ChatMessage]) -> None:
    model = FakeChatModel(["A named value."])

    response = await make_client(model).chat(conversation)

    assert response.text == "A named value."
    sent = model.requests[0]
    assert list(sent.messages) == conversation
    assert sent.options == GenerationOptions()
    assert sent.json_schema is None


async def test_chat_passes_custom_options(conversation: list[ChatMessage]) -> None:
    model = FakeChatModel()
    options = GenerationOptions(temperature=0.0, max_output_tokens=50)

    await make_client(model).chat(conversation, options)

    assert model.requests[0].options == options


@pytest.mark.parametrize(
    "messages",
    [[], [ChatMessage(role="system", content="only instructions")]],
    ids=["empty", "system-only"],
)
async def test_chat_rejects_conversations_without_user_turn(messages: list[ChatMessage]) -> None:
    model = FakeChatModel()

    with pytest.raises(ValueError, match="at least one user"):
        await make_client(model).chat(messages)
    assert model.requests == []


async def test_chat_retries_transient_failure(conversation: list[ChatMessage]) -> None:
    model = FakeChatModel([ProviderUnavailableError("503"), "recovered"])

    response = await make_client(model).chat(conversation)

    assert response.text == "recovered"
    assert len(model.requests) == 2


async def test_chat_times_out(conversation: list[ChatMessage]) -> None:
    model = FakeChatModel(delay_seconds=1.0)
    client = LLMClient(
        model, timeout_seconds=0.01, retry_policy=RetryPolicy(max_attempts=1), sleep=no_sleep
    )

    with pytest.raises(ProviderTimeoutError, match="fake did not respond"):
        await client.chat(conversation)


async def test_logs_metadata_but_never_content(
    conversation: list[ChatMessage], caplog: pytest.LogCaptureFixture
) -> None:
    model = FakeChatModel(["SECRET-ANSWER"])

    with caplog.at_level(logging.INFO, logger="app.llm.client"):
        await make_client(model).chat(conversation)

    assert "provider=fake" in caplog.text
    assert "attempts=1" in caplog.text
    assert "What is a variable?" not in caplog.text
    assert "SECRET-ANSWER" not in caplog.text


async def test_generate_json_returns_validated_model(conversation: list[ChatMessage]) -> None:
    model = FakeChatModel(['{"answer": "A box for a value", "confidence": 0.9}'])

    result = await make_client(model).generate_json(conversation, Answer)

    assert result == Answer(answer="A box for a value", confidence=0.9)
    assert model.requests[0].json_schema == Answer.model_json_schema()


async def test_generate_json_reports_truncation(conversation: list[ChatMessage]) -> None:
    cut_off = LLMResponse(text='{"answer": "A box', model="fake-model", truncated=True)
    client = make_client(FakeChatModel([cut_off]))

    with pytest.raises(InvalidResponseError, match="cut off at max_output_tokens"):
        await client.generate_json(conversation, Answer)


async def test_chat_returns_truncated_reply_and_logs_it(
    conversation: list[ChatMessage], caplog: pytest.LogCaptureFixture
) -> None:
    cut_off = LLMResponse(text="A long explan", model="fake-model", truncated=True)

    with caplog.at_level(logging.INFO, logger="app.llm.client"):
        response = await make_client(FakeChatModel([cut_off])).chat(conversation)

    assert response.truncated is True
    assert "truncated=True" in caplog.text


@pytest.mark.parametrize(
    "reply",
    ["not json at all", '{"answer": "missing confidence"}', '{"answer": 1, "confidence": "x"}'],
    ids=["not-json", "missing-field", "wrong-types"],
)
async def test_generate_json_rejects_bad_replies(
    conversation: list[ChatMessage], reply: str
) -> None:
    client = make_client(FakeChatModel([reply]))

    with pytest.raises(InvalidResponseError, match="did not match Answer") as excinfo:
        await client.generate_json(conversation, Answer)
    assert reply not in str(excinfo.value)
