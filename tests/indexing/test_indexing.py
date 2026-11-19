"""Pipeline and IndexingService against the Neon test schema, with fake embeddings."""

import asyncio
import copy
import json
import logging
import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.db.models import Chunk, Document
from app.db.repositories.chunks import ChunkRepository
from app.db.repositories.documents import DocumentRepository
from app.db.session import Database
from app.embeddings.base import EmbeddingTask
from app.embeddings.client import EmbeddingClient
from app.embeddings.fake import FakeEmbeddingModel
from app.indexing import pipeline
from app.indexing.pipeline import FAILED, READY, SKIPPED, index_document
from app.indexing.service import IndexingService
from app.ingestion.service import ingest_course
from app.providers.errors import ProviderUnavailableError, RateLimitedError
from app.providers.rate_limit import RateLimiter
from app.providers.retry import RetryPolicy
from app.vectorstore.index import VectorIndex

pytestmark = pytest.mark.anyio

REAL_COURSE = (
    Path(__file__).resolve().parents[2] / "eval" / "materials" / "javascript-beginner.json"
)


class CountingModel(FakeEmbeddingModel):
    """Fake embeddings that count calls and can fail: always, or after N good calls."""

    def __init__(self, fail_with: Exception | None = None, good_calls: int = 0) -> None:
        super().__init__(dimensions=8)
        self.fail_with = fail_with
        self.good_calls = good_calls

    @property
    def texts_embedded(self) -> int:
        return sum(len(texts) for texts, _ in self.calls)

    async def embed(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]:
        if self.fail_with is not None and len(self.calls) >= self.good_calls:
            self.calls.append(([], task))
            raise self.fail_with
        return await super().embed(texts, task)


def embedder(model: CountingModel, batch_size: int = 100) -> EmbeddingClient:
    return EmbeddingClient(
        model,
        batch_size=batch_size,
        timeout_seconds=5,
        retry_policy=RetryPolicy(max_attempts=1),
        rate_limiter=RateLimiter(100_000),
    )


def small_course_bytes(course_id: str = "small-js") -> bytes:
    data = copy.deepcopy(json.loads(REAL_COURSE.read_bytes()))
    data["course"]["courseId"] = course_id
    modules = data["course"]["modules"][:2]
    for m, module in enumerate(modules, 1):
        module["moduleId"] = f"{course_id}-mod-{m}"
        module["lessons"] = module["lessons"][:2]
        for n, lesson in enumerate(module["lessons"], 1):
            lesson["lessonId"] = f"{course_id}-mod-{m}-lesson-{n}"
    data["course"]["modules"] = modules
    return json.dumps(data).encode()


async def upload(database: Database, course_id: str = "small-js") -> uuid.UUID:
    async with database.session() as session:
        document = await ingest_course(
            session,
            content=small_course_bytes(course_id),
            filename="c.json",
            language="javascript",
            uploaded_by=None,
        )
        return document.id


async def document_status(database: Database, document_id: uuid.UUID) -> tuple[str, str | None]:
    async with database.session() as session:
        document = await DocumentRepository(session).get(document_id)
        return document.status, document.error_message


async def embedded_count(database: Database) -> int:
    async with database.session() as session:
        query = select(func.count()).select_from(Chunk).where(Chunk.embedding_id.is_not(None))
        return await session.scalar(query)


# ---- pipeline ------------------------------------------------------------------------------


async def test_index_document_stores_vectors_and_updates_the_index(database: Database) -> None:
    document_id = await upload(database)
    model = CountingModel()
    index = VectorIndex(8)

    assert await index_document(database, embedder(model), index, document_id) == READY

    assert await document_status(database, document_id) == ("ready", None)
    stored = await embedded_count(database)
    assert stored == index.course_size("small-js") > 20
    async with database.session() as session:
        chunk = (await ChunkRepository(session).list_for_document(document_id))[0]
    hit = index.search(await embedder(model).embed_query(chunk.text), k=1, course_id="small-js")[0]
    assert hit.chunk_id == chunk.id and hit.score == pytest.approx(1.0)


async def test_reindexing_unchanged_content_spends_no_quota(database: Database) -> None:
    document_id = await upload(database)
    index = VectorIndex(8)
    await index_document(database, embedder(CountingModel()), index, document_id)
    first = await embedded_count(database)

    again = CountingModel()
    assert await index_document(database, embedder(again), index, document_id) == READY

    assert await embedded_count(database) == first == index.size
    assert again.calls == []  # every chunk already had a vector in this space


async def test_quota_stop_keeps_progress_and_the_next_run_resumes(database: Database) -> None:
    document_id = await upload(database)
    index = VectorIndex(8)
    stopped = CountingModel(RateLimitedError("per-minute"), good_calls=1)

    outcome = await index_document(database, embedder(stopped, batch_size=10), index, document_id)

    assert outcome.status == "waiting"
    assert (await document_status(database, document_id))[0] == "pending"
    assert await embedded_count(database) == 10  # the first batch was saved
    assert index.size == 0  # not searchable until complete
    async with database.session() as session:
        assert await ChunkRepository(session).list_searchable("fake:fake-embedding:8") == []
        total = len(await ChunkRepository(session).list_for_document(document_id))

    resumed = CountingModel()
    assert await index_document(database, embedder(resumed, 10), index, document_id) == READY
    assert resumed.texts_embedded == total - 10  # only what was missing
    assert index.size == total


@pytest.mark.parametrize(
    ("error", "message", "delay"),
    [
        (RateLimitedError("minute", retry_after=11), "Waiting for the embedding rate limit", 60),
        (RateLimitedError("minute", retry_after=90), "Waiting for the embedding rate limit", 90),
        (RateLimitedError("day", daily=True), "Waiting for the daily embedding quota", 3600),
    ],
    ids=["minute-short", "minute-long", "daily"],
)
async def test_quota_stop_waits_instead_of_failing(
    database: Database, error: RateLimitedError, message: str, delay: float
) -> None:
    document_id = await upload(database)

    outcome = await index_document(
        database, embedder(CountingModel(error)), VectorIndex(8), document_id
    )

    assert (outcome.status, outcome.retry_after) == ("waiting", delay)
    status, reason = await document_status(database, document_id)
    assert status == "pending" and reason.startswith(message)


async def test_service_failure_marks_failed_with_safe_reason(
    database: Database, caplog: pytest.LogCaptureFixture
) -> None:
    document_id = await upload(database)
    index = VectorIndex(8)
    failing = embedder(CountingModel(ProviderUnavailableError("gemini 503 body with details")))

    with caplog.at_level(logging.WARNING):
        assert await index_document(database, failing, index, document_id) == FAILED

    status, reason = await document_status(database, document_id)
    assert status == "failed"
    assert reason == "Embedding service unavailable; re-index later."
    assert index.size == 0
    assert "503 body" not in reason


async def test_unexpected_error_is_recorded_too(database: Database) -> None:
    document_id = await upload(database)
    broken = embedder(CountingModel(RuntimeError("boom")))

    assert await index_document(database, broken, VectorIndex(8), document_id) == FAILED
    assert (await document_status(database, document_id))[0] == "failed"


async def test_missing_document_is_skipped(database: Database) -> None:
    model = CountingModel()

    outcome = await index_document(database, embedder(model), VectorIndex(8), uuid.uuid4())

    assert outcome == SKIPPED
    assert model.calls == []


# ---- service: startup rebuild, resume, re-index, search ------------------------------------


async def test_restart_rebuilds_index_without_any_embedding_calls(database: Database) -> None:
    document_id = await upload(database)
    await index_document(database, embedder(CountingModel()), VectorIndex(8), document_id)

    restarted_model = CountingModel()
    service = IndexingService(database, embedder(restarted_model))
    await service.start()
    try:
        assert service.index.course_size("small-js") == await embedded_count(database) > 0
        assert restarted_model.calls == []  # Done-when: rebuilt from Postgres alone
    finally:
        await service.aclose()
    assert restarted_model.closed is True


async def test_start_resumes_interrupted_documents(database: Database) -> None:
    pending = await upload(database, "first-js")
    processing = await upload(database, "second-js")
    async with database.session() as session:
        await DocumentRepository(session).set_status(processing, "processing")

    service = IndexingService(database, embedder(CountingModel()))
    await service.start()
    await service.wait_until_idle()
    await service.aclose()

    assert (await document_status(database, pending))[0] == "ready"
    assert (await document_status(database, processing))[0] == "ready"
    assert service.index.course_size("first-js") > 0 and service.index.course_size("second-js") > 0


async def test_vectors_from_another_embedding_space_are_not_loaded(
    database: Database, caplog: pytest.LogCaptureFixture
) -> None:
    document_id = await upload(database)
    await index_document(database, embedder(CountingModel()), VectorIndex(8), document_id)
    async with database.session() as session:
        await session.execute(Chunk.__table__.update().values(embedding_id="openai:other:8"))

    service = IndexingService(database, embedder(CountingModel()))
    with caplog.at_level(logging.INFO):
        await service.start()
    await service.aclose()

    assert service.index.size == 0
    assert "use another embedding space" in caplog.text


async def test_reindex_all_requeues_every_document(database: Database) -> None:
    await upload(database)
    service = IndexingService(database, embedder(CountingModel()))
    await service.start()
    await service.wait_until_idle()

    assert await service.reindex_all() == 1
    await service.wait_until_idle()
    await service.aclose()

    async with database.session() as session:
        statuses = list(await session.scalars(select(Document.status)))
    assert statuses == ["ready"]


async def test_enqueue_ignores_duplicates_while_queued(database: Database) -> None:
    document_id = await upload(database)
    model = CountingModel()
    service = IndexingService(database, embedder(model))
    service.enqueue(document_id)
    service.enqueue(document_id)
    await service.start()  # start() also finds it pending; still processed once
    await service.wait_until_idle()
    await service.aclose()

    assert len(model.calls) == 1


async def test_search_and_removals(database: Database) -> None:
    document_id = await upload(database)
    service = IndexingService(database, embedder(CountingModel()))
    await service.start()
    await service.wait_until_idle()
    async with database.session() as session:
        chunk = (await ChunkRepository(session).list_for_document(document_id))[3]

    hits = await service.search(chunk.text, k=3, course_id="small-js")
    assert hits[0].chunk_id == chunk.id

    service.remove_document(document_id)
    assert service.index.size == 0
    service.remove_course("small-js")
    await service.aclose()


async def test_service_retries_a_quota_pause_by_itself(
    database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pipeline, "MIN_RATE_LIMIT_RETRY_SECONDS", 0.05)
    document_id = await upload(database)
    model = CountingModel(RateLimitedError("per-minute", retry_after=0), good_calls=0)
    service = IndexingService(database, embedder(model))

    await service.start()  # finds the pending upload; first attempt hits the quota
    await service.wait_until_idle()
    assert (await document_status(database, document_id))[0] == "pending"

    model.fail_with = None  # quota available again
    for _ in range(100):
        await asyncio.sleep(0.05)
        await service.wait_until_idle()
        if (await document_status(database, document_id))[0] == "ready":
            break
    await service.aclose()

    assert (await document_status(database, document_id)) == ("ready", None)
    assert service.index.course_size("small-js") > 0


async def test_stop_cancels_scheduled_retries(database: Database) -> None:
    document_id = await upload(database)
    service = IndexingService(database, embedder(CountingModel(RateLimitedError("x"))))
    await service.start()
    await service.wait_until_idle()

    assert len(service._retries) == 1
    await service.aclose()
    assert service._retries == set()
    assert (await document_status(database, document_id))[0] == "pending"
