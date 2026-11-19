"""/code endpoints with fake runners; auth is overridden so no database is needed."""

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx2
import pytest
from fastapi import FastAPI

from app.api.deps import require_user
from app.auth.passwords import PasswordHasher
from app.auth.service import AuthService
from app.auth.tokens import TokenService
from app.core.config import Settings
from app.db.models import User
from app.db.session import Database
from app.main import create_app
from app.providers.errors import ProviderUnavailableError
from app.runner.base import RunRequest, RunResult
from app.runner.fake import FakeRunner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService

pytestmark = pytest.mark.anyio

STUDENT = User(id=uuid.uuid4(), username="asha", password_hash="unused", role="student")  # noqa: S106 - test user, never logs in


class LinkSharer:
    languages = frozenset({"c", "cpp", "java", "python"})

    async def share(self, request: RunRequest) -> str:
        return "https://godbolt.org/z/abc123"

    async def aclose(self) -> None:
        return None


def service(*steps, per_minute: int = 100) -> CodeRunnerService:
    return CodeRunnerService(
        [FakeRunner(steps)], LinkSharer(), RunQuota(QuotaLimits(per_minute, 1000, 1000))
    )


@pytest.fixture
def make_client(null_indexing):
    async def _make(code_runner: CodeRunnerService, *, logged_in: bool = True):
        app: FastAPI = create_app(
            Settings(_env_file=None, environment="test", log_level="WARNING", llm_provider="fake"),
            # Never connects: these tests override authentication.
            database=Database("postgresql://u:p@localhost/db"),
            auth=AuthService(
                PasswordHasher(),
                TokenService("k" * 64, timedelta(minutes=5)),
            ),
            code_runner=code_runner,
            indexing=null_indexing,
        )
        if logged_in:
            app.dependency_overrides[require_user] = lambda: STUDENT
        return app

    return _make


@pytest.fixture
async def http(make_client) -> AsyncIterator:
    opened: list = []

    async def _open(code_runner: CodeRunnerService, **kwargs) -> httpx2.AsyncClient:
        app = await make_client(code_runner, **kwargs)
        lifespan = app.router.lifespan_context(app)
        await lifespan.__aenter__()
        client = httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url="http://test")
        opened.append((lifespan, client))
        return client

    yield _open
    for lifespan, client in opened:
        await client.aclose()
        await lifespan.__aexit__(None, None, None)


async def test_requires_login(http) -> None:
    client = await http(service(), logged_in=False)

    assert (await client.post("/code/run", json={"language": "c", "code": "x"})).status_code == 401
    assert (
        await client.post("/code/share", json={"language": "c", "code": "x"})
    ).status_code == 401


async def test_run_returns_the_result(http) -> None:
    client = await http(service())

    response = await client.post(
        "/code/run", json={"language": "python", "code": "print(1)\nprint(2)"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "ok"
    assert body["stdout"] == "fake run: 2 line(s)\n"
    assert set(body) == {
        "outcome",
        "stdout",
        "stderr",
        "compile_output",
        "exit_code",
        "time_ms",
        "provider",
        "truncated",
    }


async def test_compile_error_is_a_normal_result(http) -> None:
    failed = RunResult("compile_error", "", "", "error: x undeclared", None, None, "fake")
    client = await http(service(failed))

    response = await client.post(
        "/code/run", json={"language": "c", "code": "int main(){return x;}"}
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "compile_error"


async def test_quota_exceeded_is_429_with_retry_after(http) -> None:
    client = await http(service(per_minute=1))
    await client.post("/code/run", json={"language": "c", "code": "x"})

    response = await client.post("/code/run", json={"language": "c", "code": "x"})

    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 60


async def test_runner_down_is_503_without_details(http) -> None:
    client = await http(service(ProviderUnavailableError("judge0 server error 502")))

    response = await client.post("/code/run", json={"language": "c", "code": "x"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "The code runner is unavailable. Please try again shortly."
    }


@pytest.mark.parametrize(
    "body",
    [
        {"language": "rust", "code": "fn main(){}"},
        {"language": "c", "code": ""},
        {"language": "c", "code": "   \n "},
        {"language": "c", "code": "x" * (20 * 1024 + 1)},
        {"language": "c", "code": "é" * (10 * 1024 + 1)},
        {"language": "c", "code": "x", "stdin": "y" * (8 * 1024 + 1)},
    ],
    ids=["unknown-language", "empty", "blank", "too-big", "too-big-in-bytes", "stdin-too-big"],
)
async def test_invalid_requests_are_422(http, body: dict) -> None:
    response = await (await http(service())).post("/code/run", json=body)

    assert response.status_code == 422


async def test_share_returns_public_link_with_warning(http) -> None:
    response = await (await http(service())).post(
        "/code/share", json={"language": "cpp", "code": "int main(){}"}
    )

    assert response.status_code == 200
    assert response.json()["url"] == "https://godbolt.org/z/abc123"
    assert "public and permanent" in response.json()["warning"]


@pytest.mark.parametrize("language", ["sql", "javascript"])
async def test_share_unsupported_language_is_422(http, language: str) -> None:
    response = await (await http(service())).post(
        "/code/share", json={"language": language, "code": "x"}
    )

    assert response.status_code == 422
    assert language in response.json()["detail"]


async def test_code_never_reaches_logs(http, caplog: pytest.LogCaptureFixture) -> None:
    client = await http(service())

    with caplog.at_level(logging.DEBUG):
        await client.post(
            "/code/run", json={"language": "python", "code": "print('student-secret')"}
        )

    assert "student-secret" not in caplog.text


async def test_stdin_is_passed_to_the_runner(http) -> None:
    runner = FakeRunner()
    quota = RunQuota(QuotaLimits(100, 1000, 1000))
    client = await http(CodeRunnerService([runner], LinkSharer(), quota))

    response = await client.post(
        "/code/run", json={"language": "python", "code": "print(input())", "stdin": "hi"}
    )

    assert response.status_code == 200
    assert runner.requests[0].stdin == "hi"


async def test_language_without_a_configured_runner_is_422(http) -> None:
    only_c = FakeRunner(languages={"c"})
    client = await http(CodeRunnerService([only_c], LinkSharer(), RunQuota(QuotaLimits(9, 9, 9))))

    response = await client.post("/code/run", json={"language": "sql", "code": "select 1;"})

    assert response.status_code == 422
    assert "sql" in response.json()["detail"]


async def test_share_service_down_is_503(http) -> None:
    class DownSharer(LinkSharer):
        async def share(self, request: RunRequest) -> str:
            raise ProviderUnavailableError("godbolt server error 502")

    quota = RunQuota(QuotaLimits(9, 9, 9))
    client = await http(CodeRunnerService([FakeRunner()], DownSharer(), quota))

    response = await client.post("/code/share", json={"language": "c", "code": "int main(){}"})

    assert response.status_code == 503
    assert "502" not in response.text
