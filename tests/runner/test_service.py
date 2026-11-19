import logging

import pytest

from app.core.quota import QuotaExceededError
from app.providers.errors import (
    InvalidResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from app.runner.base import RunRequest, RunResult
from app.runner.fake import FakeRunner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService, RunnerUnavailableError, UnsupportedLanguageError

pytestmark = pytest.mark.anyio

STUDENT_CODE = "print('student secret 42')"


def result(provider: str, outcome: str = "ok") -> RunResult:
    return RunResult(outcome, "out", "", "", 0, 5, provider)


def roomy_quota() -> RunQuota:
    return RunQuota(QuotaLimits(100, 1000, 1000))


class FakeSharer:
    languages = frozenset({"c", "python"})

    def __init__(self, outcome: str | Exception = "https://godbolt.org/z/x") -> None:
        self.outcome = outcome
        self.closed = False

    async def share(self, request: RunRequest) -> str:
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    async def aclose(self) -> None:
        self.closed = True


async def test_first_runner_answers() -> None:
    first, second = FakeRunner([result("first")], name="first"), FakeRunner(name="second")
    service = CodeRunnerService([first, second], None, roomy_quota())

    assert (await service.run("asha", RunRequest("python", "x"))).provider == "first"
    assert second.requests == []


async def test_program_failures_do_not_fall_through() -> None:
    first = FakeRunner([result("first", "compile_error")], name="first")
    second = FakeRunner(name="second")
    service = CodeRunnerService([first, second], None, roomy_quota())

    assert (await service.run("asha", RunRequest("c", "x"))).outcome == "compile_error"
    assert second.requests == []


@pytest.mark.parametrize(
    "error",
    [
        ProviderUnavailableError("down"),
        RateLimitedError("slow"),
        ProviderTimeoutError("t"),
        InvalidResponseError("junk"),
    ],
)
async def test_runner_failures_fall_through_to_the_next(error: Exception) -> None:
    first = FakeRunner([error], name="first")
    second = FakeRunner([result("second")], name="second")
    service = CodeRunnerService([first, second], None, roomy_quota())

    assert (await service.run("asha", RunRequest("python", "x"))).provider == "second"


async def test_runners_without_the_language_are_skipped() -> None:
    godbolt_like = FakeRunner(name="godbolt", languages={"c", "python"})
    judge0_like = FakeRunner([result("judge0")], name="judge0")
    service = CodeRunnerService([godbolt_like, judge0_like], None, roomy_quota())

    assert (await service.run("asha", RunRequest("sql", "select 1;"))).provider == "judge0"
    assert godbolt_like.requests == []


async def test_all_runners_failing_is_unavailable() -> None:
    service = CodeRunnerService(
        [FakeRunner([ProviderUnavailableError("a")]), FakeRunner([ProviderTimeoutError("b")])],
        None,
        roomy_quota(),
    )

    with pytest.raises(RunnerUnavailableError):
        await service.run("asha", RunRequest("c", "x"))


async def test_no_runner_for_language_is_unsupported() -> None:
    service = CodeRunnerService([FakeRunner(languages={"c"})], None, roomy_quota())

    with pytest.raises(UnsupportedLanguageError):
        await service.run("asha", RunRequest("sql", "x"))


async def test_quota_is_checked_before_running() -> None:
    runner = FakeRunner()
    service = CodeRunnerService([runner], None, RunQuota(QuotaLimits(1, 10, 10)))
    await service.run("asha", RunRequest("c", "x"))

    with pytest.raises(QuotaExceededError):
        await service.run("asha", RunRequest("c", "x"))
    assert len(runner.requests) == 1


async def test_logs_metadata_but_never_code_or_output(caplog: pytest.LogCaptureFixture) -> None:
    runners = [
        FakeRunner([ProviderUnavailableError("down")], name="first"),
        FakeRunner(name="second"),
    ]
    service = CodeRunnerService(runners, FakeSharer(), roomy_quota())

    with caplog.at_level(logging.INFO, logger="app.runner.service"):
        await service.run("asha", RunRequest("python", STUDENT_CODE, stdin="hidden-input"))
        await service.share(RunRequest("python", STUDENT_CODE))

    assert "runner=first error=ProviderUnavailableError" in caplog.text
    assert "runner=second language=python outcome=ok" in caplog.text
    assert "student secret" not in caplog.text and "hidden-input" not in caplog.text


# ---- share -------------------------------------------------------------------------------


async def test_share_returns_link() -> None:
    service = CodeRunnerService([FakeRunner()], FakeSharer(), roomy_quota())

    assert await service.share(RunRequest("c", "x")) == "https://godbolt.org/z/x"


@pytest.mark.parametrize("sharer", [None, FakeSharer()], ids=["no-sharer", "unsupported"])
async def test_share_unsupported_language(sharer: FakeSharer | None) -> None:
    service = CodeRunnerService([FakeRunner()], sharer, roomy_quota())

    with pytest.raises(UnsupportedLanguageError, match="sql"):
        await service.share(RunRequest("sql", "select 1;"))


async def test_share_failure_is_unavailable() -> None:
    service = CodeRunnerService(
        [FakeRunner()], FakeSharer(ProviderUnavailableError("x")), roomy_quota()
    )

    with pytest.raises(RunnerUnavailableError):
        await service.share(RunRequest("c", "x"))


async def test_aclose_closes_every_runner_and_the_sharer() -> None:
    runners, sharer = [FakeRunner(), FakeRunner()], FakeSharer()

    await CodeRunnerService(runners, sharer, roomy_quota()).aclose()
    await CodeRunnerService([FakeRunner()], None, roomy_quota()).aclose()

    assert all(r.closed for r in runners) and sharer.closed
