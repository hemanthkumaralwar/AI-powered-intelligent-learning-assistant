"""Provider-neutral types for running student code on an external sandbox.

Student code never runs on our server: every `CodeRunner` sends it to a remote service
(Judge0 CE or Compiler Explorer) that executes it in its own sandbox.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

Language = Literal["c", "cpp", "java", "python", "javascript", "sql"]
LANGUAGES: tuple[Language, ...] = ("c", "cpp", "java", "python", "javascript", "sql")

# What happened to the *program*. A failing program is a normal result, not an error;
# errors are reserved for the runner service itself (see app.providers.errors).
Outcome = Literal["ok", "compile_error", "runtime_error", "timeout", "output_limit"]

# Per-stream cap on what we return; long-running print loops are common in exercises.
MAX_OUTPUT_CHARS = 64 * 1024


@dataclass(frozen=True)
class RunRequest:
    language: Language
    code: str
    stdin: str = ""


@dataclass(frozen=True)
class RunResult:
    outcome: Outcome
    stdout: str
    stderr: str
    compile_output: str
    exit_code: int | None
    time_ms: int | None
    provider: str
    truncated: bool = False


class CodeRunner(Protocol):
    """One remote execution service. Maps its failures onto `app.providers.errors`."""

    name: str
    languages: frozenset[Language]

    async def run(self, request: RunRequest) -> RunResult: ...

    async def aclose(self) -> None: ...


class Sharer(Protocol):
    """Creates a public link that opens the code in an online editor."""

    languages: frozenset[Language]

    async def share(self, request: RunRequest) -> str: ...

    async def aclose(self) -> None: ...


def cap_output(*streams: str) -> tuple[list[str], bool]:
    """Cut each stream to MAX_OUTPUT_CHARS; report whether anything was cut."""
    capped = [stream[:MAX_OUTPUT_CHARS] for stream in streams]
    return capped, any(len(stream) > MAX_OUTPUT_CHARS for stream in streams)
