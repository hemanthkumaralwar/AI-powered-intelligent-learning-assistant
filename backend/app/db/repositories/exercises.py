"""Course exercises (with their hidden references) and students' graded attempts."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
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
