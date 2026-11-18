import pytest

from app.providers.errors import (
    InvalidResponseError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from app.providers.retry import RetryPolicy, call_with_retry, delay_before_retry

POLICY = RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=20.0)


class Recorder:
    def __init__(self, outcomes: list) -> None:
        self.outcomes = outcomes
        self.calls = 0
        self.sleeps: list[float] = []

    async def operation(self) -> str:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)


def test_backoff_doubles_and_caps() -> None:
    policy = RetryPolicy(base_delay=1.0, max_delay=5.0)

    assert [policy.backoff(n) for n in (1, 2, 3, 4)] == [1.0, 2.0, 4.0, 5.0]


@pytest.mark.parametrize(
    "error",
    [ProviderTimeoutError("t"), ProviderUnavailableError("u"), RateLimitedError("r")],
)
def test_transient_errors_are_retried(error: Exception) -> None:
    assert delay_before_retry(error, attempt=1, policy=POLICY) == 1.0


@pytest.mark.parametrize(
    "error", [ProviderRequestError("p"), InvalidResponseError("i"), ValueError("v")]
)
def test_permanent_errors_are_not_retried(error: Exception) -> None:
    assert delay_before_retry(error, attempt=1, policy=POLICY) is None


def test_no_retry_after_last_attempt() -> None:
    assert delay_before_retry(ProviderTimeoutError("t"), attempt=3, policy=POLICY) is None


def test_short_retry_after_is_respected() -> None:
    error = RateLimitedError("r", retry_after=7.0)

    assert delay_before_retry(error, attempt=1, policy=POLICY) == 7.0


def test_retry_after_beyond_cap_fails_fast() -> None:
    error = RateLimitedError("daily quota", retry_after=3600.0)

    assert delay_before_retry(error, attempt=1, policy=POLICY) is None


@pytest.mark.anyio
async def test_succeeds_after_transient_failures() -> None:
    recorder = Recorder([ProviderUnavailableError("u"), ProviderTimeoutError("t"), "ok"])

    result, attempts = await call_with_retry(recorder.operation, POLICY, recorder.sleep)

    assert (result, attempts) == ("ok", 3)
    assert recorder.sleeps == [1.0, 2.0]


@pytest.mark.anyio
async def test_raises_last_error_when_attempts_run_out() -> None:
    recorder = Recorder(
        [ProviderTimeoutError("1"), ProviderTimeoutError("2"), ProviderTimeoutError("3")]
    )

    with pytest.raises(ProviderTimeoutError, match="3"):
        await call_with_retry(recorder.operation, POLICY, recorder.sleep)
    assert recorder.calls == 3


@pytest.mark.anyio
async def test_permanent_error_raises_without_sleeping() -> None:
    recorder = Recorder([ProviderRequestError("bad key")])

    with pytest.raises(ProviderRequestError):
        await call_with_retry(recorder.operation, POLICY, recorder.sleep)
    assert recorder.sleeps == []
