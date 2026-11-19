"""/me/progress and /me/recommendations on the real course (Neon test schema)."""

from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import argon2
import httpx2
import pytest
from sqlalchemy import select

from app.auth.passwords import PasswordHasher
from app.auth.service import AuthService
from app.auth.tokens import TokenService
from app.core.config import Settings
from app.db.models import Exercise, ExerciseAttempt, Lesson, Module, User
from app.db.session import Database
from app.ingestion.course_json import parse_course
from app.main import create_app
from app.runner.fake import FakeRunner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService

pytestmark = pytest.mark.anyio

PASSWORD = "Str0ng-Passphrase!"  # noqa: S105 - test fixture value
REAL_COURSE = (
    Path(__file__).resolve().parents[2] / "eval" / "materials" / "javascript-beginner.json"
)
COURSE = "javascript-beginner-v1"
ARRAYS = "javascript-beginner-mod-4"


class Learner:
    def __init__(self, client: httpx2.AsyncClient, database: Database) -> None:
        self.client = client
        self.database = database

    async def login(self, username: str) -> dict[str, str]:
        credentials = {"username": username, "password": PASSWORD}
        await self.client.post("/auth/register", json=credentials)
        token = (await self.client.post("/auth/login", json=credentials)).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def record(self, username: str, *, passed_modules: range, failed_module: int) -> None:
        """Attempts for every exercise: passed in `passed_modules`, failed in another."""
        async with self.database.session() as session:
            user = await session.scalar(select(User).where(User.username == username))
            rows = await session.execute(
                select(Exercise.id, Module.position)
                .join(Lesson, Exercise.lesson_id == Lesson.id)
                .join(Module, Lesson.module_id == Module.id)
                .where(Module.course_id == COURSE)
            )
            for exercise_id, module in rows:
                if module in passed_modules or module == failed_module:
                    passed = module != failed_module
                    session.add(
                        ExerciseAttempt(
                            user_id=user.id,
                            exercise_id=exercise_id,
                            passed=passed,
                            feedback="seeded",
                        )
                    )


@pytest.fixture
async def learner(database: Database, null_indexing) -> AsyncIterator[Learner]:
    hasher = PasswordHasher(argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    app = create_app(
        Settings(_env_file=None, environment="test", log_level="WARNING", llm_provider="fake"),
        database=database,
        auth=AuthService(hasher, TokenService("j" * 64, timedelta(minutes=30))),
        code_runner=CodeRunnerService([FakeRunner()], None, RunQuota(QuotaLimits(9, 9, 9))),
        indexing=null_indexing,
    )
    async with database.session() as session:
        session.add(parse_course(REAL_COURSE.read_bytes(), "javascript"))
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            yield Learner(client, database)


# ---- Done-when: a student who struggles with Arrays -------------------------------------


async def test_student_weak_on_arrays_is_recommended_arrays(learner: Learner) -> None:
    headers = await learner.login("asha")
    await learner.record("asha", passed_modules=range(1, 4), failed_module=4)

    body = (await learner.client.get("/me/recommendations", headers=headers)).json()
    picks = body["recommendations"]

    assert body["course_id"] == COURSE
    reviews = [p for p in picks if p["kind"] == "review"]
    assert len(picks) == 5 and len(reviews) == 5
    assert all(p["lesson_id"].startswith(ARRAYS) for p in reviews)
    assert {p["module_title"] for p in reviews} == {"Arrays"}
    first = reviews[0]
    assert first["mastery"] == 0.0
    assert first["reason"] == "Review: 0% on this lesson's exercises"
    assert {e["kind"] for e in first["exercises"]} == {"bug_hunt", "interactive", "mini_challenge"}
    assert all(e["score"] == 0.0 for e in first["exercises"])
    assert [a["kind"] for a in first["practice"]][:1] == ["quiz"]


async def test_progress_shows_arrays_as_the_weak_module(learner: Learner) -> None:
    headers = await learner.login("asha")
    await learner.record("asha", passed_modules=range(1, 4), failed_module=4)

    modules = (await learner.client.get("/me/progress", headers=headers)).json()["modules"]
    by_title = {m["title"]: m for m in modules}

    assert by_title["Variables and Data Types"]["mastery"] == 1.0
    assert by_title["Arrays"]["mastery"] == 0.0
    assert by_title["Arrays"]["coverage"] == 1.0
    assert all(lesson["weak"] for lesson in by_title["Arrays"]["lessons"])
    assert by_title["Objects"]["mastery"] is None  # not started is not 0%
    assert not any(lesson["weak"] for lesson in by_title["Objects"]["lessons"])


# ---- everyone else ----------------------------------------------------------------------


async def test_a_new_student_starts_at_the_first_lessons(learner: Learner) -> None:
    headers = await learner.login("ravi")

    picks = (await learner.client.get("/me/recommendations", headers=headers)).json()

    assert [p["kind"] for p in picks["recommendations"]] == ["next"] * 5
    assert picks["recommendations"][0]["lesson_id"] == "javascript-beginner-mod-1-lesson-1"


async def test_another_students_attempts_never_show(learner: Learner) -> None:
    await learner.login("asha")
    await learner.record("asha", passed_modules=range(1, 4), failed_module=4)
    ravi = await learner.login("ravi")

    modules = (await learner.client.get("/me/progress", headers=ravi)).json()["modules"]

    assert all(m["mastery"] is None for m in modules)


async def test_unknown_course_is_404_and_login_is_required(learner: Learner) -> None:
    headers = await learner.login("asha")

    missing = await learner.client.get("/me/progress?course_id=nope", headers=headers)
    anonymous = await learner.client.get("/me/recommendations")

    assert (missing.status_code, missing.json()["detail"]) == (404, "Course not found")
    assert anonymous.status_code == 401
