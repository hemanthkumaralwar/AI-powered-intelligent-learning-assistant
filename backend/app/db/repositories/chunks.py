import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk


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

    async def list_embedded(self, embedding_id: str) -> list[Chunk]:
        """Every chunk with a vector in `embedding_id`, used to rebuild the Chroma index."""
        query = (
            select(Chunk)
            .where(Chunk.embedding_id == embedding_id)
            .order_by(Chunk.document_id, Chunk.position)
        )
        return list(await self._session.scalars(query))
