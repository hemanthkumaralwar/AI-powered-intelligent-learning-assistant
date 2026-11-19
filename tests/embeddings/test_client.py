import asyncio
import logging
import math
from collections.abc import Sequence

import pytest

from app.embeddings.base import EmbeddingTask
from app.embeddings.client import EmbeddingClient, l2_normalize
from app.embeddings.fake import FakeEmbeddingModel
from app.providers.errors import (
    InvalidResponseError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.rate_limit import RateLimiter
from app.providers.retry import RetryPolicy

pytestmark = pytest.mark.anyio


async def no_sleep(_: float) -> None:
    return None


class CountingLimiter(RateLimiter):
    def __init__(self) -> None:
        super().__init__(60, sleep=no_sleep)
        self.acquired = 0
        self.costs: list[int] = []

    async def acquire(self, cost: int = 1) -> None:
        self.acquired += 1
        self.costs.append(cost)


class ScriptedModel:
    """Returns or raises scripted outcomes, one per call."""

    provider = "scripted"
    model = "scripted-model"
    max_batch_size = 100

    def __init__(self, outcomes: list, dimensions: int = 3, delay: float = 0.0) -> None:
        self.outcomes = outcomes
        self.dimensions = dimensions
        self.delay = delay

    async def embed(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]:
        if self.delay:
            await asyncio.sleep(self.delay)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_client(
    model, batch_size: int = 100, timeout: float = 5.0, limiter=None
) -> EmbeddingClient:
    return EmbeddingClient(
        model,
        batch_size=batch_size,
        timeout_seconds=timeout,
        retry_policy=RetryPolicy(max_attempts=3),
        rate_limiter=limiter or CountingLimiter(),
        sleep=no_sleep,
    )


def is_unit(vector: list[float]) -> bool:
    return math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0)


async def test_embed_documents_returns_unit_vectors_in_order() -> None:
    model = FakeEmbeddingModel(dimensions=8)
    client = make_client(model)

    vectors = await client.embed_documents(["let", "const", "let"])

    assert len(vectors) == 3
    assert all(len(v) == 8 and is_unit(v) for v in vectors)
    assert vectors[0] == vectors[2] != vectors[1]
    assert model.calls == [(["let", "const", "let"], "document")]


async def test_empty_input_makes_no_call() -> None:
    model = FakeEmbeddingModel()
    limiter = CountingLimiter()

    assert await make_client(model, limiter=limiter).embed_documents([]) == []
    assert model.calls == []
    assert limiter.acquired == 0


@pytest.mark.parametrize("texts", [[""], ["ok", "   "], ["\n\t"]])
async def test_blank_text_is_rejected_before_any_call(texts: list[str]) -> None:
    model = FakeEmbeddingModel()

    with pytest.raises(ValueError, match="must not be empty"):
        await make_client(model).embed_documents(texts)
    assert model.calls == []


async def test_blank_query_is_rejected() -> None:
    with pytest.raises(ValueError):
        await make_client(FakeEmbeddingModel()).embed_query("  ")


async def test_documents_are_split_into_batches_with_one_slot_each() -> None:
    model = FakeEmbeddingModel()
    limiter = CountingLimiter()

    vectors = await make_client(model, batch_size=2, limiter=limiter).embed_documents(
        ["a", "b", "c", "d", "e"]
    )

    assert [len(texts) for texts, _ in model.calls] == [2, 2, 1]
    assert len(vectors) == 5
    # One slot per request, charged one unit per text (Gemini meters every batch item).
    assert limiter.costs == [2, 2, 1]


async def test_batch_size_is_capped_by_the_model() -> None:
    model = FakeEmbeddingModel()
    model.max_batch_size = 2

    await make_client(model, batch_size=100).embed_documents(["a", "b", "c"])

    assert [len(texts) for texts, _ in model.calls] == [2, 1]


async def test_embed_query_uses_query_task() -> None:
    model = FakeEmbeddingModel(dimensions=4)

    vector = await make_client(model).embed_query("What is a closure?")

    assert len(vector) == 4 and is_unit(vector)
    assert model.calls == [(["What is a closure?"], "query")]


async def test_query_and_document_of_same_text_match() -> None:
    client = make_client(FakeEmbeddingModel())

    assert await client.embed_query("arrays") == (await client.embed_documents(["arrays"]))[0]


async def test_vector_count_mismatch_is_rejected() -> None:
    model = ScriptedModel([[[1.0, 0.0, 0.0]]])

    with pytest.raises(InvalidResponseError, match="1 vectors for 2 texts"):
        await make_client(model).embed_documents(["a", "b"])


async def test_wrong_dimensions_are_rejected() -> None:
    model = ScriptedModel([[[1.0, 0.0]]], dimensions=3)

    with pytest.raises(InvalidResponseError, match="not 3-dimensional"):
        await make_client(model).embed_documents(["a"])


async def test_zero_vector_is_rejected() -> None:
    model = ScriptedModel([[[0.0, 0.0, 0.0]]])

    with pytest.raises(InvalidResponseError, match="all-zero"):
        await make_client(model).embed_documents(["a"])


async def test_transient_failure_is_retried_with_a_new_slot() -> None:
    model = ScriptedModel([ProviderUnavailableError("503"), [[3.0, 4.0, 0.0]]])
    limiter = CountingLimiter()

    vectors = await make_client(model, limiter=limiter).embed_documents(["a"])

    assert vectors == [[0.6, 0.8, 0.0]]
    assert limiter.acquired == 2


async def test_slow_provider_times_out() -> None:
    model = ScriptedModel([[[1.0, 0.0, 0.0]]] * 3, delay=1.0)

    with pytest.raises(ProviderTimeoutError, match="scripted embeddings did not respond"):
        await make_client(model, timeout=0.01).embed_documents(["a"])


async def test_embedding_id_names_the_vector_space() -> None:
    client = make_client(FakeEmbeddingModel(dimensions=16))

    assert client.embedding_id == "fake:fake-embedding:16"
    assert (client.provider, client.dimensions) == ("fake", 16)


async def test_logs_metadata_but_never_text(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="app.embeddings.client"):
        await make_client(FakeEmbeddingModel()).embed_documents(["SECRET-CHUNK-TEXT"])

    assert "texts=1 batches=1" in caplog.text
    assert "SECRET-CHUNK-TEXT" not in caplog.text


def test_l2_normalize() -> None:
    assert l2_normalize([3.0, 4.0]) == [0.6, 0.8]


async def test_questions_use_their_own_budget() -> None:
    documents, questions = CountingLimiter(), CountingLimiter()
    client = EmbeddingClient(
        FakeEmbeddingModel(),
        batch_size=10,
        timeout_seconds=5,
        retry_policy=RetryPolicy(max_attempts=1),
        rate_limiter=documents,
        query_rate_limiter=questions,
        sleep=no_sleep,
    )

    await client.embed_documents(["a", "b", "c"])
    await client.embed_query("what is a closure?")

    assert (documents.costs, questions.costs) == ([3], [1])
    assert client.batch_size == 10


async def test_without_a_query_budget_questions_share_the_document_one() -> None:
    shared = CountingLimiter()

    await make_client(FakeEmbeddingModel(), limiter=shared).embed_query("x")

    assert shared.costs == [1]


async def test_repeated_questions_are_embedded_once() -> None:
    model = ScriptedModel([[[1.0, 0.0, 0.0]], [[0.0, 1.0, 0.0]]])
    client = make_client(model)

    first = await client.embed_query("What is let?")
    again = await client.embed_query("  What   is let? ")  # same text, other spacing
    other = await client.embed_query("What is const?")

    assert first == again != other
    assert model.outcomes == []  # exactly two provider calls
