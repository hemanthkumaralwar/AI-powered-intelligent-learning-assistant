"""Google Gemini adapter (official `google-genai` SDK)."""

import re
from typing import Any

import httpx2
from google import genai
from google.genai import errors, types

from app.llm.base import CompletionRequest, LLMResponse
from app.llm.errors import (
    InvalidResponseError,
    LLMTimeoutError,
    ProviderError,
    ProviderUnavailableError,
    RateLimitedError,
)

# Gemini calls the assistant role "model" and takes system text separately.
_GEMINI_ROLES = {"user": "user", "assistant": "model"}
_RETRY_INFO_TYPE = "type.googleapis.com/google.rpc.RetryInfo"
_DURATION = re.compile(r"^(\d+(?:\.\d+)?)s$")


class GeminiChatModel:
    provider = "gemini"

    def __init__(self, client: genai.Client, model: str) -> None:
        self._client = client
        self.model = model

    async def complete(self, request: CompletionRequest) -> LLMResponse:
        try:
            result = await self._client.aio.models.generate_content(
                model=self.model,
                contents=to_gemini_contents(request),
                config=to_gemini_config(request),
            )
        except errors.APIError as exc:
            raise map_api_error(exc) from exc
        except httpx2.TimeoutException as exc:
            raise LLMTimeoutError("gemini request timed out") from exc
        except httpx2.TransportError as exc:
            raise ProviderUnavailableError("gemini connection failed") from exc

        if not result.text:
            # Happens when output is blocked by safety filters or cut off at zero tokens.
            raise InvalidResponseError("gemini returned an empty response")
        usage = result.usage_metadata
        return LLMResponse(
            text=result.text,
            model=self.model,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
        )


def to_gemini_contents(request: CompletionRequest) -> list[types.Content]:
    return [
        types.Content(role=_GEMINI_ROLES[message.role], parts=[types.Part(text=message.content)])
        for message in request.messages
        if message.role != "system"
    ]


def to_gemini_config(request: CompletionRequest) -> types.GenerateContentConfig:
    system_text = "\n\n".join(m.content for m in request.messages if m.role == "system")
    config: dict[str, Any] = {
        "system_instruction": system_text or None,
        "temperature": request.options.temperature,
        "max_output_tokens": request.options.max_output_tokens,
    }
    if request.json_schema is not None:
        config["response_mime_type"] = "application/json"
        config["response_json_schema"] = request.json_schema
    return types.GenerateContentConfig(**config)


def map_api_error(exc: errors.APIError) -> Exception:
    if exc.code == 429:
        return RateLimitedError("gemini rate limit reached", parse_retry_delay(exc.details))
    if exc.code is not None and exc.code >= 500:
        return ProviderUnavailableError(f"gemini server error {exc.code}")
    return ProviderError(f"gemini request failed with status {exc.code}")


def parse_retry_delay(details: Any) -> float | None:
    """Read the RetryInfo delay (e.g. "37s") from a Gemini error body, if present."""
    error = details.get("error") if isinstance(details, dict) else None
    entries = error.get("details") if isinstance(error, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("@type") == _RETRY_INFO_TYPE:
            match = _DURATION.match(str(entry.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return None
