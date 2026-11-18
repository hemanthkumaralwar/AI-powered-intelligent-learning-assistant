import pytest

from app.runner.quota import DAY, MINUTE, QuotaExceededError, QuotaLimits, RunQuota, SlidingWindow


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def quota(
    clock: Clock, per_minute: int = 2, per_day: int = 5, global_per_minute: int = 100
) -> RunQuota:
    return RunQuota(QuotaLimits(per_minute, per_day, global_per_minute), clock)


def test_allows_up_to_the_per_minute_limit_then_refuses() -> None:
    clock = Clock()
    runs = quota(clock)
    runs.consume("asha")
    runs.consume("asha")

    with pytest.raises(QuotaExceededError, match="too often") as excinfo:
        runs.consume("asha")
    assert excinfo.value.retry_after == pytest.approx(MINUTE)


def test_window_slides() -> None:
    clock = Clock()
    runs = quota(clock)
    runs.consume("asha")
    clock.now += 30
    runs.consume("asha")

    clock.now += 30.001
    runs.consume("asha")  # the first run has left the 60 s window


def test_users_have_separate_allowances() -> None:
    runs = quota(Clock())
    runs.consume("asha")
    runs.consume("asha")

    runs.consume("ravi")


def test_daily_limit() -> None:
    clock = Clock()
    runs = quota(clock, per_minute=100, per_day=3)
    for _ in range(3):
        runs.consume("asha")
        clock.now += 61

    with pytest.raises(QuotaExceededError, match="today's limit") as excinfo:
        runs.consume("asha")
    assert 0 < excinfo.value.retry_after < DAY


def test_global_limit_is_shared_by_everyone() -> None:
    runs = quota(Clock(), per_minute=100, global_per_minute=2)
    runs.consume("asha")
    runs.consume("ravi")

    with pytest.raises(QuotaExceededError, match="busy"):
        runs.consume("meera")


def test_refused_runs_are_not_counted() -> None:
    clock = Clock()
    runs = quota(clock, per_minute=1, per_day=2)
    runs.consume("asha")
    for _ in range(5):
        with pytest.raises(QuotaExceededError):
            runs.consume("asha")

    clock.now += 61
    runs.consume("asha")  # day limit 2 is not exhausted by the refused attempts


def test_idle_keys_are_forgotten() -> None:
    window = SlidingWindow(limit=1, window=10)
    window.record("asha", now=0)

    assert window.wait_time("asha", now=5) == 5
    assert window.wait_time("asha", now=11) == 0
    assert "asha" not in window._events
