"""Course materials for any logged-in user. Answers are never part of these responses:
course JSON files cannot be downloaded here, and the response models have no answer fields."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, Session
from app.api.downloads import file_response
from app.api.schemas.materials import CourseOutline, CourseSummary, DocumentResponse, LessonResponse
from app.db.repositories.courses import CourseRepository
from app.db.repositories.documents import DocumentRepository

router = APIRouter(tags=["materials"])


@router.get("/courses")
async def list_courses(user: CurrentUser, session: Session) -> list[CourseSummary]:
    return [CourseSummary.model_validate(c) for c in await CourseRepository(session).list()]


@router.get("/courses/{course_id}")
async def course_outline(course_id: str, user: CurrentUser, session: Session) -> CourseOutline:
    """Modules (with their explanations) and lesson titles, in order."""
    course = await CourseRepository(session).get(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return CourseOutline.model_validate(course, from_attributes=True)


@router.get("/lessons/{lesson_id}")
async def lesson(lesson_id: str, user: CurrentUser, session: Session) -> LessonResponse:
    """Teaching content and exercises (starter code, hints), without any solutions."""
    found = await CourseRepository(session).get_lesson(lesson_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    return LessonResponse.model_validate(found)


@router.get("/materials")
async def list_notes(
    user: CurrentUser, session: Session, course_id: str | None = None
) -> list[DocumentResponse]:
    """Downloadable notes (TXT). Course JSON files are not listed: they contain answers."""
    documents = await DocumentRepository(session).list(course_id, kind="notes")
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get("/materials/{document_id}/download")
async def download_notes(document_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    documents = DocumentRepository(session)
    document = await documents.get(document_id)
    # A course JSON answers 404 too, so students cannot even confirm it exists.
    if document is None or document.kind != "notes":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    content = await documents.get_content(document_id)
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return file_response(document, content)
