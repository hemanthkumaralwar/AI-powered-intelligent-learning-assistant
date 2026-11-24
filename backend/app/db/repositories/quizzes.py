"""Lesson quizzes (with their answers, which only marking reads) and students' attempts."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lesson, Module, QuizAttempt, QuizQuestion


class QuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def questions(self, lesson_id: str) -> list[QuizQuestion]:
        """The lesson's questions in order (empty: no quiz, or no such lesson)."""
        rows = await self._session.scalars(
            select(QuizQuestion)
            .where(QuizQuestion.lesson_id == lesson_id)
            .order_by(QuizQuestion.position)
        )
        return list(rows)

    async def add_attempt(
        self,
        user_id: uuid.UUID,
        lesson_id: str,
        correct: int,
        total: int,
        answers: dict[str, int | None],
    ) -> QuizAttempt:
        attempt = QuizAttempt(
            user_id=user_id, lesson_id=lesson_id, correct=correct, total=total, answers=answers
        )
        self._session.add(attempt)
        await self._session.flush()
        await self._session.refresh(attempt, ["created_at", "source"])
        return attempt

    async def attempts(
        self, user_id: uuid.UUID, lesson_id: str, limit: int = 20
    ) -> list[QuizAttempt]:
        """This student's attempts at this lesson's quiz, newest first."""
        rows = await self._session.scalars(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id, QuizAttempt.lesson_id == lesson_id)
            .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id)
            .limit(limit)
        )
        return list(rows)

    async def results_by_lesson(self, user_id: uuid.UUID, course_id: str) -> dict[str, list[float]]:
        """This student's quiz scores in one course: lesson id -> share correct, newest
        first."""
        rows = await self._session.execute(
            select(QuizAttempt.lesson_id, QuizAttempt.correct, QuizAttempt.total)
            .join(Lesson, QuizAttempt.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .where(QuizAttempt.user_id == user_id, Module.course_id == course_id)
            .order_by(QuizAttempt.created_at.desc(), QuizAttempt.id)
        )
        results: dict[str, list[float]] = {}
        for lesson_id, correct, total in rows:
            results.setdefault(lesson_id, []).append(correct / total)
        return results

    async def latest_course(self, user_id: uuid.UUID) -> str | None:
        """The course of this student's most recent quiz attempt (None: no attempts)."""
        return await self._session.scalar(
            select(Module.course_id)
            .join(Lesson, Lesson.module_id == Module.id)
            .join(QuizAttempt, QuizAttempt.lesson_id == Lesson.id)
            .where(QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.created_at.desc())
            .limit(1)
        )
