"""Index one uploaded document: chunk -> embed -> store vectors -> update the FAISS index.

Resumable, because the Gemini free tier allows only ~100 embedded texts a minute and
~1,000 a day:
- chunks are stored first and left untouched when unchanged, so saved vectors survive;
- only chunks without a vector in the current embedding space are embedded;
- every batch's vectors are saved as soon as it returns, so a quota stop loses nothing
  and the next run continues where this one stopped.
A document becomes searchable only when all its chunks have vectors (status `ready`);
startup rebuilds load `ready` documents only, so search never sees a half-indexed one.
Embedding happens outside database transactions, so no connection waits on the network.
"""

import logging
import time
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

from app.db.models import Chunk
from app.db.repositories.chunks import ChunkRepository, NewChunk
from app.db.repositories.courses import CourseRepository
from app.db.repositories.documents import DocumentRepository
from app.db.session import Database
from app.embeddings.client import EmbeddingClient
from app.indexing.errors import (
    DEFAULT_FAILURE_REASON,
    FAILURE_REASONS,
    WAITING_FOR_DAILY_QUOTA,
    WAITING_FOR_RATE_LIMIT,
)
from app.ingestion.chunking import chunk_course
from app.providers.errors import RateLimitedError
from app.vectorstore.index import IndexEntry, VectorIndex

logger = logging.getLogger(__name__)

# How long to wait before trying again after a quota stop. The daily quota resets at
# midnight Pacific; checking hourly is cheap (one request) and needs no clock maths.
DAILY_QUOTA_RETRY_SECONDS = 3600.0
MIN_RATE_LIMIT_RETRY_SECONDS = 60.0


@dataclass(frozen=True)
class IndexOutcome:
    status: Literal["ready", "failed", "skipped", "waiting"]
    retry_after: float | None = None


READY = IndexOutcome("ready")
FAILED = IndexOutcome("failed")
SKIPPED = IndexOutcome("skipped")


@dataclass(frozen=True)
class _Plan:
    course_id: str
    missing: list[NewChunk]  # chunks still without a vector in the current space


async def index_document(
    database: Database, embedder: EmbeddingClient, index: VectorIndex, document_id: uuid.UUID
) -> IndexOutcome:
    """Index `document_id` as far as the quota allows.

    Never raises: failures are recorded on the document (status `failed` + a safe reason),
    and quota stops set it back to `pending` with a "waiting" message plus a retry delay.
    """
    started = time.perf_counter()
    try:
        plan = await _prepare(database, embedder.embedding_id, document_id)
        if plan is None:
            return SKIPPED
        for batch in _batches(plan.missing, embedder.batch_size):
            vectors = await embedder.embed_documents([chunk.text for chunk in batch])
            await _save_vectors(database, embedder.embedding_id, batch, vectors)
        entries = await _finish(database, document_id, plan.course_id)
    except RateLimitedError as exc:
        return await _wait_for_quota(database, document_id, exc)
    # Deliberately broad: whatever goes wrong must end up on the document, not kill the worker.
    except Exception as exc:
        await _fail(database, document_id, exc)
        return FAILED
    index.replace_document(document_id, entries)
    logger.info(
        "document indexed document_id=%s chunks=%d embedded_now=%d latency_ms=%d",
        document_id,
        len(entries),
        len(plan.missing),
        (time.perf_counter() - started) * 1000,
    )
    return READY


async def _prepare(database: Database, embedding_id: str, document_id: uuid.UUID) -> _Plan | None:
    async with database.session() as session:
        documents = DocumentRepository(session)
        document = await documents.get(document_id)
        if document is None:
            logger.info("document gone before indexing document_id=%s", document_id)
            return None
        course = await CourseRepository(session).get_full(document.course_id)
        if course is None:
            logger.info("course gone before indexing document_id=%s", document_id)
            return None
        await documents.set_status(document_id, "processing")
        chunks = chunk_course(course, document_id)
        missing = await _store_chunks(ChunkRepository(session), document_id, chunks, embedding_id)
        return _Plan(course.id, missing)


async def _store_chunks(
    repository: ChunkRepository, document_id: uuid.UUID, chunks: list[NewChunk], embedding_id: str
) -> list[NewChunk]:
    """Keep stored chunks (and their vectors) if unchanged; return those still needing one."""
    stored = await repository.list_for_document(document_id)
    if [c.id for c in stored] != [c.id for c in chunks]:
        await repository.replace_for_document(document_id, chunks)
        return chunks
    done = {c.id for c in stored if c.embedding_id == embedding_id}
    return [chunk for chunk in chunks if chunk.id not in done]


async def _save_vectors(
    database: Database,
    embedding_id: str,
    batch: Sequence[NewChunk],
    vectors: list[list[float]],
) -> None:
    async with database.session() as session:
        await ChunkRepository(session).set_embeddings(
            embedding_id, {chunk.id: vector for chunk, vector in zip(batch, vectors, strict=True)}
        )


async def _finish(database: Database, document_id: uuid.UUID, course_id: str) -> list[IndexEntry]:
    async with database.session() as session:
        rows = await ChunkRepository(session).list_for_document(document_id)
        await DocumentRepository(session).set_status(document_id, "ready")
    return [_entry(row, course_id) for row in rows]


async def _wait_for_quota(
    database: Database, document_id: uuid.UUID, exc: RateLimitedError
) -> IndexOutcome:
    if exc.daily:
        message, delay = WAITING_FOR_DAILY_QUOTA, DAILY_QUOTA_RETRY_SECONDS
    else:
        message = WAITING_FOR_RATE_LIMIT
        delay = max(exc.retry_after or 0.0, MIN_RATE_LIMIT_RETRY_SECONDS)
    logger.warning(
        "indexing paused for quota document_id=%s daily=%s retry_in_s=%d",
        document_id,
        exc.daily,
        delay,
    )
    await _record(database, document_id, "pending", message)
    return IndexOutcome("waiting", retry_after=delay)


async def _fail(database: Database, document_id: uuid.UUID, exc: Exception) -> None:
    known = next((text for kind, text in FAILURE_REASONS if isinstance(exc, kind)), None)
    if known is None:
        logger.exception("indexing failed unexpectedly document_id=%s", document_id)
    else:
        logger.warning("indexing failed document_id=%s error=%s", document_id, type(exc).__name__)
    await _record(database, document_id, "failed", known or DEFAULT_FAILURE_REASON)


async def _record(
    database: Database,
    document_id: uuid.UUID,
    status: Literal["pending", "failed"],
    message: str,
) -> None:
    try:
        async with database.session() as session:
            await DocumentRepository(session).set_status(document_id, status, message)
    # The database itself may be what failed; log and move on.
    except Exception:
        logger.exception("could not record indexing state document_id=%s", document_id)


def _batches(chunks: list[NewChunk], size: int) -> Iterator[list[NewChunk]]:
    for start in range(0, len(chunks), size):
        yield chunks[start : start + size]


def _entry(row: Chunk, course_id: str) -> IndexEntry:
    return IndexEntry(
        chunk_id=row.id,
        document_id=row.document_id,
        course_id=course_id,
        lesson_id=row.lesson_id,
        section=row.section,
        text=row.text,
        vector=row.embedding or [],
        metadata=row.extra,
    )
