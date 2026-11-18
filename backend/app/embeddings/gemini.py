"""Gemini embedding adapter (official `google-genai` SDK)."""

from collections.abc import Sequence

from google import genai
from google.genai import types

from app.embeddings.base import EmbeddingTask
from app.providers.gemini_sdk import translate_gemini_errors

_TASK_TYPES: dict[EmbeddingTask, str] = {
    "document": "RETRIEVAL_DOCUMENT",
    "query": "RETRIEVAL_QUERY",
}


class GeminiEmbeddingModel:
    provider = "gemini"
    # Gemini's batch embedding endpoint accepts at most 100 texts per request.
    max_batch_size = 100

    def __init__(self, client: genai.Client, model: str, dimensions: int) -> None:
        self._client = client
        self.model = model
        self.dimensions = dimensions

    async def embed(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]:
        with translate_gemini_errors():
            result = await self._client.aio.models.embed_content(
                model=self.model,
                contents=list(texts),
                config=types.EmbedContentConfig(
                    task_type=_TASK_TYPES[task], output_dimensionality=self.dimensions
                ),
            )
        return [list(embedding.values or []) for embedding in result.embeddings or []]
