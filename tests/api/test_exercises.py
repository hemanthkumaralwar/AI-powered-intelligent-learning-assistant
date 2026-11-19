"""/exercises/{id}/attempts end to end on the Neon test schema, with a scripted model."""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import argon2
import httpx2
import pytest

from app.auth.passwords import PasswordHasher
from app.auth.service import AuthService
from app.auth.tokens import TokenService
from app.core.config import Settings
from app.core.quota import MINUTE, Quota, QuotaRule
from app.db.models import Course, Exercise, Lesson, Module
from app.db.session import Database
from app.learning.grading import GENERIC_HINT, ExerciseGrader
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.main import create_app
from app.providers.retry import RetryPolicy
from app.runner.fake import FakeRunner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService

pytestmark = pytest.mark.anyio

PASSWORD = "Str0ng-Passphrase!"  # noqa: S105 - test fixture value
EXERCISE_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
FIXED = "let counter = 0;\ncounter = counter + 1;\nconsole.log(counter);"


class Practice:
    def __init__(self) -> None:
        self.model = FakeChatModel()
        self.client: httpx2.AsyncClient
        self.headers: dict[str, str] = {}

    def reply(self, *replies: dict) -> None:
        self.model.push(*(json.dumps(r) for r in replies))

    async def login(self, username: str) -> dict[str, str]:
        credentials = {"username": username, "password": PASSWORD}
        await self.client.post("/auth/register", json=credentials)
        token = (await self.client.post("/auth/login", json=credentials)).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def submit(
        self,
        code: str = "let counter = 0;",
        exercise: uuid.UUID = EXERCISE_ID,
        headers: dict[str, str] | None = None,
    ) -> httpx2.Response:
        return await self.client.post(
            f"/exercises/{exercise}/attempts",
            headers=self.headers if headers is None else headers,
            json={"code": code},
        )

    async def attempts(self, headers: dict[str, str]) -> list[dict]:
        response = await self.client.get(f"/exercises/{EXERCISE_ID}/attempts", headers=headers)
        return response.json()


@pytest.fixture
async def practice(database: Database, null_indexing) -> AsyncIterator[Practice]:
    harness = Practice()
    llm = LLMClient(harness.model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
    hasher = PasswordHasher(argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    app = create_app(
        Settings(_env_file=None, environment="test", log_level="WARNING", llm_provider="fake"),
        database=database,
        auth=AuthService(hasher, TokenService("j" * 64, timedelta(minutes=30))),
        code_runner=CodeRunnerService([FakeRunner()], None, RunQuota(QuotaLimits(9, 9, 9))),
        indexing=null_indexing,
        grader=ExerciseGrader(llm, Quota([QuotaRule("too quickly", 5, MINUTE)])),
    )
    async with database.session() as session:
        session.add(Course(id="js", title="JS", language="javascript"))
        session.add(Module(id="m1", course_id="js", position=1, title="Basics"))
        session.add(Lesson(id="l1", module_id="m1", position=1, title="Variables"))
        session.add(
            Exercise(
                id=EXERCISE_ID,
                lesson_id="l1",
                kind="bug_hunt",
                title="Fix it",
                instructions="Find the bug.",
                starter_code="const counter = 0;",
                solution=FIXED,
            )
        )
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            harness.client = client
            harness.headers = await harness.login("asha")
            yield harness


async def test_attempt_is_graded_recorded_and_listed(practice: Practice) -> None:
    practice.reply({"passed": True, "feedback": "Yes: a value that changes needs let."})

    response = await practice.submit(FIXED)
    listed = await practice.attempts(practice.headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["passed"], body["feedback"]) == (True, "Yes: a value that changes needs let.")
    assert [a["id"] for a in listed] == [body["id"]]
    assert "<reference>\nlet counter = 0;" in practice.model.requests[0].messages[1].content


async def test_feedback_never_carries_the_solution(practice: Practice) -> None:
    practice.reply({"passed": False, "feedback": "Write: let counter = 0; instead."})

    body = (await practice.submit()).json()

    assert body["feedback"] == GENERIC_HINT


async def test_students_only_see_their_own_attempts(practice: Practice) -> None:
    practice.reply({"passed": False, "feedback": "Think about const."})
    await practice.submit()

    assert await practice.attempts(await practice.login("ravi")) == []


async def test_unknown_exercise_is_404_without_a_model_call(practice: Practice) -> None:
    response = await practice.submit(exercise=uuid.uuid4())

    assert (response.status_code, response.json()["detail"]) == (404, "Exercise not found")
    assert practice.model.requests == []


@pytest.mark.parametrize("code", ["   ", "x" * (8 * 1024 + 1), "x\n" * 201])
async def test_invalid_code_is_422(practice: Practice, code: str) -> None:
    assert (await practice.submit(code)).status_code == 422


async def test_needs_login(practice: Practice) -> None:
    assert (await practice.submit(headers={})).status_code == 401
