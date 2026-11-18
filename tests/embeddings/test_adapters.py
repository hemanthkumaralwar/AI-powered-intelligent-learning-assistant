"""Gemini, OpenAI, Hugging Face and fake embedding adapters, with SDK stubs (no network)."""

from types import SimpleNamespace
from typing import Any

import httpx2
import openai
import pytest
from google.genai import errors

from app.embeddings.fake import FakeEmbeddingModel, fake_vector
from app.embeddings.gemini import GeminiEmbeddingModel
from app.embeddings.huggingface import HuggingFaceEmbeddingModel
from app.embeddings.openai import OpenAIEmbeddingModel
from app.providers.errors import ProviderConfigurationError, RateLimitedError

pytestmark = pytest.mark.anyio


class Recorder:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def gemini_client(outcome: Any) -> tuple[SimpleNamespace, Recorder]:
    recorder = Recorder(outcome)
    return SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(embed_content=recorder))
    ), recorder


def openai_client(outcome: Any) -> tuple[SimpleNamespace, Recorder]:
    recorder = Recorder(outcome)
    return SimpleNamespace(embeddings=SimpleNamespace(create=recorder)), recorder


@pytest.mark.parametrize(
    ("task", "task_type"), [("document", "RETRIEVAL_DOCUMENT"), ("query", "RETRIEVAL_QUERY")]
)
async def test_gemini_sends_task_type_and_dimensions(task: str, task_type: str) -> None:
    result = SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2])])
    client, recorder = gemini_client(result)

    vectors = await GeminiEmbeddingModel(client, "gemini-embedding-001", 2).embed(["hi"], task)

    assert vectors == [[0.1, 0.2]]
    call = recorder.calls[0]
    assert (call["model"], call["contents"]) == ("gemini-embedding-001", ["hi"])
    assert call["config"].task_type == task_type
    assert call["config"].output_dimensionality == 2


async def test_gemini_handles_missing_embeddings() -> None:
    client, _ = gemini_client(SimpleNamespace(embeddings=None))

    assert await GeminiEmbeddingModel(client, "m", 2).embed(["hi"], "document") == []


async def test_gemini_maps_rate_limit() -> None:
    client, _ = gemini_client(errors.ClientError(429, {"error": {"code": 429}}))

    with pytest.raises(RateLimitedError):
        await GeminiEmbeddingModel(client, "m", 2).embed(["hi"], "document")


async def test_openai_orders_by_index_and_sends_dimensions() -> None:
    data = [
        SimpleNamespace(index=1, embedding=[0.0, 1.0]),
        SimpleNamespace(index=0, embedding=[1.0, 0.0]),
    ]
    client, recorder = openai_client(SimpleNamespace(data=data))

    vectors = await OpenAIEmbeddingModel(client, "text-embedding-3-small", 2).embed(
        ["first", "second"], "query"
    )

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert recorder.calls[0] == {
        "model": "text-embedding-3-small",
        "input": ["first", "second"],
        "dimensions": 2,
    }


async def test_openai_maps_rate_limit() -> None:
    request = httpx2.Request("POST", "https://api.openai.com/v1/embeddings")
    error = openai.RateLimitError(
        "slow down", response=httpx2.Response(429, request=request), body=None
    )
    client, _ = openai_client(error)

    with pytest.raises(RateLimitedError):
        await OpenAIEmbeddingModel(client, "m", 2).embed(["hi"], "document")


class StubEncoder:
    def __init__(self, dimensions: int | None = 3) -> None:
        self.dimensions = dimensions
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def get_embedding_dimension(self) -> int | None:
        return self.dimensions

    def encode(self, sentences: list[str], **kwargs: Any) -> Any:
        self.calls.append((sentences, kwargs))
        rows = [[float(len(s)), 1.0, 0.0] for s in sentences]
        return SimpleNamespace(tolist=lambda: rows)


async def test_huggingface_encodes_in_a_thread_with_model_size() -> None:
    encoder = StubEncoder()
    model = HuggingFaceEmbeddingModel(encoder, "BAAI/bge-small-en-v1.5")

    vectors = await model.embed(["ab", "abc"], "query")

    assert model.dimensions == 3
    assert vectors == [[2.0, 1.0, 0.0], [3.0, 1.0, 0.0]]
    assert encoder.calls == [(["ab", "abc"], {"batch_size": 64})]


def test_huggingface_rejects_model_without_known_size() -> None:
    with pytest.raises(ProviderConfigurationError, match="embedding size"):
        HuggingFaceEmbeddingModel(StubEncoder(dimensions=None), "broken/model")


async def test_fake_is_deterministic_and_bounded() -> None:
    model = FakeEmbeddingModel(dimensions=16)

    first, again, other = await model.embed(["loops", "loops", "arrays"], "document")

    assert first == again != other
    assert all(-1.0 <= value <= 1.0 for value in first)
    assert first == fake_vector("loops", 16)
    assert model.calls == [(["loops", "loops", "arrays"], "document")]
