from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from google.genai import errors, types

from app.llm.base import ChatMessage, CompletionRequest, GenerationOptions
from app.llm.errors import (
    InvalidResponseError,
    LLMTimeoutError,
    ProviderError,
    ProviderUnavailableError,
    RateLimitedError,
)
from app.llm.gemini import (
    GeminiChatModel,
    parse_retry_delay,
    to_gemini_config,
    to_gemini_contents,
)

REQUEST = CompletionRequest(
    messages=(
        ChatMessage(role="system", content="Be brief."),
        ChatMessage(role="system", content="Cite lessons."),
        ChatMessage(role="user", content="What is let?"),
        ChatMessage(role="assistant", content="A declaration."),
        ChatMessage(role="user", content="And const?"),
    ),
    options=GenerationOptions(temperature=0.1, max_output_tokens=100),
)


class StubGenaiClient:
    """Mimics `genai.Client().aio.models.generate_content` without network access."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def gemini_result(
    text: str | None,
    usage: bool = True,
    finish_reason: types.FinishReason | None = types.FinishReason.STOP,
) -> SimpleNamespace:
    metadata = SimpleNamespace(prompt_token_count=12, candidates_token_count=3) if usage else None
    candidates = [SimpleNamespace(finish_reason=finish_reason)] if finish_reason else []
    return SimpleNamespace(text=text, usage_metadata=metadata, candidates=candidates)


def test_contents_map_roles_and_drop_system_messages() -> None:
    contents = to_gemini_contents(REQUEST)

    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[0].parts[0].text == "What is let?"


def test_config_joins_system_text_and_sets_options() -> None:
    config = to_gemini_config(REQUEST)

    assert config.system_instruction == "Be brief.\n\nCite lessons."
    assert config.temperature == 0.1
    assert config.max_output_tokens == 100
    assert config.thinking_config.thinking_budget == 0
    assert config.response_mime_type is None


def test_config_adds_thinking_budget_on_top_of_answer_limit() -> None:
    config = to_gemini_config(REQUEST, thinking_budget=512)

    assert config.thinking_config.thinking_budget == 512
    assert config.max_output_tokens == 100 + 512


def test_config_without_system_messages_has_no_instruction() -> None:
    request = CompletionRequest(
        messages=(ChatMessage(role="user", content="hi"),), options=GenerationOptions()
    )

    assert to_gemini_config(request).system_instruction is None


def test_config_requests_json_when_schema_given() -> None:
    schema = {"type": "object", "properties": {"answer": {"type": "string"}}}
    request = REQUEST.model_copy(update={"json_schema": schema})

    config = to_gemini_config(request)

    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == schema


@pytest.mark.anyio
async def test_complete_returns_text_and_usage() -> None:
    client = StubGenaiClient(gemini_result("const cannot be reassigned."))
    model = GeminiChatModel(client, "gemini-test")

    response = await model.complete(REQUEST)

    assert response.text == "const cannot be reassigned."
    assert (response.model, response.input_tokens, response.output_tokens) == (
        "gemini-test",
        12,
        3,
    )
    assert response.truncated is False
    assert client.calls[0]["model"] == "gemini-test"


@pytest.mark.anyio
async def test_complete_passes_thinking_budget() -> None:
    client = StubGenaiClient(gemini_result("ok"))

    await GeminiChatModel(client, "m", thinking_budget=256).complete(REQUEST)

    assert client.calls[0]["config"].max_output_tokens == 100 + 256


@pytest.mark.anyio
async def test_complete_flags_truncated_reply() -> None:
    result = gemini_result(
        '{"country":"India","capital":"New', finish_reason=types.FinishReason.MAX_TOKENS
    )

    response = await GeminiChatModel(StubGenaiClient(result), "m").complete(REQUEST)

    assert response.truncated is True


@pytest.mark.anyio
async def test_complete_handles_missing_usage_and_candidates() -> None:
    result = gemini_result("ok", usage=False, finish_reason=None)

    response = await GeminiChatModel(StubGenaiClient(result), "m").complete(REQUEST)

    assert response.input_tokens is None
    assert response.truncated is False


@pytest.mark.anyio
@pytest.mark.parametrize("text", [None, ""])
async def test_complete_rejects_empty_text(text: str | None) -> None:
    model = GeminiChatModel(StubGenaiClient(gemini_result(text)), "m")

    with pytest.raises(InvalidResponseError):
        await model.complete(REQUEST)


RATE_LIMIT_BODY = {
    "error": {
        "code": 429,
        "status": "RESOURCE_EXHAUSTED",
        "details": [
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure"},
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"},
        ],
    }
}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (errors.ClientError(429, RATE_LIMIT_BODY), RateLimitedError),
        (errors.ServerError(503, {"error": {"code": 503}}), ProviderUnavailableError),
        (errors.ClientError(400, {"error": {"code": 400}}), ProviderError),
        (errors.ClientError(403, {"error": {"code": 403}}), ProviderError),
        (httpx2.ReadTimeout("slow"), LLMTimeoutError),
        (httpx2.ConnectError("down"), ProviderUnavailableError),
    ],
)
async def test_complete_maps_errors(raised: Exception, expected: type[Exception]) -> None:
    model = GeminiChatModel(StubGenaiClient(raised), "m")

    with pytest.raises(expected):
        await model.complete(REQUEST)


@pytest.mark.anyio
async def test_rate_limit_error_carries_retry_delay() -> None:
    model = GeminiChatModel(StubGenaiClient(errors.ClientError(429, RATE_LIMIT_BODY)), "m")

    with pytest.raises(RateLimitedError) as excinfo:
        await model.complete(REQUEST)
    assert excinfo.value.retry_after == 37.0


@pytest.mark.parametrize(
    "details",
    [
        None,
        "text body",
        {"error": "flat"},
        {"error": {"details": "not a list"}},
        {"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo"}]}},
        {
            "error": {
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "soon"}
                ]
            }
        },
    ],
)
def test_parse_retry_delay_tolerates_unexpected_shapes(details: Any) -> None:
    assert parse_retry_delay(details) is None


def test_parse_retry_delay_reads_fractional_seconds() -> None:
    details = {
        "error": {
            "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "1.5s"}]
        }
    }

    assert parse_retry_delay(details) == 1.5
