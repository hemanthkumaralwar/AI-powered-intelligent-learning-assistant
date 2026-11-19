"""A small in-memory cache: bounded size (least recently used goes first), optional expiry.

In memory on purpose: one Render instance, and everything cached can be rebuilt (course
content from Postgres, embeddings from the provider). No locking is needed: get/set
never await, so on one event loop they run atomically.
"""

import time
from collections import OrderedDict
from collections.abc import Callable, Hashable


class TTLCache[V]:
    def __init__(
        self,
        max_entries: int,
        ttl_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[Hashable, tuple[float, V]] = OrderedDict()

    def get(self, key: Hashable) -> V | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if self._ttl is not None and self._clock() - stored_at >= self._ttl:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def set(self, key: Hashable, value: V) -> None:
        self._entries[key] = (self._clock(), value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)
