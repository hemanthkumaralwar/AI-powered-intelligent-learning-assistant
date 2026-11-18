"""Builds the configured `LLMClient` from settings."""

import openai
from google import genai
from google.genai import types
from pydantic import SecretStr

from app.core.config import Settings
from app.llm.base import ChatModel
from app.llm.client import LLMClient
from app.llm.errors import LLMConfigurationError
from app.llm.fake import FakeChatModel
from app.llm.gemini import GeminiChatModel
from app.llm.openai import OpenAIChatModel
from app.llm.retry import RetryPolicy


def build_llm_client(settings: Settings) -> LLMClient:
    return LLMClient(
        build_chat_model(settings),
        timeout_seconds=settings.llm_timeout_seconds,
        retry_policy=RetryPolicy(max_attempts=settings.llm_max_attempts),
    )


def build_chat_model(settings: Settings) -> ChatModel:
    # SDK retries stay off (Gemini's default; max_retries=0 for OpenAI): LLMClient retries.
    timeout = settings.llm_timeout_seconds
    match settings.llm_provider:
        case "gemini":
            client = genai.Client(
                api_key=_require_key(settings.gemini_api_key, "GEMINI_API_KEY", "gemini"),
                http_options=types.HttpOptions(timeout=int(timeout * 1000)),
            )
            return GeminiChatModel(client, settings.gemini_model, settings.gemini_thinking_budget)
        case "openai":
            client = openai.AsyncOpenAI(
                api_key=_require_key(settings.openai_api_key, "OPENAI_API_KEY", "openai"),
                timeout=timeout,
                max_retries=0,
            )
            return OpenAIChatModel(client, settings.openai_model)
        case "fake":
            return FakeChatModel()


def _require_key(key: SecretStr | None, env_name: str, provider: str) -> str:
    value = key.get_secret_value().strip() if key else ""
    if not value:
        raise LLMConfigurationError(f"{env_name} is required when LLM_PROVIDER={provider}")
    return value
