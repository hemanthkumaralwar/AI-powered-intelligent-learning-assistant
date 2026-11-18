"""Google Gemini chat adapter (official `google-genai` SDK)."""

from typing import Any

from google import genai
from google.genai import types

from app.llm.base import CompletionRequest, LLMResponse
from app.providers.errors import InvalidResponseError
from app.providers.gemini_sdk import translate_gemini_errors

# Gemini calls the assistant role "model" and takes system text separately.
_GEMINI_ROLES = {"user": "user", "assistant": "model"}


class GeminiChatModel:
    provider = "gemini"

    def __init__(self, client: genai.Client, model: str, thinking_budget: int = 0) -> None:
        self._client = client
        self.model = model
        self._thinking_budget = thinking_budget

    async def complete(self, request: CompletionRequest) -> LLMResponse:
        with translate_gemini_errors():
            result = await self._client.aio.models.generate_content(
                model=self.model,
                contents=to_gemini_contents(request),
                config=to_gemini_config(request, self._thinking_budget),
            )

        if not result.text:
            # Happens when output is blocked by safety filters or cut off at zero tokens.
            raise InvalidResponseError("gemini returned an empty response")
        usage = result.usage_metadata
        finish_reason = result.candidates[0].finish_reason if result.candidates else None
        return LLMResponse(
            text=result.text,
            model=self.model,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
            truncated=finish_reason == types.FinishReason.MAX_TOKENS,
        )


def to_gemini_contents(request: CompletionRequest) -> list[types.Content]:
    return [
        types.Content(role=_GEMINI_ROLES[message.role], parts=[types.Part(text=message.content)])
        for message in request.messages
        if message.role != "system"
    ]


def to_gemini_config(
    request: CompletionRequest, thinking_budget: int = 0
) -> types.GenerateContentConfig:
    system_text = "\n\n".join(m.content for m in request.messages if m.role == "system")
    config: dict[str, Any] = {
        "system_instruction": system_text or None,
        "temperature": request.options.temperature,
        # Gemini counts thinking tokens against max_output_tokens. Adding the thinking
        # budget keeps the caller's limit for the visible answer, so thinking cannot
        # cut the answer short.
        "max_output_tokens": request.options.max_output_tokens + thinking_budget,
        "thinking_config": types.ThinkingConfig(thinking_budget=thinking_budget),
    }
    if request.json_schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_json_schema"] = request.json_schema
    return types.GenerateContentConfig(**config)
