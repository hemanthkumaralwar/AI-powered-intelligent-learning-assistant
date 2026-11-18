"""In-memory run quotas: per student (minute and day) and for the whole app (minute).

All runs leave Render from one IP, so the free runners' per-IP allowance is shared by
every student; the app-wide limit protects it. State lives in memory: correct for the
single Render instance, reset on restart (documented in PLAN.md).

No locking is needed: `consume` never awaits, so on one event loop it runs atomically.
"""

import time
from collections import deque
from collections.abc import Callable, Hashable
from dataclasses import dataclass

MINUTE = 60.0
DAY = 24 * 60 * 60.0


class QuotaExceededError(Exception):
    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class QuotaLimits:
    per_user_per_minute: int
    per_user_per_day: int
    global_per_minute: int


class SlidingWindow:
    """At most `limit` events per `window` seconds for each key."""

    def __init__(self, limit: int, window: float) -> None:
        self._limit = limit
        self._window = window
        self._events: dict[Hashable, deque[float]] = {}

    def wait_time(self, key: Hashable, now: float) -> float:
        """Seconds until `key` may act again (0 if it may act now)."""
        events = self._prune(key, now)
        if len(events) < self._limit:
            return 0.0
        return events[0] + self._window - now

    def record(self, key: Hashable, now: float) -> None:
        self._events.setdefault(key, deque()).append(now)

    def _prune(self, key: Hashable, now: float) -> deque[float]:
        events = self._events.get(key, deque())
        while events and events[0] <= now - self._window:
            events.popleft()
        if not events:
            # Drop idle keys so memory does not grow with every student who ever ran code.
            self._events.pop(key, None)
        return events


@dataclass(frozen=True)
class _Limit:
    message: str
    per_user: bool
    window: SlidingWindow

    def key(self, user_key: Hashable) -> Hashable:
        return user_key if self.per_user else "*"


class RunQuota:
    def __init__(self, limits: QuotaLimits, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._limits = [
            _Limit(
                "You are running code too often; wait a moment.",
                per_user=True,
                window=SlidingWindow(limits.per_user_per_minute, MINUTE),
            ),
            _Limit(
                "You have reached today's limit for running code.",
                per_user=True,
                window=SlidingWindow(limits.per_user_per_day, DAY),
            ),
            _Limit(
                "The code runner is busy; try again in a moment.",
                per_user=False,
                window=SlidingWindow(limits.global_per_minute, MINUTE),
            ),
        ]

    def consume(self, user_key: Hashable) -> None:
        """Count one run for `user_key`, or raise `QuotaExceededError` without counting."""
        now = self._clock()
        for limit in self._limits:
            wait = limit.window.wait_time(limit.key(user_key), now)
            if wait > 0:
                raise QuotaExceededError(limit.message, retry_after=wait)
        for limit in self._limits:
            limit.window.record(limit.key(user_key), now)
