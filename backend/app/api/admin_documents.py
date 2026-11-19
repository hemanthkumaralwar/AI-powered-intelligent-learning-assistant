"""Admin-only course management: upload, list, download, delete, re-index, search."""

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

from app.api.deps import Session, require_admin
from app.api.downloads import file_response
from app.api.schemas.materials import DocumentResponse
from app.api.schemas.search import ReindexResponse, SearchHitResponse, SearchRequest
from app.db.models import User
from app.db.repositories.courses import CourseRepository
from app.db.repositories.documents import DocumentRepository
from app.indexing.service import IndexingService
from app.ingestion.errors import (
    CourseExistsError,
    FileTooLargeError,
    UnsupportedFileTypeError,
    UploadRejectedError,
)
from app.ingestion.files import MAX_UPLOAD_BYTES, require_course_json, safe_filename
from app.ingestion.service import ingest_course
from app.providers.errors import ProviderCallError
from app.runner.base import Language

# Every route here requires an admin.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
Admin = Annotated[User, Depends(require_admin)]


def get_indexing(request: Request) -> IndexingService:
    return request.app.state.indexing


Indexing = Annotated[IndexingService, Depends(get_indexing)]

_STATUS = {
    FileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    UnsupportedFileTypeError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    CourseExistsError: status.HTTP_409_CONFLICT,
}


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    admin: Admin,
    session: Session,
    indexing: Indexing,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File(description="A course JSON file")],
    language: Annotated[Language, Form(description="Programming language of the course")],
) -> DocumentResponse:
    """Upload a course JSON; creates the course, then indexes it in the background.

    The response comes back with status `pending`; poll GET /admin/documents for
    `ready` (or `failed` with a reason).
    """
    filename = safe_filename(file.filename)
    # The body-size middleware already capped the request; read one byte over the
    # limit so an exact-limit file is accepted and anything larger is not.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        require_course_json(filename)
        document = await ingest_course(
            session, content=content, filename=filename, language=language, uploaded_by=admin.id
        )
    except UploadRejectedError as exc:
        code = _STATUS.get(type(exc), status.HTTP_422_UNPROCESSABLE_CONTENT)
        raise HTTPException(code, str(exc)) from exc
    # Background tasks run after the response, i.e. after the upload has committed, so
    # the worker always finds the document.
    background.add_task(indexing.enqueue, document.id)
    return DocumentResponse.model_validate(document)


@router.get("/documents")
async def list_documents(session: Session, course_id: str | None = None) -> list[DocumentResponse]:
    documents = await DocumentRepository(session).list_documents(course_id)
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
async def delete_document(
    document_id: uuid.UUID, session: Session, indexing: Indexing, background: BackgroundTasks
) -> None:
    if not await DocumentRepository(session).delete(document_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    background.add_task(indexing.remove_document, document_id)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str, session: Session, indexing: Indexing, background: BackgroundTasks
) -> None:
    """Delete a course and EVERYTHING attached to it: lessons, quizzes, exercises, and all
    of its stored documents and vectors. Use this before re-uploading a changed course."""
    if not await CourseRepository(session).delete(course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    background.add_task(indexing.remove_course, course_id)


@router.post("/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex(indexing: Indexing) -> ReindexResponse:
    """Re-embed every document, e.g. after changing the embedding provider or model."""
    return ReindexResponse(queued=await indexing.reindex_all())


@router.post("/search")
async def search(body: SearchRequest, indexing: Indexing) -> list[SearchHitResponse]:
    """What retrieval would return for a question (to check retrieval quality)."""
    try:
        hits = await indexing.search(body.query, body.k, body.course_id)
    except ProviderCallError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The embedding service is unavailable."
        ) from exc
    return [SearchHitResponse.model_validate(hit, from_attributes=True) for hit in hits]
