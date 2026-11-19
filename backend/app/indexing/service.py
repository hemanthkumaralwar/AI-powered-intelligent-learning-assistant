"""IndexingService: owns the vector index, the embedding client and a one-at-a-time worker.

- `start()`: rebuild the FAISS index from Postgres (no embedding calls), then queue any
  document a restart interrupted, then start the worker.
- `enqueue()`: queue a document after its upload has committed.
- One worker processes documents sequentially, keeping memory and embedding quota
  predictable and avoiding two jobs racing on the same course.
- A document paused by the embedding quota is queued again after the delay the pipeline
  asks for (about a minute, or hourly checks while the daily quota is exhausted).
"""

import asyncio
import contextlib
import logging
import uuid

from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.documents import DocumentRepository
from app.db.session import Database
from app.embeddings.client import EmbeddingClient
from app.indexing.pipeline import index_document
from app.vectorstore.index import IndexEntry, SearchHit, VectorIndex

logger = logging.getLogger(__name__)


class IndexingService:
    def __init__(self, database: Database, embedder: EmbeddingClient) -> None:
        self._database = database
        self._embedder = embedder
        self.index = VectorIndex(embedder.dimensions)
        self._queue: asyncio.Queue[uuid.UUID] = asyncio.Queue()
        self._queued: set[uuid.UUID] = set()
        self._worker: asyncio.Task[None] | None = None
        self._retries: set[asyncio.Task[None]] = set()

    @property
    def embedding_id(self) -> str:
        return self._embedder.embedding_id

    async def start(self) -> None:
        await self.rebuild_index()
        async with self._database.session() as session:
            interrupted = await DocumentRepository(session).ids_with_status("pending", "processing")
        for document_id in interrupted:
            self.enqueue(document_id)
        if interrupted:
            logger.info("resuming interrupted indexing documents=%d", len(interrupted))
        self._worker = asyncio.create_task(self._run(), name="indexing-worker")

    async def stop(self) -> None:
        for retry in list(self._retries):
            retry.cancel()
        self._retries.clear()
        if self._worker is not None:
            self._worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None

    async def aclose(self) -> None:
        await self.stop()
        await self._embedder.aclose()

    async def rebuild_index(self) -> int:
        """Load every stored vector of the current embedding space. Makes no embedding calls."""
        embedding_id = self._embedder.embedding_id
        async with self._database.session() as session:
            chunks = ChunkRepository(session)
            rows = await chunks.list_searchable(embedding_id)
            stale = await chunks.count_other_spaces(embedding_id)
        self.index.add(
            IndexEntry(
                chunk_id=row.id,
                document_id=row.document_id,
                course_id=row.extra["course_id"],
                lesson_id=row.lesson_id,
                section=row.section,
                text=row.text,
                vector=row.embedding or [],
                metadata=row.extra,
            )
            for row in rows
        )
        logger.info(
            "vector index rebuilt chunks=%d embedding_id=%s other_spaces=%d",
            len(rows),
            embedding_id,
            stale,
        )
        if stale:
            logger.warning("%d chunks use another embedding space; run POST /admin/reindex", stale)
        return len(rows)

    def enqueue(self, document_id: uuid.UUID) -> None:
        if document_id not in self._queued:
            self._queued.add(document_id)
            self._queue.put_nowait(document_id)

    async def reindex_all(self) -> int:
        """Mark every document pending and queue it (e.g. after an embedding change)."""
        async with self._database.session() as session:
            document_ids = await DocumentRepository(session).mark_all_pending()
        for document_id in document_ids:
            self.enqueue(document_id)
        return len(document_ids)

    async def wait_until_idle(self) -> None:
        """Return once everything queued so far has been processed (tests, scripts)."""
        await self._queue.join()

    def remove_document(self, document_id: uuid.UUID) -> None:
        self.index.remove_document(document_id)

    def remove_course(self, course_id: str) -> None:
        self.index.remove_course(course_id)

    async def search(self, query: str, k: int, course_id: str | None = None) -> list[SearchHit]:
        """Embed the question (query task type) and return the k closest chunks."""
        vector = await self._embedder.embed_query(query)
        return self.index.search(vector, k, course_id)

    async def _run(self) -> None:
        while True:
            document_id = await self._queue.get()
            # Leave the dedupe set first: an upload arriving while this one runs may
            # need it indexed again afterwards.
            self._queued.discard(document_id)
            try:
                outcome = await index_document(
                    self._database, self._embedder, self.index, document_id
                )
                if outcome.status == "waiting" and outcome.retry_after is not None:
                    self._retry_later(document_id, outcome.retry_after)
            finally:
                self._queue.task_done()

    def _retry_later(self, document_id: uuid.UUID, delay: float) -> None:
        async def requeue() -> None:
            await asyncio.sleep(delay)
            self.enqueue(document_id)

        task = asyncio.create_task(requeue(), name=f"indexing-retry-{document_id}")
        self._retries.add(task)
        task.add_done_callback(self._retries.discard)
