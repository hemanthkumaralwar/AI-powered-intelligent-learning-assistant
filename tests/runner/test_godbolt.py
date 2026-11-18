import json

import httpx2
import pytest

from app.providers.errors import InvalidResponseError, ProviderUnavailableError, RateLimitedError
from app.runner.base import RunRequest
from app.runner.godbolt import COMPILERS, GodboltRunner, GodboltSharer, godbolt_source

pytestmark = pytest.mark.anyio


def client(handler) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        base_url="https://godbolt.test", transport=httpx2.MockTransport(handler)
    )


def reply(body: object, status: int = 200):
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json=body)

    return handler


def lines(*texts: str) -> list[dict]:
    return [{"text": text} for text in texts]


async def test_run_posts_to_the_language_compiler_with_stdin() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(
            200,
            json={
                "code": 0,
                "didExecute": True,
                "timedOut": False,
                "truncated": False,
                "execTime": "24",
                "stdout": lines("cba"),
                "stderr": [],
                "buildResult": {"code": 0},
            },
        )

    result = await GodboltRunner(client(handler)).run(
        RunRequest("python", "print(input()[::-1])", "abc")
    )

    assert seen[0].url.path == f"/api/compiler/{COMPILERS['python']}/compile"
    body = json.loads(seen[0].content)
    assert body["source"] == "print(input()[::-1])"
    assert body["options"]["executeParameters"]["stdin"] == "abc"
    assert body["options"]["filters"]["execute"] is True
    assert (result.outcome, result.stdout, result.exit_code, result.time_ms) == ("ok", "cba", 0, 24)
    assert result.provider == "godbolt"


async def test_build_failure_is_compile_error_with_colour_codes_removed() -> None:
    body = {
        "code": -1,
        "didExecute": False,
        "timedOut": False,
        "stdout": [],
        "stderr": lines("Build failed"),
        "buildResult": {
            "code": 1,
            "stderr": lines(
                "\x1b[01m\x1b[K<source>:1:24:\x1b[m\x1b[K "
                "\x1b[01;31m\x1b[Kerror: \x1b[m\x1b[K'x' undeclared"
            ),
        },
    }

    result = await GodboltRunner(client(reply(body))).run(RunRequest("c", "int main(){return x;}"))

    assert result.outcome == "compile_error"
    assert result.compile_output == "<source>:1:24: error: 'x' undeclared"
    assert "\x1b" not in result.compile_output
    assert (result.stdout, result.stderr, result.exit_code) == ("", "", None)


async def test_nonzero_exit_is_runtime_error() -> None:
    body = {
        "code": 1,
        "timedOut": False,
        "stdout": [],
        "stderr": lines("Traceback", "ZeroDivisionError"),
        "buildResult": {"code": 0},
    }

    result = await GodboltRunner(client(reply(body))).run(RunRequest("python", "print(1/0)"))

    assert (result.outcome, result.exit_code) == ("runtime_error", 1)
    assert result.stderr == "Traceback\nZeroDivisionError"


async def test_timed_out_program_is_timeout() -> None:
    body = {
        "code": 143,
        "timedOut": True,
        "stdout": [],
        "stderr": lines("Killed"),
        "buildResult": {"code": 0},
        "execTime": "not-a-number",
    }

    result = await GodboltRunner(client(reply(body))).run(RunRequest("c", "for(;;);"))

    assert (result.outcome, result.exit_code, result.time_ms) == ("timeout", None, None)


async def test_truncation_flag_is_passed_through() -> None:
    body = {"code": 0, "stdout": "not-a-list", "truncated": True, "buildResult": {"code": 0}}

    result = await GodboltRunner(client(reply(body))).run(RunRequest("c", "x"))

    assert (result.stdout, result.truncated) == ("", True)


async def test_runner_maps_http_errors() -> None:
    with pytest.raises(RateLimitedError):
        await GodboltRunner(client(reply({}, 429))).run(RunRequest("c", "x"))
    with pytest.raises(ProviderUnavailableError):
        await GodboltRunner(client(reply({}, 502))).run(RunRequest("c", "x"))


@pytest.mark.parametrize(
    "response", [httpx2.Response(200, text="<html>"), httpx2.Response(200, json=[])]
)
async def test_runner_rejects_malformed_replies(response: httpx2.Response) -> None:
    with pytest.raises(InvalidResponseError):
        await GodboltRunner(client(lambda request: response)).run(RunRequest("c", "x"))


def test_runner_and_sharer_cover_the_same_four_languages() -> None:
    assert GodboltRunner.languages == GodboltSharer.languages == {"c", "cpp", "java", "python"}


# ---- share links -------------------------------------------------------------------------


async def test_share_saves_state_and_returns_short_link() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"url": "https://godbolt.org/z/abc123"})

    url = await GodboltSharer(client(handler)).share(RunRequest("cpp", "int main(){}"))

    assert url == "https://godbolt.org/z/abc123"
    assert seen[0].url.path == "/api/shortener"
    session = json.loads(seen[0].content)["sessions"][0]
    assert (session["language"], session["source"]) == ("c++", "int main(){}")
    assert session["executors"][0]["compiler"]["id"] == COMPILERS["cpp"]


@pytest.mark.parametrize(
    "body",
    [{}, {"url": 42}, {"url": "https://evil.example/z/abc"}, {"url": "http://godbolt.org/z/x"}],
)
async def test_share_rejects_unexpected_links(body: dict) -> None:
    with pytest.raises(InvalidResponseError):
        await GodboltSharer(client(reply(body))).share(RunRequest("c", "x"))


async def test_share_maps_http_errors() -> None:
    with pytest.raises(ProviderUnavailableError):
        await GodboltSharer(client(reply({}, 500))).share(RunRequest("c", "x"))


async def test_aclose_closes_clients() -> None:
    runner, sharer = GodboltRunner(client(reply({}))), GodboltSharer(client(reply({})))
    await runner.aclose()
    await sharer.aclose()

    assert runner._client.is_closed and sharer._client.is_closed


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("public class Main { }", "class Main { }"),
        ("public final class Main{}", "final class Main{}"),
        ("import java.util.*;\npublic  class Main {\n}", "import java.util.*;\nclass Main {\n}"),
        ("public class Helper {} class Main {}", "public class Helper {} class Main {}"),
        ("public class MainApp {}", "public class MainApp {}"),
    ],
)
def test_java_public_main_is_made_package_private(code: str, expected: str) -> None:
    assert godbolt_source(RunRequest("java", code)) == expected


def test_other_languages_are_sent_unchanged() -> None:
    code = "public class Main {}"

    assert godbolt_source(RunRequest("cpp", code)) == code


async def test_runner_and_sharer_send_the_adjusted_java_source() -> None:
    bodies: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        if request.url.path == "/api/shortener":
            return httpx2.Response(200, json={"url": "https://godbolt.org/z/j"})
        return httpx2.Response(200, json={"code": 0, "buildResult": {"code": 0}})

    request = RunRequest("java", "public class Main { }")
    await GodboltRunner(client(handler)).run(request)
    await GodboltSharer(client(handler)).share(request)

    assert bodies[0]["source"] == "class Main { }"
    assert bodies[1]["sessions"][0]["source"] == "class Main { }"
