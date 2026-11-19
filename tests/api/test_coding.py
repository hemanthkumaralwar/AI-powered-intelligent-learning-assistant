"""/coding end to end on the Neon test schema, with a scripted fake model."""

import json
from collections.abc import AsyncIterator
from datetime import timedelta

import argon2
import httpx2
import pytest

from app.auth.passwords import PasswordHasher
from app.auth.service import AuthService
from app.auth.tokens import TokenService
from app.coding.service import CodingService
from app.core.config import Settings
from app.core.quota import MINUTE, Quota, QuotaRule
from app.db.models import Course, Exercise, Lesson, Module
from app.db.session import Database
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.main import create_app
from app.providers.errors import ProviderUnavailableError
from app.providers.retry import RetryPolicy
from app.rag.retriever import Retriever
from app.runner.fake import FakeRunner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService

pytestmark = pytest.mark.anyio

PASSWORD = "Str0ng-Passphrase!"  # noqa: S105 - test fixture value
BUG_HUNT = "const counter = 0;\ncounter = counter + 1;\nconsole.log(counter);"
FIXED = "let counter = 0;\ncounter = counter + 1;\nconsole.log(counter);"
DEBUG_REPLY = {
    "summary": "counter is const.",
    "issues": [{"line": 2, "problem": "Reassigns a const.", "fix_hint": "Should it change?"}],
    "corrected_code": FIXED,
    "concepts": [],
}


class Coding:
    def __init__(self) -> None:
        self.model = FakeChatModel()
        self.client: httpx2.AsyncClient
        self.headers: dict[str, str] = {}

    def reply(self, *replies) -> None:
        self.model.push(*(json.dumps(r) if isinstance(r, dict) else r for r in replies))

    async def post(self, path: str, **body) -> httpx2.Response:
        return await self.client.post(f"/coding/{path}", headers=self.headers, json=body)


async def no_search(query: str, k: int, course_id: str | None) -> list:
    return []


@pytest.fixture
async def coding(database: Database, null_indexing) -> AsyncIterator[Coding]:
    harness = Coding()
    llm = LLMClient(harness.model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
    service = CodingService(
        llm, Quota([QuotaRule("too quickly", 3, MINUTE)]), Retriever(no_search, 5, 0.63)
    )
    hasher = PasswordHasher(argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    app = create_app(
        Settings(_env_file=None, environment="test", log_level="WARNING", llm_provider="fake"),
        database=database,
        auth=AuthService(hasher, TokenService("j" * 64, timedelta(minutes=30))),
        code_runner=CodeRunnerService([FakeRunner()], None, RunQuota(QuotaLimits(9, 9, 9))),
        indexing=null_indexing,
        coding=service,
    )
    async with database.session() as session:
        session.add(Course(id="js", title="JS", language="javascript"))
        session.add(Module(id="js-m1", course_id="js", position=1, title="Basics"))
        session.add(Lesson(id="js-m1-l1", module_id="js-m1", position=1, title="Variables"))
        session.add(
            Exercise(
                lesson_id="js-m1-l1",
                kind="bug_hunt",
                title="Fix it",
                instructions="Find the bug.",
                starter_code=BUG_HUNT,
                solution=FIXED,
            )
        )
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            harness.client = client
            credentials = {"username": "asha", "password": PASSWORD}
            await client.post("/auth/register", json=credentials)
            token = (await client.post("/auth/login", json=credentials)).json()["access_token"]
            harness.headers = {"Authorization": f"Bearer {token}"}
            yield harness


async def test_debug_returns_issues_and_corrected_code(coding: Coding) -> None:
    coding.reply(DEBUG_REPLY)
    code = "let total = 0\nfor (let i = 0; i <= 3; i++) total += i\nconsole.log(totl)"
    run = {"outcome": "runtime_error", "stderr": "ReferenceError: totl is not defined"}

    response = await coding.post("debug", language="javascript", code=code, run=run)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exercise"] is False
    assert body["corrected_code"] == FIXED
    assert body["issues"][0]["line"] == 2
    assert body["related_lessons"] == []
    assert "ReferenceError: totl" in coding.model.requests[0].messages[1].content


async def test_a_course_bug_hunt_gets_hints_only(coding: Coding) -> None:
    coding.reply(DEBUG_REPLY)

    response = await coding.post("debug", language="javascript", code=BUG_HUNT)

    body = response.json()
    assert (body["exercise"], body["corrected_code"]) == (True, None)
    assert FIXED not in response.text


async def test_same_code_in_another_language_is_not_an_exercise(coding: Coding) -> None:
    coding.reply(DEBUG_REPLY)

    response = await coding.post("debug", language="python", code=BUG_HUNT)

    assert response.json()["exercise"] is False


async def test_explain_example_and_practice(coding: Coding) -> None:
    coding.reply(
        {"summary": "Counts.", "lines": [{"line": 1, "explanation": "Declares."}], "concepts": []},
        {"title": "Loop", "code": "for x in y: pass", "explanation": "Loops.", "concepts": []},
        {
            "questions": [
                {"question": "Sum 1..3", "hints": ["Use a loop"], "expected_output": "6"}
            ],
            "concepts": [],
        },
    )

    explained = await coding.post("explain", language="python", code="x = 1")
    example = await coding.post("example", language="python", topic="for loops")
    practice = await coding.post("practice", language="python", topic="for loops")

    assert explained.json()["lines"] == [{"line": 1, "explanation": "Declares."}]
    assert example.json()["title"] == "Loop"
    assert practice.json()["questions"][0]["expected_output"] == "6"
    assert "solution" not in practice.text


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("explain", {"language": "javascript", "code": "   "}),
        ("explain", {"language": "javascript", "code": "x" * (8 * 1024 + 1)}),
        ("explain", {"language": "javascript", "code": "x\n" * 201}),
        ("explain", {"language": "cobol", "code": "x"}),
        ("example", {"language": "python", "topic": "  "}),
        ("example", {"language": "python", "topic": "t" * 201}),
        ("debug", {"language": "python", "code": "x", "run": {"outcome": "exploded"}}),
    ],
    ids=["blank", "too-big", "too-many-lines", "language", "blank-topic", "long-topic", "outcome"],
)
async def test_invalid_requests_are_422(coding: Coding, path: str, body: dict) -> None:
    assert (await coding.post(path, **body)).status_code == 422


async def test_unusable_reply_twice_is_a_friendly_502(coding: Coding) -> None:
    coding.reply("not json", "still not json")

    response = await coding.post("explain", language="python", code="x = 1")

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "The assistant couldn't produce a valid answer. Please try again."
    )


async def test_provider_down_is_503_and_quota_is_429(coding: Coding) -> None:
    coding.reply(ProviderUnavailableError("gemini 504"))
    assert (await coding.post("explain", language="python", code="x")).status_code == 503

    for _ in range(2):
        await coding.post("explain", language="python", code="x")
    over = await coding.post("explain", language="python", code="x")
    assert over.status_code == 429 and "Retry-After" in over.headers


async def test_requires_login(coding: Coding) -> None:
    coding.headers = {}

    assert (await coding.post("explain", language="python", code="x")).status_code == 401


async def test_coding_uses_the_profile_level_unless_the_request_overrides_it(
    coding: Coding,
) -> None:
    explained = {"summary": "s", "lines": [], "concepts": []}
    coding.reply(explained, explained)
    await coding.client.patch("/auth/me", headers=coding.headers, json={"level": "intermediate"})

    await coding.post("explain", language="python", code="x = 1")
    await coding.post("explain", language="python", code="x = 1", level="advanced")

    profile, override = (r.messages[0].content for r in coding.model.requests)
    assert "Explanation level: intermediate." in profile
    assert "Explanation level: advanced." in override
