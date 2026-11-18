"""Local Hugging Face embeddings via sentence-transformers. For local runs only.

Needs `pip install -r requirements-local.txt` (pulls in torch, about 1 GB). Production on
Render never installs it, which is why the import happens inside `load_sentence_transformer`.
"""

import asyncio
from collections.abc import Sequence
from typing import Any, Protocol

from app.embeddings.base import EmbeddingTask
from app.providers.errors import ProviderConfigurationError


class SentenceEncoder(Protocol):
    """The slice of `SentenceTransformer` this adapter uses (lets tests pass a stub)."""

    def encode(self, sentences: list[str], **kwargs: Any) -> Any: ...

    def get_embedding_dimension(self) -> int | None: ...


class HuggingFaceEmbeddingModel:
    provider = "huggingface"
    # Keeps CPU memory bounded on a laptop; the model itself has no hard limit.
    max_batch_size = 64

    def __init__(self, encoder: SentenceEncoder, model: str) -> None:
        dimensions = encoder.get_embedding_dimension()
        if not dimensions:
            raise ProviderConfigurationError(f"cannot read the embedding size of {model}")
        self._encoder = encoder
        self.model = model
        self.dimensions = dimensions

    async def embed(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]:
        # Inference is CPU-bound; a worker thread keeps the event loop responsive.
        array = await asyncio.to_thread(
            self._encoder.encode, list(texts), batch_size=self.max_batch_size
        )
        return array.tolist()


def load_sentence_transformer(model: str) -> SentenceEncoder:  # pragma: no cover
    """Import and load the model (downloads it once into the Hugging Face cache)."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ProviderConfigurationError(
            "EMBEDDING_PROVIDER=huggingface needs: pip install -r requirements-local.txt"
        ) from exc
    return SentenceTransformer(model)
