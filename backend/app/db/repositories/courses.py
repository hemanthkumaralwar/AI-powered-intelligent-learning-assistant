from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Course, Module
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

    async def list(self) -> list[Course]:
        """All courses by title, without their modules (cheap for listings)."""
        return list(await self._session.scalars(select(Course).order_by(Course.title)))
