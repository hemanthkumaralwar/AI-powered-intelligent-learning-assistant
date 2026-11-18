import hashlib
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentFile, DocumentStatus


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        course_id: str,
        filename: str,
        content_type: str,
        content: bytes,
        uploaded_by: uuid.UUID | None,
    ) -> Document:
        """Store a document and its bytes. Size and hash come from `content` itself."""
        if not content:
            raise ValueError("document content must not be empty")
        document = Document(
            course_id=course_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            status="pending",
            uploaded_by=uploaded_by,
        )
        self._session.add(document)
        await self._session.flush()
        self._session.add(DocumentFile(document_id=document.id, content=content))
        await self._session.flush()
        return document

    async def get(self, document_id: uuid.UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    async def get_content(self, document_id: uuid.UUID) -> bytes | None:
        query = select(DocumentFile.content).where(DocumentFile.document_id == document_id)
        return await self._session.scalar(query)

    async def list(self, course_id: str | None = None) -> list[Document]:
        """Newest first, optionally for one course. Never loads file contents."""
        query = select(Document).order_by(Document.created_at.desc(), Document.id)
        if course_id is not None:
            query = query.where(Document.course_id == course_id)
        return list(await self._session.scalars(query))

    async def set_status(
        self, document_id: uuid.UUID, status: DocumentStatus, error_message: str | None = None
    ) -> bool:
        """Update processing status. Returns False if the document does not exist."""
        result = await self._session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(status=status, error_message=error_message)
        )
        return result.rowcount == 1

    async def delete(self, document_id: uuid.UUID) -> bool:
        """Delete a document; its file and chunks go with it (ON DELETE CASCADE)."""
        document = await self.get(document_id)
        if document is None:
            return False
        await self._session.delete(document)
        await self._session.flush()
        return True
