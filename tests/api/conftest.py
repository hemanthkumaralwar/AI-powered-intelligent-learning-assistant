"""`world`: the whole app on the Neon test schema with scripted providers, an admin and two
students, for the failure and privacy suites (Step 20)."""

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import argon2
import httpx2
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.auth.passwords import PasswordHasher
from app.auth.seed import seed_admin
from app.auth.service import AuthService
from app.auth.tokens import TokenService
from app.coding.service import CodingService
from app.core.config import Settings
from app.core.quota import MINUTE, Quota, QuotaRule
from app.db.models import Course, Exercise, Lesson, Module
from app.db.session import Database
from app.learning.grading import ExerciseGrader
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.main import create_app
from app.providers.errors import ProviderCallError, ProviderUnavailableError
from app.providers.retry import RetryPolicy
from app.rag.answer import AnswerService
from app.rag.condense import Condenser
from app.rag.retriever import Retriever
from app.runner.fake import FakeRunner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService
from app.vectorstore.index import SearchHit

PASSWORD = "Str0ng-Passphrase!"  # noqa: S105 - test fixture value
COURSE = "js"
LESSON = "js-m1-l1"
EXERCISE_ID = uuid.UUID("00000000-0000-4000-8000-0000000000e1")
AI_QUESTIONS_PER_MINUTE = 6


class World:
    """The app plus knobs: the scripted model, the search outcome, and who is logged in."""

    # Exposed here: test modules cannot import from conftest (importlib import mode).
    password = PASSWORD
    course_id = COURSE
    exercise_id = EXERCISE_ID
    ai_questions_per_minute = AI_QUESTIONS_PER_MINUTE

    def __init__(self) -> None:
        self.model = FakeChatModel(default_reply="`let` is block-scoped [1].")
        self.search_error: ProviderCallError | None = None
        self.client: httpx2.AsyncClient
        self.app: FastAPI
        self.headers: dict[str, dict[str, str]] = {}

    async def search(self, query: str, k: int, course_id: str | None) -> list[SearchHit]:
        if self.search_error is not None:
            raise self.search_error
        return [
            SearchHit(
                chunk_id="c1",
                score=0.9,
                course_id=COURSE,
                lesson_id=LESSON,
                section="Explanation",
                text="let is block-scoped.",
                metadata={"course_title": "JS", "module_title": "Basics", "lesson_title": "Let"},
            )
        ]

    async def login(self, username: str, *, register: bool = True) -> dict[str, str]:
        credentials = {"username": username, "password": PASSWORD}
        if register:
            await self.client.post("/auth/register", json=credentials)
        token = (await self.client.post("/auth/login", json=credentials)).json()["access_token"]
        self.headers[username] = {"Authorization": f"Bearer {token}"}
        return self.headers[username]


@pytest.fixture
async def world(database: Database, null_indexing) -> AsyncIterator[World]:
    world = World()
    llm = LLMClient(world.model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
    quota = Quota([QuotaRule("too quickly", AI_QUESTIONS_PER_MINUTE, MINUTE)])
    hasher = PasswordHasher(argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    auth = AuthService(hasher, TokenService("j" * 64, timedelta(minutes=30)))
    down = [ProviderUnavailableError("runner down")] * 10
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            log_level="INFO",
            llm_provider="fake",
            login_failures_per_username=2,
        ),
        database=database,
        auth=auth,
        code_runner=CodeRunnerService([FakeRunner(down)], None, RunQuota(QuotaLimits(9, 9, 9))),
        indexing=null_indexing,
        answers=AnswerService(Retriever(world.search, 5, 0.63), llm, quota, Condenser(llm)),
        coding=CodingService(llm, quota, Retriever(world.search, 5, 0.63)),
        grader=ExerciseGrader(llm, quota),
    )
    async with database.session() as session:
        session.add(Course(id=COURSE, title="JS", language="javascript"))
        session.add(Module(id="js-m1", course_id=COURSE, position=1, title="Basics"))
        session.add(Lesson(id=LESSON, module_id="js-m1", position=1, title="Let"))
        session.add(
            Exercise(
                id=EXERCISE_ID,
                lesson_id=LESSON,
                kind="bug_hunt",
                title="Fix it",
                instructions="Find the bug.",
                starter_code="const x = 0;\nx = 1;",
                solution="let x = 0;\nx = 1;",
            )
        )
    await seed_admin(database, auth, "boss", SecretStr(PASSWORD))
    world.app = app  # e.g. for app.dependency_overrides in a test
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            world.client = client
            await world.login("boss", register=False)
            await world.login("asha")
            await world.login("ravi")
            yield world
