"""Client-side spacing to stay under a provider's per-minute quota."""

import asyncio
import time
from collections.abc import Awaitable, Callable

type Clock = Callable[[], float]
type Sleep = Callable[[float], Awaitable[None]]


class RateLimiter:
    """Allows at most `units_per_minute` units, spread evenly over time.

    A call reserves `cost` units: one per request, or one per *text* for providers that
    meter batch items individually (Gemini embeddings count each text in a batch as a
    request). After a call of cost n, the next one waits n * 60 / units_per_minute
    seconds, so the long-run rate never exceeds the limit.

    Smooth spacing rather than bursts: free tiers count usage per rolling minute, so an
    evenly spaced stream avoids 429s instead of reacting to them.
    """

    def __init__(
        self,
        units_per_minute: int,
        *,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if units_per_minute < 1:
            raise ValueError("units_per_minute must be at least 1")
        self._seconds_per_unit = 60.0 / units_per_minute
        self._clock = clock
        self._sleep = sleep
        self._next_allowed = float("-inf")
        # Serialises waiters so concurrent callers each get their own slot.
        self._lock = asyncio.Lock()

    async def acquire(self, cost: int = 1) -> None:
        """Wait until the previous reservation has elapsed, then reserve `cost` units."""
        if cost < 1:
            raise ValueError("cost must be at least 1")
        async with self._lock:
            now = self._clock()
            wait = self._next_allowed - now
            if wait > 0:
                await self._sleep(wait)
            self._next_allowed = max(now, self._next_allowed) + cost * self._seconds_per_unit
