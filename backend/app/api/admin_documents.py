"""Admin-only course material management: upload, list, download, delete."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.api.deps import Session, require_admin
from app.api.downloads import file_response
from app.api.schemas.materials import DocumentResponse
from app.db.models import User
from app.db.repositories.courses import CourseRepository
from app.db.repositories.documents import DocumentRepository
from app.ingestion.errors import (
    CourseExistsError,
    FileTooLargeError,
    UnknownTargetError,
    UnsupportedFileTypeError,
    UploadRejectedError,
)
from app.ingestion.files import MAX_UPLOAD_BYTES, file_kind, safe_filename
from app.ingestion.service import ingest_course, ingest_notes
from app.runner.base import Language

# Every route here requires an admin.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
Admin = Annotated[User, Depends(require_admin)]

_STATUS = {
    FileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    UnsupportedFileTypeError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    CourseExistsError: status.HTTP_409_CONFLICT,
    UnknownTargetError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    admin: Admin,
    session: Session,
    file: Annotated[UploadFile, File(description="A course .json or a .txt notes file")],
    language: Annotated[Language | None, Form(description="Required for course JSON")] = None,
    course_id: Annotated[str | None, Form(description="Required for .txt notes")] = None,
    module_id: Annotated[str | None, Form()] = None,
    lesson_id: Annotated[str | None, Form()] = None,
) -> DocumentResponse:
    """Upload a course JSON (creates the course) or TXT notes (attached to a course)."""
    filename = safe_filename(file.filename)
    # The body-size middleware already capped the request; read one byte over the
    # limit so an exact-limit file is accepted and anything larger is not.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        if file_kind(filename) == "json":
            if language is None:
                raise _bad_request("Choose the course's programming language.")
            document = await ingest_course(
                session,
                content=content,
                filename=filename,
                language=language,
                uploaded_by=admin.id,
            )
        else:
            if not course_id:
                raise _bad_request("Choose the course these notes belong to.")
            document = await ingest_notes(
                session,
                content=content,
                filename=filename,
                course_id=course_id,
                module_id=module_id or None,
                lesson_id=lesson_id or None,
                uploaded_by=admin.id,
            )
    except UploadRejectedError as exc:
        code = _STATUS.get(type(exc), status.HTTP_422_UNPROCESSABLE_CONTENT)
        raise HTTPException(code, str(exc)) from exc
    return DocumentResponse.model_validate(document)


@router.get("/documents")
async def list_documents(session: Session, course_id: str | None = None) -> list[DocumentResponse]:
    documents = await DocumentRepository(session).list(course_id)
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get("/documents/{document_id}/download")
async def download_document(document_id: uuid.UUID, session: Session) -> Response:
    """The original file, including course JSON with its answers (admins only)."""
    documents = DocumentRepository(session)
    document = await documents.get(document_id)
    content = await documents.get_content(document_id) if document else None
    if document is None or content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return file_response(document, content)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, session: Session) -> None:
    if not await DocumentRepository(session).delete(document_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course_id: str, session: Session) -> None:
    """Delete a course and EVERYTHING attached to it: lessons, quizzes, exercises, and all
    of its documents including notes. Use this before re-uploading a changed course."""
    if not await CourseRepository(session).delete(course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)
