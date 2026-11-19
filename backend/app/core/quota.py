"""In-memory usage quotas (sliding windows), shared by code runs and chat questions.

State lives in memory: correct for the single Render instance, reset on restart
(documented in PLAN.md). No locking is needed: `consume` never awaits, so on one event
loop it runs atomically.
"""

import time
from collections import deque
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass

MINUTE = 60.0
DAY = 24 * 60 * 60.0


class QuotaExceededError(Exception):
    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = retry_after


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
            # Drop idle keys so memory does not grow with every student who ever acted.
            self._events.pop(key, None)
        return events


@dataclass(frozen=True)
class QuotaRule:
    """`limit` events per `window` seconds, per user or (per_user=False) for everyone."""

    message: str
    limit: int
    window: float
    per_user: bool = True


class Quota:
    """Every rule must allow an event; a refused event is not counted against any rule."""

    def __init__(
        self, rules: Sequence[QuotaRule], clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._clock = clock
        self._rules = [(rule, SlidingWindow(rule.limit, rule.window)) for rule in rules]

    def consume(self, user_key: Hashable) -> None:
        """Count one event for `user_key`, or raise `QuotaExceededError` without counting."""
        now = self._clock()
        for rule, window in self._rules:
            wait = window.wait_time(_key(rule, user_key), now)
            if wait > 0:
                raise QuotaExceededError(rule.message, retry_after=wait)
        for rule, window in self._rules:
            window.record(_key(rule, user_key), now)


def _key(rule: QuotaRule, user_key: Hashable) -> Hashable:
    return user_key if rule.per_user else "*"
