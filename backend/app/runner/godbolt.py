"""Compiler Explorer (godbolt.org) adapters: fallback runner and share links.

Compiler Explorer can execute C, C++, Java and Python, but not JavaScript or SQL.
Its share links are public and permanent by design.
"""

import re
from typing import Any

import httpx2

from app.providers.errors import InvalidResponseError
from app.providers.http import check_status, translate_http_errors
from app.runner.base import Language, Outcome, RunRequest, RunResult, cap_output

# Compiler ids (checked against /api/compilers/<lang> on 2026-11-18).
COMPILERS: dict[Language, str] = {
    "c": "cg142",  # x86-64 gcc 14.2
    "cpp": "g142",  # x86-64 gcc 14.2
    "java": "java2502",  # jdk 25.0.2
    "python": "python312",  # Python 3.12
}
# Compiler Explorer's own language ids, used in share links.
_SITE_LANGUAGES: dict[Language, str] = {
    "c": "c",
    "cpp": "c++",
    "java": "java",
    "python": "python",
}
# Compiler diagnostics arrive with terminal colour codes.
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Compiler Explorer saves Java source under its own file name, so `public class Main`
# fails ("should be declared in a file named Main.java"). Judge0 requires `Main`, so
# course code uses it; dropping `public` from that one declaration runs identically.
_PUBLIC_MAIN = re.compile(r"\bpublic\s+((?:(?:final|abstract)\s+)*)class\s+Main\b")


def godbolt_source(request: RunRequest) -> str:
    """The code as Compiler Explorer needs it (only Java's `public class Main` changes)."""
    if request.language != "java":
        return request.code
    return _PUBLIC_MAIN.sub(r"\1class Main", request.code, count=1)


class GodboltRunner:
    name = "godbolt"
    languages = frozenset(COMPILERS)

    def __init__(self, client: httpx2.AsyncClient) -> None:
        self._client = client

    async def run(self, request: RunRequest) -> RunResult:
        body = {
            "source": godbolt_source(request),
            "options": {
                "userArguments": "",
                "executeParameters": {"args": [], "stdin": request.stdin},
                "compilerOptions": {"executorRequest": True},
                "filters": {"execute": True},
                "tools": [],
                "libraries": [],
            },
            "allowStoreCodeDebug": False,
        }
        compiler = COMPILERS[request.language]
        with translate_http_errors(self.name):
            response = await self._client.post(f"/api/compiler/{compiler}/compile", json=body)
        check_status(response, self.name)
        return to_result(_json(response))

    async def aclose(self) -> None:
        await self._client.aclose()


class GodboltSharer:
    """Saves code to a godbolt.org/z/... short link. The link is public and permanent."""

    languages = frozenset(COMPILERS)

    def __init__(self, client: httpx2.AsyncClient) -> None:
        self._client = client

    async def share(self, request: RunRequest) -> str:
        state = {
            "sessions": [
                {
                    "id": 1,
                    "language": _SITE_LANGUAGES[request.language],
                    "source": godbolt_source(request),
                    "compilers": [],
                    "executors": [
                        {
                            "compiler": {
                                "id": COMPILERS[request.language],
                                "libs": [],
                                "options": "",
                            },
                            "arguments": "",
                            "stdin": request.stdin,
                        }
                    ],
                }
            ]
        }
        with translate_http_errors("godbolt"):
            response = await self._client.post("/api/shortener", json=state)
        check_status(response, "godbolt")
        url = _json(response).get("url")
        if not isinstance(url, str) or not url.startswith("https://godbolt.org/z/"):
            raise InvalidResponseError("godbolt returned no share link")
        return url

    async def aclose(self) -> None:
        await self._client.aclose()


def to_result(body: dict[str, Any]) -> RunResult:
    build = body.get("buildResult") or {}
    compile_output = _text(build.get("stderr")) or _text(build.get("stdout"))
    built = build.get("code", 0) == 0
    (stdout, stderr, compile_output), truncated = cap_output(
        _text(body.get("stdout")) if built else "",
        _text(body.get("stderr")) if built else "",
        compile_output if not built else "",
    )
    outcome = _outcome(body, built)
    return RunResult(
        outcome=outcome,
        stdout=stdout,
        stderr=stderr,
        compile_output=compile_output,
        exit_code=body.get("code") if outcome in ("ok", "runtime_error") else None,
        time_ms=_millis(body.get("execTime")),
        provider="godbolt",
        truncated=truncated or bool(body.get("truncated")),
    )


def _outcome(body: dict[str, Any], built: bool) -> Outcome:
    if not built:
        return "compile_error"
    if body.get("timedOut"):
        return "timeout"
    return "ok" if body.get("code") == 0 else "runtime_error"


def _text(lines: object) -> str:
    if not isinstance(lines, list):
        return ""
    text = "\n".join(line.get("text", "") for line in lines if isinstance(line, dict))
    return _ANSI.sub("", text)


def _millis(value: object) -> int | None:
    try:
        return round(float(value))
    except (TypeError, ValueError):
        return None


def _json(response: httpx2.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise InvalidResponseError("godbolt returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise InvalidResponseError("godbolt returned an unexpected body")
    return body
