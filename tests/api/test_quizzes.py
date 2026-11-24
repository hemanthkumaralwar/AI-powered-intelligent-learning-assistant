"""/lessons/{id}/quiz end to end on the real course (Neon test schema): questions without
answers, server-side marking, owner-only attempts, and quiz scores in progress."""

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
from app.db.models import QuizAttempt, QuizQuestion
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
LESSON = "javascript-beginner-mod-1-lesson-1"


class Quizzer:
    def __init__(self, client: httpx2.AsyncClient, database: Database) -> None:
        self.client = client
        self.database = database

    async def login(self, username: str) -> dict[str, str]:
        credentials = {"username": username, "password": PASSWORD}
        await self.client.post("/auth/register", json=credentials)
        token = (await self.client.post("/auth/login", json=credentials)).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def key(self, lesson_id: str = LESSON) -> dict[str, int]:
        """Question id -> correct option, read straight from the database."""
        async with self.database.session() as session:
            rows = await session.execute(
                select(QuizQuestion.id, QuizQuestion.correct_index).where(
                    QuizQuestion.lesson_id == lesson_id
                )
            )
            return {str(question_id): correct for question_id, correct in rows}

    async def answers(self, right: int, lesson_id: str = LESSON) -> dict[str, int]:
        """Answers with the first `right` questions correct and the rest wrong."""
        key = await self.key(lesson_id)
        return {
            question_id: correct if n < right else (correct + 1) % 4
            for n, (question_id, correct) in enumerate(sorted(key.items()))
        }

    async def submit(
        self, headers: dict[str, str], answers: dict, lesson_id: str = LESSON
    ) -> httpx2.Response:
        return await self.client.post(
            f"/lessons/{lesson_id}/quiz/attempts", headers=headers, json={"answers": answers}
        )


@pytest.fixture
async def quizzer(database: Database, null_indexing) -> AsyncIterator[Quizzer]:
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
            yield Quizzer(client, database)


async def test_quiz_has_the_questions_but_never_the_answers(quizzer: Quizzer) -> None:
    headers = await quizzer.login("asha")

    response = await quizzer.client.get(f"/lessons/{LESSON}/quiz", headers=headers)

    assert response.status_code == 200, response.text
    questions = response.json()["questions"]
    assert len(questions) == 10
    assert set(questions[0]) == {"id", "position", "question", "options"}
    assert all(set(option) == {"id", "text"} for q in questions for option in q["options"])
    assert "correct" not in response.text and "explanation" not in response.text


async def test_options_are_shuffled_the_same_way_on_every_visit(quizzer: Quizzer) -> None:
    headers = await quizzer.login("asha")
    path = f"/lessons/{LESSON}/quiz"

    first = (await quizzer.client.get(path, headers=headers)).json()["questions"]
    again = (await quizzer.client.get(path, headers=headers)).json()["questions"]

    assert first == again
    shown = [[option["id"] for option in q["options"]] for q in first]
    assert any(order != sorted(order) for order in shown)  # not the file's order
    assert all(sorted(order) == list(range(len(order))) for order in shown)


async def test_attempt_is_marked_recorded_and_shows_the_answers(quizzer: Quizzer) -> None:
    headers = await quizzer.login("asha")
    key = await quizzer.key()

    response = await quizzer.submit(headers, await quizzer.answers(right=7))
    listed = await quizzer.client.get(f"/lessons/{LESSON}/quiz/attempts", headers=headers)

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["correct"], body["total"]) == (7, 10)
    assert {r["question_id"]: r["correct_option"] for r in body["results"]} == key
    assert all(r["explanation"] for r in body["results"])
    assert [(a["id"], a["correct"]) for a in listed.json()] == [(body["id"], 7)]


async def test_unanswered_questions_count_as_wrong(quizzer: Quizzer) -> None:
    headers = await quizzer.login("asha")
    answers = await quizzer.answers(right=10)
    first = sorted(answers)[0]

    body = (await quizzer.submit(headers, {first: answers[first]})).json()

    assert (body["correct"], body["total"]) == (1, 10)


async def test_students_only_see_their_own_attempts(quizzer: Quizzer) -> None:
    await quizzer.submit(await quizzer.login("asha"), await quizzer.answers(right=3))
    ravi = await quizzer.login("ravi")

    listed = await quizzer.client.get(f"/lessons/{LESSON}/quiz/attempts", headers=ravi)

    assert listed.json() == []


async def test_lesson_without_a_quiz_is_404(quizzer: Quizzer) -> None:
    headers = await quizzer.login("asha")

    quiz = await quizzer.client.get("/lessons/nope/quiz", headers=headers)
    submitted = await quizzer.submit(headers, {}, lesson_id="nope")

    assert (quiz.status_code, quiz.json()["detail"]) == (404, "This lesson has no quiz")
    assert submitted.status_code == 404


async def test_bad_answers_are_422_and_nothing_is_saved(quizzer: Quizzer) -> None:
    headers = await quizzer.login("asha")
    other_lesson = await quizzer.answers(right=10, lesson_id="javascript-beginner-mod-1-lesson-2")
    question_id = sorted(await quizzer.key())[0]

    foreign = await quizzer.submit(headers, other_lesson)
    out_of_range = await quizzer.submit(headers, {question_id: 9})
    not_a_number = await quizzer.submit(headers, {question_id: "b"})

    assert [r.status_code for r in (foreign, out_of_range, not_a_number)] == [422] * 3
    async with quizzer.database.session() as session:
        assert (await session.scalars(select(QuizAttempt))).all() == []


async def test_quiz_needs_an_account(quizzer: Quizzer) -> None:
    quiz = await quizzer.client.get(f"/lessons/{LESSON}/quiz")
    submitted = await quizzer.submit({}, {})

    assert (quiz.status_code, submitted.status_code) == (401, 401)


async def test_a_poor_quiz_shows_in_progress_and_recommendations(quizzer: Quizzer) -> None:
    headers = await quizzer.login("asha")
    await quizzer.submit(headers, await quizzer.answers(right=3))

    progress = (await quizzer.client.get("/me/progress", headers=headers)).json()
    picks = (await quizzer.client.get("/me/recommendations", headers=headers)).json()

    assert progress["course_id"] == COURSE  # found from the quiz, no exercises done
    lesson = progress["modules"][0]["lessons"][0]
    assert (lesson["lesson_id"], lesson["quiz_score"], lesson["mastery"]) == (LESSON, 0.3, 0.3)
    assert lesson["weak"] is True
    first = picks["recommendations"][0]
    assert (first["kind"], first["lesson_id"], first["quiz_score"]) == ("review", LESSON, 0.3)
    assert first["reason"] == "Review: 30% on this lesson's quiz"


async def test_a_retake_counts_most(quizzer: Quizzer) -> None:
    headers = await quizzer.login("asha")
    await quizzer.submit(headers, await quizzer.answers(right=2))
    await quizzer.submit(headers, await quizzer.answers(right=10))

    progress = (await quizzer.client.get("/me/progress", headers=headers)).json()

    lesson = progress["modules"][0]["lessons"][0]
    assert lesson["quiz_score"] == pytest.approx((1.0 + 0.5 * 0.2) / 1.5)
    assert lesson["weak"] is False
