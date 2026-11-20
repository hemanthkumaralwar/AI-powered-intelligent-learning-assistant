"""Course exercises (with their hidden references) and students' graded attempts."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Course, Exercise, ExerciseAttempt, Lesson, Module


@dataclass(frozen=True)
class ExerciseTask:
    """What grading needs. `solution` and `expected_output` never reach the student."""

    id: uuid.UUID
    kind: str
    title: str
    instructions: str
    starter_code: str
    language: str
    solution: str | None
    expected_output: str | None


class ExerciseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def task(self, exercise_id: uuid.UUID) -> ExerciseTask | None:
        row = (
            await self._session.execute(
                select(Exercise, Course.language)
                .join(Lesson, Exercise.lesson_id == Lesson.id)
                .join(Module, Lesson.module_id == Module.id)
                .join(Course, Module.course_id == Course.id)
                .where(Exercise.id == exercise_id)
            )
        ).first()
        if row is None:
            return None
        exercise, language = row
        return ExerciseTask(
            id=exercise.id,
            kind=exercise.kind,
            title=exercise.title,
            instructions=exercise.instructions,
            starter_code=exercise.starter_code,
            language=language,
            solution=exercise.solution,
            expected_output=exercise.expected_output,
        )

    async def add_attempt(
        self, user_id: uuid.UUID, exercise_id: uuid.UUID, passed: bool, feedback: str
    ) -> ExerciseAttempt:
        attempt = ExerciseAttempt(
            user_id=user_id, exercise_id=exercise_id, passed=passed, feedback=feedback
        )
        self._session.add(attempt)
        await self._session.flush()
        await self._session.refresh(attempt, ["created_at"])
        return attempt

    async def results_by_exercise(
        self, user_id: uuid.UUID, course_id: str
    ) -> dict[str, list[bool]]:
        """This student's results in one course: exercise id -> passed, newest first."""
        rows = await self._session.execute(
            select(ExerciseAttempt.exercise_id, ExerciseAttempt.passed)
            .join(Exercise, ExerciseAttempt.exercise_id == Exercise.id)
            .join(Lesson, Exercise.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .where(ExerciseAttempt.user_id == user_id, Module.course_id == course_id)
            .order_by(ExerciseAttempt.created_at.desc(), ExerciseAttempt.id)
        )
        results: dict[str, list[bool]] = {}
        for exercise_id, passed in rows:
            results.setdefault(str(exercise_id), []).append(passed)
        return results

    async def most_attempted_course(self, user_id: uuid.UUID) -> str | None:
        """The course this student has the most exercise attempts in (None: no attempts)."""
        return await self._session.scalar(
            select(Module.course_id)
            .join(Lesson, Lesson.module_id == Module.id)
            .join(Exercise, Exercise.lesson_id == Lesson.id)
            .join(ExerciseAttempt, ExerciseAttempt.exercise_id == Exercise.id)
            .where(ExerciseAttempt.user_id == user_id)
            .group_by(Module.course_id)
            .order_by(func.count().desc(), Module.course_id)
            .limit(1)
        )

    async def lesson_attempts(
        self, user_id: uuid.UUID, course_id: str
    ) -> list[tuple[str, datetime, bool]]:
        """This student's graded attempts in a course as (lesson id, time, passed), oldest
        first: what spaced review replays."""
        rows = await self._session.execute(
            select(Exercise.lesson_id, ExerciseAttempt.created_at, ExerciseAttempt.passed)
            .join(Exercise, Exercise.id == ExerciseAttempt.exercise_id)
            .join(Lesson, Lesson.id == Exercise.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .where(ExerciseAttempt.user_id == user_id, Module.course_id == course_id)
            .order_by(ExerciseAttempt.created_at, ExerciseAttempt.id)
        )
        return [(lesson_id, at, passed) for lesson_id, at, passed in rows]

    async def attempts(
        self, user_id: uuid.UUID, exercise_id: uuid.UUID, limit: int = 20
    ) -> list[ExerciseAttempt]:
        """This student's attempts at this exercise, newest first."""
        rows = await self._session.scalars(
            select(ExerciseAttempt)
            .where(ExerciseAttempt.user_id == user_id, ExerciseAttempt.exercise_id == exercise_id)
            .order_by(ExerciseAttempt.created_at.desc(), ExerciseAttempt.id)
            .limit(limit)
        )
        return list(rows)
