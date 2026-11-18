import asyncio

import pytest

from app.providers.rate_limit import RateLimiter


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def limiter(rpm: int, fake: FakeTime) -> RateLimiter:
    return RateLimiter(rpm, clock=fake.clock, sleep=fake.sleep)


def test_rejects_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        RateLimiter(0)


@pytest.mark.anyio
async def test_first_request_does_not_wait() -> None:
    fake = FakeTime()

    await limiter(60, fake).acquire()

    assert fake.sleeps == []


@pytest.mark.anyio
async def test_back_to_back_requests_are_spaced() -> None:
    fake = FakeTime()
    rate = limiter(60, fake)

    await rate.acquire()
    await rate.acquire()

    assert fake.sleeps == [1.0]


@pytest.mark.anyio
async def test_no_wait_once_interval_has_passed() -> None:
    fake = FakeTime()
    rate = limiter(30, fake)

    await rate.acquire()
    fake.now = 5.0
    await rate.acquire()

    assert fake.sleeps == []


@pytest.mark.anyio
async def test_concurrent_callers_each_get_their_own_slot() -> None:
    fake = FakeTime()
    rate = limiter(60, fake)

    await asyncio.gather(rate.acquire(), rate.acquire(), rate.acquire())

    assert fake.sleeps == [1.0, 2.0]
