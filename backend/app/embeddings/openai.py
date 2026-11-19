"""OpenAI embedding adapter. Selected with EMBEDDING_PROVIDER=openai."""

from collections.abc import Sequence

import openai

from app.embeddings.base import EmbeddingTask
from app.providers.openai_sdk import translate_openai_errors


class OpenAIEmbeddingModel:
    provider = "openai"
    # OpenAI accepts up to 2048 inputs per embeddings request.
    max_batch_size = 2048

    def __init__(self, client: openai.AsyncOpenAI, model: str, dimensions: int) -> None:
        self._client = client
        self.model = model
        self.dimensions = dimensions

    async def embed(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]:
        # OpenAI embeds documents and queries the same way, so `task` is unused.
        with translate_openai_errors():
            result = await self._client.embeddings.create(
                model=self.model, input=list(texts), dimensions=self.dimensions
            )
        # Sort by index: the API documents order by `index`, not list position.
        return [item.embedding for item in sorted(result.data, key=lambda item: item.index)]

    async def aclose(self) -> None:
        await self._client.close()
