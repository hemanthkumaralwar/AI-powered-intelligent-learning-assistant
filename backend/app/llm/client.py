"""`LLMClient`: the single entry point the rest of the app uses to talk to an LLM."""

import asyncio
import logging
import time
from collections.abc import Sequence

from pydantic import BaseModel, ValidationError

from app.llm.base import ChatMessage, ChatModel, CompletionRequest, GenerationOptions, LLMResponse
from app.providers.errors import InvalidResponseError, ProviderTimeoutError
from app.providers.retry import RetryPolicy, Sleep, call_with_retry

logger = logging.getLogger(__name__)


class LLMClient:
    """Validates input, enforces the timeout, retries, and logs metadata.

    Vendor-specific work lives in the injected `ChatModel`. Prompt and response text
    are never logged: they can contain student questions and code.
    """

    def __init__(
        self,
        chat_model: ChatModel,
        *,
        timeout_seconds: float,
        retry_policy: RetryPolicy,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._chat_model = chat_model
        self._timeout_seconds = timeout_seconds
        self._retry_policy = retry_policy
        self._sleep = sleep

    @property
    def provider(self) -> str:
        return self._chat_model.provider

    @property
    def model(self) -> str:
        return self._chat_model.model

    async def aclose(self) -> None:
        await self._chat_model.aclose()

    async def chat(
        self, messages: Sequence[ChatMessage], options: GenerationOptions | None = None
    ) -> LLMResponse:
        """Return the model's free-text reply to `messages`."""
        return await self._run(self._build_request(messages, options, json_schema=None))

    async def generate_json[SchemaT: BaseModel](
        self,
        messages: Sequence[ChatMessage],
        schema: type[SchemaT],
        options: GenerationOptions | None = None,
    ) -> SchemaT:
        """Return the model's reply parsed and validated as `schema`."""
        request = self._build_request(messages, options, json_schema=schema.model_json_schema())
        response = await self._run(request)
        if response.truncated:
            raise InvalidResponseError(
                f"{self.provider} reply was cut off at max_output_tokens; raise the limit"
            )
        try:
            return schema.model_validate_json(response.text)
        except ValidationError as exc:
            # The validation detail may quote model output, so it stays out of the message.
            raise InvalidResponseError(
                f"{self.provider} reply did not match {schema.__name__}"
            ) from exc

    @staticmethod
    def _build_request(
        messages: Sequence[ChatMessage],
        options: GenerationOptions | None,
        json_schema: dict | None,
    ) -> CompletionRequest:
        if not any(message.role != "system" for message in messages):
            raise ValueError("messages must include at least one user or assistant message")
        return CompletionRequest(
            messages=tuple(messages),
            options=options or GenerationOptions(),
            json_schema=json_schema,
        )

    async def _run(self, request: CompletionRequest) -> LLMResponse:
        started = time.perf_counter()
        response, attempts = await call_with_retry(
            lambda: self._complete_once(request), self._retry_policy, self._sleep
        )
        logger.info(
            "llm call provider=%s model=%s attempts=%d latency_ms=%d "
            "input_tokens=%s output_tokens=%s truncated=%s",
            self.provider,
            response.model,
            attempts,
            (time.perf_counter() - started) * 1000,
            response.input_tokens,
            response.output_tokens,
            response.truncated,
        )
        return response

    async def _complete_once(self, request: CompletionRequest) -> LLMResponse:
        # Enforced here, not only in each SDK, so every provider times out the same way.
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._chat_model.complete(request)
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"{self.provider} did not respond within {self._timeout_seconds}s"
            ) from exc
