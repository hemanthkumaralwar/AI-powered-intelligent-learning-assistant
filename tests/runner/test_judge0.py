import base64
import json

import httpx2
import pytest

from app.providers.errors import (
    InvalidResponseError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)
from app.runner.base import MAX_OUTPUT_CHARS, RunRequest
from app.runner.judge0 import LANGUAGE_IDS, Judge0Runner

pytestmark = pytest.mark.anyio


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def runner(handler) -> Judge0Runner:
    client = httpx2.AsyncClient(
        base_url="https://judge0.test", transport=httpx2.MockTransport(handler)
    )
    return Judge0Runner(client, cpu_seconds=5, wall_seconds=10)


def reply(body: object, status: int = 200):
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json=body)

    return handler


def judged(status_id: int, **fields) -> dict:
    encoded = {k: b64(v) for k, v in fields.items() if k in ("stdout", "stderr", "compile_output")}
    rest = {k: v for k, v in fields.items() if k not in encoded}
    return {"status": {"id": status_id}, **encoded, **rest}


async def test_sends_base64_code_with_language_and_limits() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=judged(3, stdout="olleh\n", time="0.012", exit_code=0))

    result = await runner(handler).run(RunRequest("python", "print(input()[::-1])", "hello"))

    request = seen[0]
    assert request.url.path == "/submissions"
    assert request.url.params["base64_encoded"] == "true"
    assert request.url.params["wait"] == "true"
    body = json.loads(request.content)
    assert body["language_id"] == LANGUAGE_IDS["python"]
    assert base64.b64decode(body["source_code"]).decode() == "print(input()[::-1])"
    assert base64.b64decode(body["stdin"]).decode() == "hello"
    assert (body["cpu_time_limit"], body["wall_time_limit"]) == (5, 10)
    assert (result.outcome, result.stdout, result.exit_code, result.time_ms) == (
        "ok",
        "olleh\n",
        0,
        12,
    )
    assert result.provider == "judge0"


@pytest.mark.parametrize(
    ("status_id", "outcome"),
    [
        (3, "ok"),
        (5, "timeout"),
        (6, "compile_error"),
        (7, "runtime_error"),
        (8, "output_limit"),
        (9, "runtime_error"),
        (10, "runtime_error"),
        (11, "runtime_error"),
        (12, "runtime_error"),
    ],
)
async def test_maps_status_to_outcome(status_id: int, outcome: str) -> None:
    result = await runner(reply(judged(status_id, exit_code=1))).run(RunRequest("c", "x"))

    assert result.outcome == outcome


async def test_compile_error_carries_compiler_output_and_no_exit_code() -> None:
    body = judged(6, compile_output="main.c:1: error: 'x' undeclared", exit_code=None)

    result = await runner(reply(body)).run(RunRequest("c", "int main(){return x;}"))

    assert result.compile_output == "main.c:1: error: 'x' undeclared"
    assert result.exit_code is None


async def test_timeout_does_not_report_exit_code_zero() -> None:
    # Judge0 sends exit_code 0 for timeouts, which would read as success.
    result = await runner(reply(judged(5, exit_code=0, time="2.086"))).run(
        RunRequest("python", "x")
    )

    assert (result.outcome, result.exit_code) == ("timeout", None)


async def test_runtime_error_keeps_stderr_and_exit_code() -> None:
    body = judged(11, stderr="ZeroDivisionError", exit_code=1, time="1.061")

    result = await runner(reply(body)).run(RunRequest("python", "print(1/0)"))

    assert (result.stderr, result.exit_code, result.time_ms) == ("ZeroDivisionError", 1, 1061)


async def test_invalid_utf8_output_is_replaced_not_fatal() -> None:
    body = {"status": {"id": 3}, "stdout": base64.b64encode(b"ok \xff\xfe").decode()}

    result = await runner(reply(body)).run(RunRequest("c", "x"))

    assert result.stdout.startswith("ok ")


async def test_long_output_is_capped() -> None:
    result = await runner(reply(judged(3, stdout="x" * (MAX_OUTPUT_CHARS + 10)))).run(
        RunRequest("python", "x")
    )

    assert len(result.stdout) == MAX_OUTPUT_CHARS
    assert result.truncated is True


@pytest.mark.parametrize("status_id", [1, 2, 13, 14, None])
async def test_service_side_statuses_are_runner_failures(status_id: int | None) -> None:
    with pytest.raises(ProviderUnavailableError):
        await runner(reply({"status": {"id": status_id}})).run(RunRequest("c", "x"))


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (429, RateLimitedError),
        (500, ProviderUnavailableError),
        (503, ProviderUnavailableError),
        (400, ProviderRequestError),
        (422, ProviderRequestError),
    ],
)
async def test_http_errors_are_mapped(status: int, error: type[Exception]) -> None:
    with pytest.raises(error):
        await runner(reply({"error": "x"}, status)).run(RunRequest("c", "x"))


async def test_rate_limit_carries_retry_after() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(429, headers={"retry-after": "12"})

    with pytest.raises(RateLimitedError) as excinfo:
        await runner(handler).run(RunRequest("c", "x"))
    assert excinfo.value.retry_after == 12


@pytest.mark.parametrize(
    ("exc", "error"),
    [(httpx2.ReadTimeout, ProviderTimeoutError), (httpx2.ConnectError, ProviderUnavailableError)],
)
async def test_transport_errors_are_mapped(exc: type[Exception], error: type[Exception]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise exc("down", request=request)

    with pytest.raises(error):
        await runner(handler).run(RunRequest("c", "x"))


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(200, text="not json"),
        httpx2.Response(200, json=[1, 2]),
        httpx2.Response(200, json={"status": {"id": 3}, "stdout": "%%%not-base64"}),
    ],
    ids=["not-json", "not-object", "bad-base64"],
)
async def test_malformed_replies_are_invalid_responses(response: httpx2.Response) -> None:
    with pytest.raises(InvalidResponseError):
        await runner(lambda request: response).run(RunRequest("c", "x"))


async def test_aclose_closes_the_http_client() -> None:
    judge0 = runner(reply({}))
    await judge0.aclose()

    assert judge0._client.is_closed
