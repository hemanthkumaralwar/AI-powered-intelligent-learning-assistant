"""Builds the configured `LLMClient` from settings."""

from app.core.config import Settings
from app.llm.base import ChatModel
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.llm.gemini import GeminiChatModel
from app.llm.openai import OpenAIChatModel
from app.providers.gemini_sdk import make_gemini_client
from app.providers.keys import require_api_key
from app.providers.openai_sdk import make_openai_client
from app.providers.retry import RetryPolicy


def build_llm_client(settings: Settings) -> LLMClient:
    return LLMClient(
        build_chat_model(settings),
        timeout_seconds=settings.llm_timeout_seconds,
        retry_policy=RetryPolicy(max_attempts=settings.llm_max_attempts),
    )


def build_chat_model(settings: Settings) -> ChatModel:
    timeout = settings.llm_timeout_seconds
    match settings.llm_provider:
        case "gemini":
            key = require_api_key(settings.gemini_api_key, "GEMINI_API_KEY", "gemini")
            return GeminiChatModel(
                make_gemini_client(key, timeout),
                settings.gemini_model,
                settings.gemini_thinking_budget,
            )
        case "openai":
            key = require_api_key(settings.openai_api_key, "OPENAI_API_KEY", "openai")
            return OpenAIChatModel(make_openai_client(key, timeout), settings.openai_model)
        case "fake":
            return FakeChatModel()
