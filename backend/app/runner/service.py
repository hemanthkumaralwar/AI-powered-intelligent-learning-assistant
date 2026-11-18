"""Runs code on the first available runner, with quotas, and creates share links."""

import logging
import time
from collections.abc import Hashable, Sequence

from app.providers.errors import ProviderCallError
from app.runner.base import CodeRunner, RunRequest, RunResult, Sharer
from app.runner.quota import RunQuota

logger = logging.getLogger(__name__)


class RunnerUnavailableError(Exception):
    """No configured runner could run the code right now."""


class UnsupportedLanguageError(Exception):
    """The requested operation is not available for this language."""


class CodeRunnerService:
    """Tries runners in order; a runner failure (not a program failure) falls through.

    Never logs code, stdin or output: they are the student's work.
    """

    def __init__(
        self, runners: Sequence[CodeRunner], sharer: Sharer | None, quota: RunQuota
    ) -> None:
        self._runners = list(runners)
        self._sharer = sharer
        self._quota = quota

    async def run(self, user_key: Hashable, request: RunRequest) -> RunResult:
        candidates = [r for r in self._runners if request.language in r.languages]
        if not candidates:
            raise UnsupportedLanguageError(f"no runner supports {request.language}")
        self._quota.consume(user_key)
        for runner in candidates:
            started = time.perf_counter()
            try:
                result = await runner.run(request)
            except ProviderCallError as exc:
                logger.warning(
                    "code runner failed runner=%s error=%s", runner.name, type(exc).__name__
                )
                continue
            logger.info(
                "code run runner=%s language=%s outcome=%s latency_ms=%d",
                runner.name,
                request.language,
                result.outcome,
                (time.perf_counter() - started) * 1000,
            )
            return result
        raise RunnerUnavailableError("the code runner is unavailable")

    async def share(self, request: RunRequest) -> str:
        if self._sharer is None or request.language not in self._sharer.languages:
            raise UnsupportedLanguageError(f"share links are not available for {request.language}")
        try:
            url = await self._sharer.share(request)
        except ProviderCallError as exc:
            logger.warning("share link failed error=%s", type(exc).__name__)
            raise RunnerUnavailableError("the share service is unavailable") from exc
        logger.info("share link created language=%s", request.language)
        return url

    async def aclose(self) -> None:
        for closable in [*self._runners, self._sharer]:
            if closable is not None:
                await closable.aclose()
