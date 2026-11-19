import pytest

from app.core.cache import TTLCache


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_values_expire_after_the_ttl() -> None:
    clock = Clock()
    cache: TTLCache[str] = TTLCache(10, ttl_seconds=60, clock=clock)
    cache.set("k", "v")

    clock.now += 59.9
    assert cache.get("k") == "v"
    clock.now += 0.1
    assert cache.get("k") is None and len(cache) == 0


def test_zero_ttl_means_nothing_is_cached() -> None:
    cache: TTLCache[str] = TTLCache(10, ttl_seconds=0)
    cache.set("k", "v")

    assert cache.get("k") is None


def test_least_recently_used_entry_is_dropped_first() -> None:
    cache: TTLCache[int] = TTLCache(2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")  # a is now the most recent

    cache.set("c", 3)

    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (1, None, 3)


def test_clear_and_size_limit() -> None:
    cache: TTLCache[int] = TTLCache(5)
    cache.set("a", 1)
    cache.clear()

    assert cache.get("a") is None
    with pytest.raises(ValueError, match="at least 1"):
        TTLCache(0)
