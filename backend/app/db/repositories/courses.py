from collections.abc import Sequence

from sqlalchemy import delete, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Course, Exercise, Lesson, Module
from app.db.repositories._integrity import unique_violation_as


class CourseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, course: Course) -> Course:
        """Insert a course with its modules and lessons in one flush.

        Raises `DuplicateError` if any course, module or lesson id already exists.
        """
        self._session.add(course)
        with unique_violation_as("course, module or lesson id already exists"):
            await self._session.flush()
        return course

    async def get(self, course_id: str) -> Course | None:
        """Load a course with its modules and lessons, all ordered by position."""
        query = (
            select(Course)
            .where(Course.id == course_id)
            .options(selectinload(Course.modules).selectinload(Module.lessons))
        )
        return await self._session.scalar(query)

    async def list_courses(self) -> list[Course]:
        """All courses by title, without their modules (cheap for listings)."""
        return list(await self._session.scalars(select(Course).order_by(Course.title)))

    async def exists(self, course_id: str) -> bool:
        return bool(await self._session.scalar(select(exists().where(Course.id == course_id))))

    async def lessons_by_ids(self, lesson_ids: Sequence[str]) -> list[Lesson]:
        """The lessons with these ids (any order); unknown ids are skipped."""
        if not lesson_ids:
            return []
        return list(await self._session.scalars(select(Lesson).where(Lesson.id.in_(lesson_ids))))

    async def exercise_code(self, language: str) -> list[str]:
        """Starter code of every bug hunt and mini challenge in courses of `language`, so
        the coding assistant can recognise an exercise and hold back its solution."""
        rows = await self._session.scalars(
            select(Exercise.starter_code)
            .join(Lesson, Exercise.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .join(Course, Module.course_id == Course.id)
            .where(Course.language == language, Exercise.kind.in_(("bug_hunt", "mini_challenge")))
        )
        return list(rows)

    async def delete(self, course_id: str) -> bool:
        """Delete a course; its modules, lessons, quizzes, exercises and documents go with it."""
        result = await self._session.execute(delete(Course).where(Course.id == course_id))
        return result.rowcount == 1

    async def get_lesson(self, lesson_id: str) -> Lesson | None:
        """A lesson with its module and exercises (quiz questions are not loaded)."""
        query = (
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.module), selectinload(Lesson.exercises))
        )
        return await self._session.scalar(query)

    async def get_full(self, course_id: str) -> Course | None:
        """A course with modules, lessons and exercises: everything the chunker reads."""
        query = (
            select(Course)
            .where(Course.id == course_id)
            .options(
                selectinload(Course.modules)
                .selectinload(Module.lessons)
                .selectinload(Lesson.exercises)
            )
        )
        return await self._session.scalar(query)
