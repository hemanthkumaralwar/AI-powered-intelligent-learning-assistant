"""OpenAI adapter (official `openai` SDK). Selected with LLM_PROVIDER=openai."""

from typing import Any

import openai

from app.llm.base import CompletionRequest, LLMResponse
from app.llm.errors import (
    InvalidResponseError,
    LLMTimeoutError,
    ProviderError,
    ProviderUnavailableError,
    RateLimitedError,
)


class OpenAIChatModel:
    provider = "openai"

    def __init__(self, client: openai.AsyncOpenAI, model: str) -> None:
        self._client = client
        self.model = model

    async def complete(self, request: CompletionRequest) -> LLMResponse:
        try:
            result = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                temperature=request.options.temperature,
                max_completion_tokens=request.options.max_output_tokens,
                **response_format(request.json_schema),
            )
        except openai.APIError as exc:
            raise map_api_error(exc) from exc

        text = result.choices[0].message.content if result.choices else None
        if not text:
            raise InvalidResponseError("openai returned an empty response")
        usage = result.usage
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
        )


def response_format(json_schema: dict[str, Any] | None) -> dict[str, Any]:
    if json_schema is None:
        return {}
    # strict=False: strict mode rejects common Pydantic schemas (optional fields, defaults);
    # LLMClient validates the reply against the Pydantic model anyway.
    return {
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "response", "schema": json_schema, "strict": False},
        }
    }


def map_api_error(exc: openai.APIError) -> Exception:
    # Order matters: APITimeoutError is a subclass of APIConnectionError.
    if isinstance(exc, openai.APITimeoutError):
        return LLMTimeoutError("openai request timed out")
    if isinstance(exc, openai.APIConnectionError):
        return ProviderUnavailableError("openai connection failed")
    if isinstance(exc, openai.RateLimitError):
        return RateLimitedError("openai rate limit reached", parse_retry_after(exc))
    if isinstance(exc, openai.InternalServerError):
        return ProviderUnavailableError(f"openai server error {exc.status_code}")
    status = getattr(exc, "status_code", None)
    return ProviderError(f"openai request failed with status {status}")


def parse_retry_after(exc: openai.APIStatusError) -> float | None:
    try:
        return float(exc.response.headers["retry-after"])
    except (KeyError, ValueError):
        return None
