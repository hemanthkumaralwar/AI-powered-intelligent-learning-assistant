import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document


@dataclass(frozen=True)
class NewChunk:
    """A chunk produced by Step 9's chunker, before it has a vector."""

    id: str
    position: int
    section: str
    text: str
    lesson_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_document(
        self, document_id: uuid.UUID, chunks: Sequence[NewChunk]
    ) -> None:
        """Swap a document's chunks for a new set (re-processing must not leave strays)."""
        await self._session.execute(delete(Chunk).where(Chunk.document_id == document_id))
        self._session.add_all(
            Chunk(
                id=chunk.id,
                document_id=document_id,
                lesson_id=chunk.lesson_id,
                position=chunk.position,
                section=chunk.section,
                text=chunk.text,
                extra=chunk.metadata,
            )
            for chunk in chunks
        )
        await self._session.flush()

    async def list_for_document(self, document_id: uuid.UUID) -> list[Chunk]:
        query = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.position)
        return list(await self._session.scalars(query))

    async def set_embeddings(
        self, embedding_id: str, vectors: Mapping[str, Sequence[float]]
    ) -> None:
        """Store vectors by chunk id, all from the vector space `embedding_id`."""
        if not vectors:
            return
        await self._session.execute(
            update(Chunk),
            [
                {"id": chunk_id, "embedding": list(vector), "embedding_id": embedding_id}
                for chunk_id, vector in vectors.items()
            ],
        )

    async def count_other_spaces(self, embedding_id: str) -> int:
        """Chunks embedded in a different vector space (they need a re-index)."""
        query = select(func.count()).where(
            Chunk.embedding_id.is_not(None), Chunk.embedding_id != embedding_id
        )
        return await self._session.scalar(query) or 0

    async def list_searchable(self, embedding_id: str) -> list[Chunk]:
        """Chunks of fully indexed (`ready`) documents in `embedding_id`: the search index.

        A document still collecting vectors (quota pause) must not be half-searchable.
        """
        query = (
            select(Chunk)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.embedding_id == embedding_id, Document.status == "ready")
            .order_by(Chunk.document_id, Chunk.position)
        )
        return list(await self._session.scalars(query))
