"""Judge0 CE adapter (open source; public instance at ce.judge0.com, no API key).

Covers all six course languages, including SQL via SQLite.
"""

import base64
from typing import Any

import httpx2

from app.providers.errors import InvalidResponseError, ProviderUnavailableError
from app.providers.http import check_status, translate_http_errors
from app.runner.base import Language, Outcome, RunRequest, RunResult, cap_output

# Judge0 language ids (checked against /languages on 2026-11-18; ids differ between
# Judge0 versions, so scripts/code_runner_smoke.py re-checks them).
LANGUAGE_IDS: dict[Language, int] = {
    "c": 103,  # C (GCC 14.1.0)
    "cpp": 105,  # C++ (GCC 14.1.0)
    "java": 91,  # Java (JDK 17.0.6); the public class must be named Main
    "python": 100,  # Python (3.12.5)
    "javascript": 97,  # JavaScript (Node.js 20.17.0)
    "sql": 82,  # SQL (SQLite 3.27.2)
}

# Judge0 status ids -> program outcome. 1/2 (queued/processing) and 13/14 (internal
# errors) are failures of the service, not of the program.
_OUTCOMES: dict[int, Outcome] = {
    3: "ok",
    5: "timeout",
    6: "compile_error",
    7: "runtime_error",  # SIGSEGV
    8: "output_limit",  # SIGXFSZ
    9: "runtime_error",  # SIGFPE
    10: "runtime_error",  # SIGABRT
    11: "runtime_error",  # NZEC (non-zero exit)
    12: "runtime_error",  # other
}
_FIELDS = "stdout,stderr,compile_output,status,time,exit_code"


class Judge0Runner:
    name = "judge0"
    languages = frozenset(LANGUAGE_IDS)

    def __init__(
        self, client: httpx2.AsyncClient, *, cpu_seconds: float, wall_seconds: float
    ) -> None:
        self._client = client
        self._cpu_seconds = cpu_seconds
        self._wall_seconds = wall_seconds

    async def run(self, request: RunRequest) -> RunResult:
        # base64 both ways: output may contain bytes that are not valid UTF-8.
        payload = {
            "language_id": LANGUAGE_IDS[request.language],
            "source_code": _b64(request.code),
            "stdin": _b64(request.stdin),
            "cpu_time_limit": self._cpu_seconds,
            "wall_time_limit": self._wall_seconds,
        }
        with translate_http_errors(self.name):
            response = await self._client.post(
                "/submissions",
                params={"base64_encoded": "true", "wait": "true", "fields": _FIELDS},
                json=payload,
            )
        check_status(response, self.name)
        return to_result(_json(response))

    async def aclose(self) -> None:
        await self._client.aclose()


def to_result(body: dict[str, Any]) -> RunResult:
    status = (body.get("status") or {}).get("id")
    outcome = _OUTCOMES.get(status)
    if outcome is None:
        raise ProviderUnavailableError(f"judge0 could not run the code (status {status})")
    (stdout, stderr, compile_output), truncated = cap_output(
        _unb64(body.get("stdout")), _unb64(body.get("stderr")), _unb64(body.get("compile_output"))
    )
    return RunResult(
        outcome=outcome,
        stdout=stdout,
        stderr=stderr,
        compile_output=compile_output,
        # Judge0 reports exit code 0 for timeouts; that would read as success.
        exit_code=None if outcome in ("compile_error", "timeout") else body.get("exit_code"),
        time_ms=_millis(body.get("time")),
        provider="judge0",
        truncated=truncated,
    )


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def _unb64(value: str | None) -> str:
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode(errors="replace")
    except ValueError as exc:
        raise InvalidResponseError("judge0 returned malformed output") from exc


def _millis(seconds: object) -> int | None:
    try:
        return round(float(seconds) * 1000)
    except (TypeError, ValueError):
        return None


def _json(response: httpx2.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise InvalidResponseError("judge0 returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise InvalidResponseError("judge0 returned an unexpected body")
    return body
