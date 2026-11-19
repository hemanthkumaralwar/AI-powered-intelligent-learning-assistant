"""Store an uploaded course JSON: course tree, quizzes, exercises and the original file.

Works inside the caller's session, so the whole upload commits or rolls back as one unit.
Logs ids and sizes only, never file contents.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.errors import DuplicateError
from app.db.models import Document
from app.db.repositories.courses import CourseRepository
from app.db.repositories.documents import DocumentRepository
from app.ingestion.course_json import parse_course
from app.ingestion.errors import CourseExistsError
from app.ingestion.files import check_size

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
