"""`EmbeddingClient`: the single entry point the app uses to turn text into vectors."""

import asyncio
import logging
import math
import time
from collections.abc import Sequence

from app.core.cache import TTLCache
from app.embeddings.base import EmbeddingModel, EmbeddingTask
from app.providers.errors import InvalidResponseError, ProviderTimeoutError
from app.providers.rate_limit import RateLimiter
from app.providers.retry import RetryPolicy, Sleep, call_with_retry

logger = logging.getLogger(__name__)

# About 3 MB of 768-dimension vectors.
QUERY_CACHE_ENTRIES = 512


class EmbeddingClient:
    """Batches, rate-limits, retries, checks and normalises embedding calls.

    Text is never logged: chunks are course material, but queries are student questions.
    """

    def __init__(
        self,
        model: EmbeddingModel,
        *,
        batch_size: int,
        timeout_seconds: float,
        retry_policy: RetryPolicy,
        rate_limiter: RateLimiter,
        query_rate_limiter: RateLimiter | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._model = model
        self._batch_size = min(batch_size, model.max_batch_size)
        self._timeout_seconds = timeout_seconds
        self._retry_policy = retry_policy
        # Separate budgets: a student's question never queues behind an indexing batch.
        self._limiters: dict[EmbeddingTask, RateLimiter] = {
            "document": rate_limiter,
            "query": query_rate_limiter or rate_limiter,
        }
        self._sleep = sleep
        # Students in one course ask the same questions; each repeat would cost a text of
        # the free tier's daily budget. One client serves one vector space, so the text
        # alone is the key.
        self._query_cache: TTLCache[list[float]] = TTLCache(QUERY_CACHE_ENTRIES)

    @property
    def provider(self) -> str:
        return self._model.provider

    @property
    def batch_size(self) -> int:
        """Texts per request; callers that save progress per batch use the same size."""
        return self._batch_size

    @property
    def dimensions(self) -> int:
        return self._model.dimensions

    @property
    def embedding_id(self) -> str:
        """Identifies the vector space; vectors with different ids must not be mixed."""
        return f"{self._model.provider}:{self._model.model}:{self._model.dimensions}"

    async def aclose(self) -> None:
        await self._model.aclose()

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed course chunks, preserving order. An empty input makes no API call."""
        _require_text(texts)
        started = time.perf_counter()
        batches = [texts[i : i + self._batch_size] for i in range(0, len(texts), self._batch_size)]
        vectors: list[list[float]] = []
        for batch in batches:
            vectors.extend(await self._embed_batch(batch, "document"))
        logger.info(
            "embeddings provider=%s model=%s task=document texts=%d batches=%d latency_ms=%d",
            self.provider,
            self._model.model,
            len(texts),
            len(batches),
            (time.perf_counter() - started) * 1000,
        )
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        """Embed one student question for similarity search (repeats come from a cache)."""
        _require_text([text])
        key = " ".join(text.split())
        if (cached := self._query_cache.get(key)) is not None:
            return cached
        (vector,) = await self._embed_batch([text], "query")
        self._query_cache.set(key, vector)
        return vector

    async def _embed_batch(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]:
        vectors, _ = await call_with_retry(
            lambda: self._embed_once(texts, task), self._retry_policy, self._sleep
        )
        self._check_shape(vectors, expected_count=len(texts))
        return [l2_normalize(vector) for vector in vectors]

    async def _embed_once(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]:
        # Each attempt is a separate request and every text in it counts against the
        # provider's quota (Gemini meters batch items individually), so reserve one unit
        # per text.
        await self._limiters[task].acquire(cost=len(texts))
        try:
            async with asyncio.timeout(self._timeout_seconds):
                return await self._model.embed(texts, task)
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                f"{self.provider} embeddings did not respond within {self._timeout_seconds}s"
            ) from exc

    def _check_shape(self, vectors: list[list[float]], expected_count: int) -> None:
        # Some models (e.g. gemini-embedding-2) merge a batch into one vector; catching it
        # here prevents chunks being stored against the wrong vectors.
        if len(vectors) != expected_count:
            raise InvalidResponseError(
                f"{self.provider} returned {len(vectors)} vectors for {expected_count} texts"
            )
        if any(len(vector) != self.dimensions for vector in vectors):
            raise InvalidResponseError(
                f"{self.provider} returned vectors that are not {self.dimensions}-dimensional"
            )


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Scale to unit length so dot product equals cosine similarity for every provider."""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        raise InvalidResponseError("provider returned an all-zero vector")
    return [value / norm for value in vector]


def _require_text(texts: Sequence[str]) -> None:
    if any(not text.strip() for text in texts):
        raise ValueError("texts to embed must not be empty or whitespace")
