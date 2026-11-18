"""Store uploads: course JSON (course tree + quizzes + exercises) and TXT notes.

Each call works inside the caller's session, so a request's whole upload commits or rolls
back as one unit. Logs ids, kinds and sizes only, never file contents.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.errors import DuplicateError
from app.db.models import Document
from app.db.repositories.courses import CourseRepository
from app.db.repositories.documents import DocumentRepository
from app.ingestion.course_json import parse_course
from app.ingestion.errors import CourseExistsError, UnknownTargetError
from app.ingestion.files import check_size, decode_text

logger = logging.getLogger(__name__)


async def ingest_course(
    session: AsyncSession,
    *,
    content: bytes,
    filename: str,
    language: str,
    uploaded_by: uuid.UUID | None,
) -> Document:
    """Validate a course JSON and store it with its whole course tree."""
    check_size(content)
    course = parse_course(content, language)
    courses = CourseRepository(session)
    if await courses.exists(course.id):
        raise CourseExistsError(
            f"Course '{course.id}' already exists. Delete it first to replace it."
        )
    try:
        await courses.add(course)
    except DuplicateError as exc:
        raise CourseExistsError(
            "A module or lesson id in this file is already used by another course."
        ) from exc
    document = await DocumentRepository(session).add(
        course_id=course.id,
        kind="course",
        filename=filename,
        content_type="application/json",
        content=content,
        uploaded_by=uploaded_by,
    )
    logger.info(
        "course uploaded document_id=%s course_id=%s modules=%d lessons=%d bytes=%d",
        document.id,
        course.id,
        len(course.modules),
        sum(len(module.lessons) for module in course.modules),
        len(content),
    )
    return document


async def ingest_notes(
    session: AsyncSession,
    *,
    content: bytes,
    filename: str,
    course_id: str,
    module_id: str | None,
    lesson_id: str | None,
    uploaded_by: uuid.UUID | None,
) -> Document:
    """Store a UTF-8 text file, tagged to an existing course (and optionally a lesson)."""
    check_size(content)
    decode_text(content)
    module_id = await _resolve_tags(session, course_id, module_id, lesson_id)
    document = await DocumentRepository(session).add(
        course_id=course_id,
        kind="notes",
        filename=filename,
        content_type="text/plain; charset=utf-8",
        content=content,
        uploaded_by=uploaded_by,
        module_id=module_id,
        lesson_id=lesson_id,
    )
    logger.info(
        "notes uploaded document_id=%s course_id=%s bytes=%d", document.id, course_id, len(content)
    )
    return document


async def _resolve_tags(
    session: AsyncSession, course_id: str, module_id: str | None, lesson_id: str | None
) -> str | None:
    """Check the tags belong together; a lesson implies its module. Returns the module id."""
    courses = CourseRepository(session)
    if not await courses.exists(course_id):
        raise UnknownTargetError(f"Course '{course_id}' does not exist.")
    if lesson_id is not None:
        lesson = await courses.get_lesson(lesson_id)
        if lesson is None or lesson.module.course_id != course_id:
            raise UnknownTargetError(f"Lesson '{lesson_id}' is not part of course '{course_id}'.")
        if module_id is not None and module_id != lesson.module_id:
            raise UnknownTargetError(f"Lesson '{lesson_id}' is not in module '{module_id}'.")
        return lesson.module_id
    if module_id is not None:
        module = await courses.get_module(module_id)
        if module is None or module.course_id != course_id:
            raise UnknownTargetError(f"Module '{module_id}' is not part of course '{course_id}'.")
    return module_id
