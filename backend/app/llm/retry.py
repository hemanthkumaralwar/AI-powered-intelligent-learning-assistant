"""Retry with exponential backoff for transient LLM failures."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.llm.errors import RETRYABLE_ERRORS, RateLimitedError

type Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    # Longest wait we accept. A longer provider retry-after (e.g. the free-tier daily
    # quota) fails fast instead of keeping a student's request hanging.
    max_delay: float = 20.0

    def backoff(self, attempt: int) -> float:
        """Delay before retry number `attempt` (1-based): 1s, 2s, 4s ... capped."""
        return min(self.max_delay, self.base_delay * 2 ** (attempt - 1))


def delay_before_retry(error: Exception, attempt: int, policy: RetryPolicy) -> float | None:
    """Seconds to wait before retrying, or None when the error must be raised now."""
    if not isinstance(error, RETRYABLE_ERRORS) or attempt >= policy.max_attempts:
        return None
    delay = policy.backoff(attempt)
    if isinstance(error, RateLimitedError) and error.retry_after is not None:
        if error.retry_after > policy.max_delay:
            return None
        delay = max(delay, error.retry_after)
    return delay


async def call_with_retry[T](
    operation: Callable[[], Awaitable[T]], policy: RetryPolicy, sleep: Sleep
) -> tuple[T, int]:
    """Run `operation`, retrying transient errors. Returns (result, attempts used)."""
    attempt = 1
    while True:
        try:
            return await operation(), attempt
        except Exception as error:
            delay = delay_before_retry(error, attempt, policy)
            if delay is None:
                raise
            await sleep(delay)
            attempt += 1
