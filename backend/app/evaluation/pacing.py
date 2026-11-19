"""A paced LLM client for evaluation scripts, which fire many calls in a row."""

from app.core.config import Settings
from app.llm.base import ChatModel, CompletionRequest, LLMResponse
from app.llm.client import LLMClient
from app.llm.factory import build_chat_model
from app.providers.rate_limit import RateLimiter
from app.providers.retry import RetryPolicy


class PacedChatModel:
    """Spaces out every call (rewrites, answers, judge, coding) to stay in the free tier."""

    def __init__(self, inner: ChatModel, limiter: RateLimiter) -> None:
        self._inner = inner
        self._limiter = limiter
        self.provider = inner.provider
        self.model = inner.model

    async def complete(self, request: CompletionRequest) -> LLMResponse:
        await self._limiter.acquire()
        return await self._inner.complete(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def paced_llm(settings: Settings, per_minute: int) -> LLMClient:
    """One LLM client for every model call of an evaluation run."""
    return LLMClient(
        PacedChatModel(build_chat_model(settings), RateLimiter(per_minute)),
        timeout_seconds=settings.llm_timeout_seconds,
        retry_policy=RetryPolicy(max_attempts=settings.llm_max_attempts),
    )
