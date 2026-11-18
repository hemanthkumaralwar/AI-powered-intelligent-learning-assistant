"""OpenAI adapter (official `openai` SDK). Selected with LLM_PROVIDER=openai."""

from typing import Any

import openai

from app.llm.base import CompletionRequest, LLMResponse
from app.providers.errors import InvalidResponseError
from app.providers.openai_sdk import translate_openai_errors


class OpenAIChatModel:
    provider = "openai"

    def __init__(self, client: openai.AsyncOpenAI, model: str) -> None:
        self._client = client
        self.model = model

    async def complete(self, request: CompletionRequest) -> LLMResponse:
        with translate_openai_errors():
            result = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                temperature=request.options.temperature,
                max_completion_tokens=request.options.max_output_tokens,
                **response_format(request.json_schema),
            )

        choice = result.choices[0] if result.choices else None
        text = choice.message.content if choice else None
        if not text:
            raise InvalidResponseError("openai returned an empty response")
        usage = result.usage
        return LLMResponse(
            text=text,
            model=self.model,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            truncated=choice.finish_reason == "length",
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
