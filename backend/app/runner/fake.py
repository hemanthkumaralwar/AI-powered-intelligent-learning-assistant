"""Offline `CodeRunner` for tests and keyless development."""

from collections import deque
from collections.abc import Iterable

from app.runner.base import LANGUAGES, RunRequest, RunResult

ScriptStep = RunResult | Exception


class FakeRunner:
    """Replays scripted results in order (an `Exception` is raised instead).

    With an empty script it echoes the code's line count, so dev flows work offline.
    """

    def __init__(
        self,
        script: Iterable[ScriptStep] = (),
        *,
        name: str = "fake",
        languages: Iterable[str] = LANGUAGES,
    ) -> None:
        self._script = deque(script)
        self.name = name
        self.languages = frozenset(languages)
        self.requests: list[RunRequest] = []
        self.closed = False

    async def run(self, request: RunRequest) -> RunResult:
        self.requests.append(request)
        step = self._script.popleft() if self._script else None
        if isinstance(step, Exception):
            raise step
        return step or RunResult(
            outcome="ok",
            stdout=f"fake run: {len(request.code.splitlines())} line(s)\n",
            stderr="",
            compile_output="",
            exit_code=0,
            time_ms=0,
            provider=self.name,
        )

    async def aclose(self) -> None:
        self.closed = True
