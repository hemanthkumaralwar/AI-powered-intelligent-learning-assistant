"""Client-side request spacing to stay under a provider's requests-per-minute quota."""

import asyncio
import time
from collections.abc import Awaitable, Callable

type Clock = Callable[[], float]
type Sleep = Callable[[float], Awaitable[None]]


class RateLimiter:
    """Spaces calls at least `60 / requests_per_minute` seconds apart.

    Smooth spacing rather than bursts: free tiers count requests per rolling minute,
    so an evenly spaced stream avoids 429s instead of reacting to them.
    """

    def __init__(
        self,
        requests_per_minute: int,
        *,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be at least 1")
        self._interval = 60.0 / requests_per_minute
        self._clock = clock
        self._sleep = sleep
        self._next_allowed = float("-inf")
        # Serialises waiters so concurrent callers each get their own slot.
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until the next request slot is free, then claim it."""
        async with self._lock:
            now = self._clock()
            wait = self._next_allowed - now
            if wait > 0:
                await self._sleep(wait)
            self._next_allowed = max(now, self._next_allowed) + self._interval
