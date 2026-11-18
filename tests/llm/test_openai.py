from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest

from app.llm.base import ChatMessage, CompletionRequest, GenerationOptions
from app.llm.errors import (
    InvalidResponseError,
    LLMTimeoutError,
    ProviderError,
    ProviderUnavailableError,
    RateLimitedError,
)
from app.llm.openai import OpenAIChatModel, parse_retry_after, response_format

REQUEST = CompletionRequest(
    messages=(
        ChatMessage(role="system", content="Be brief."),
        ChatMessage(role="user", content="What is let?"),
    ),
    options=GenerationOptions(temperature=0.3, max_output_tokens=64),
)
HTTP_REQUEST = httpx2.Request("POST", "https://api.openai.com/v1/chat/completions")


class StubOpenAIClient:
    """Mimics `AsyncOpenAI().chat.completions.create` without network access."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def completion(
    content: str | None, usage: bool = True, finish_reason: str = "stop"
) -> SimpleNamespace:
    choice = SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)
    tokens = SimpleNamespace(prompt_tokens=9, completion_tokens=4) if usage else None
    return SimpleNamespace(choices=[choice], usage=tokens)


def status_error(cls: type[openai.APIStatusError], status: int, headers: dict | None = None):
    response = httpx2.Response(status, headers=headers or {}, request=HTTP_REQUEST)
    return cls("error", response=response, body=None)


@pytest.mark.anyio
async def test_complete_sends_messages_and_options() -> None:
    client = StubOpenAIClient(completion("A block-scoped variable."))

    response = await OpenAIChatModel(client, "gpt-test").complete(REQUEST)

    assert response.text == "A block-scoped variable."
    assert (response.input_tokens, response.output_tokens) == (9, 4)
    call = client.calls[0]
    assert call["messages"] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "What is let?"},
    ]
    assert (call["model"], call["temperature"], call["max_completion_tokens"]) == (
        "gpt-test",
        0.3,
        64,
    )
    assert "response_format" not in call


@pytest.mark.anyio
async def test_complete_handles_missing_usage() -> None:
    response = await OpenAIChatModel(StubOpenAIClient(completion("ok", usage=False)), "m").complete(
        REQUEST
    )

    assert response.output_tokens is None


@pytest.mark.anyio
@pytest.mark.parametrize(("finish_reason", "truncated"), [("stop", False), ("length", True)])
async def test_complete_flags_truncation(finish_reason: str, truncated: bool) -> None:
    result = completion("partial", finish_reason=finish_reason)

    response = await OpenAIChatModel(StubOpenAIClient(result), "m").complete(REQUEST)

    assert response.truncated is truncated


@pytest.mark.anyio
@pytest.mark.parametrize(
    "result",
    [completion(None), completion(""), SimpleNamespace(choices=[], usage=None)],
    ids=["none", "empty", "no-choices"],
)
async def test_complete_rejects_empty_reply(result: Any) -> None:
    with pytest.raises(InvalidResponseError):
        await OpenAIChatModel(StubOpenAIClient(result), "m").complete(REQUEST)


def test_response_format_only_when_schema_given() -> None:
    schema = {"type": "object"}

    assert response_format(None) == {}
    assert response_format(schema)["response_format"]["json_schema"]["schema"] == schema


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (openai.APITimeoutError(request=HTTP_REQUEST), LLMTimeoutError),
        (openai.APIConnectionError(request=HTTP_REQUEST), ProviderUnavailableError),
        (status_error(openai.RateLimitError, 429), RateLimitedError),
        (status_error(openai.InternalServerError, 503), ProviderUnavailableError),
        (status_error(openai.AuthenticationError, 401), ProviderError),
        (status_error(openai.BadRequestError, 400), ProviderError),
    ],
)
async def test_complete_maps_errors(raised: Exception, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        await OpenAIChatModel(StubOpenAIClient(raised), "m").complete(REQUEST)


@pytest.mark.parametrize(("header", "expected"), [("2.5", 2.5), ("soon", None), (None, None)])
def test_parse_retry_after(header: str | None, expected: float | None) -> None:
    headers = {"retry-after": header} if header is not None else {}

    assert parse_retry_after(status_error(openai.RateLimitError, 429, headers)) == expected
