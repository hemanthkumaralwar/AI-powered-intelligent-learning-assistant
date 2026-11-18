"""Builds the `CodeRunnerService` from settings."""

import httpx2

from app.core.config import RunnerName, Settings
from app.providers.http import USER_AGENT
from app.runner.base import CodeRunner
from app.runner.fake import FakeRunner
from app.runner.godbolt import GodboltRunner, GodboltSharer
from app.runner.judge0 import Judge0Runner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService


def build_code_runner_service(settings: Settings) -> CodeRunnerService:
    """App-lifetime service; call `aclose()` at shutdown to release HTTP connections."""
    runners = [_build_runner(name, settings) for name in settings.code_runners]
    sharer = GodboltSharer(_client(settings.godbolt_base_url, settings))
    quota = RunQuota(
        QuotaLimits(
            per_user_per_minute=settings.code_runs_per_user_per_minute,
            per_user_per_day=settings.code_runs_per_user_per_day,
            global_per_minute=settings.code_runs_global_per_minute,
        )
    )
    return CodeRunnerService(runners, sharer, quota)


def _build_runner(name: RunnerName, settings: Settings) -> CodeRunner:
    match name:
        case "judge0":
            return Judge0Runner(
                _client(settings.judge0_base_url, settings),
                cpu_seconds=settings.code_cpu_seconds,
                wall_seconds=settings.code_wall_seconds,
            )
        case "godbolt":
            return GodboltRunner(_client(settings.godbolt_base_url, settings))
        case "fake":
            return FakeRunner()


def _client(base_url: str, settings: Settings) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        base_url=base_url,
        timeout=settings.code_runner_timeout_seconds,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
