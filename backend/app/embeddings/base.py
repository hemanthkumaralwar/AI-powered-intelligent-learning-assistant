"""The adapter contract every embedding provider implements."""

from collections.abc import Sequence
from typing import Literal, Protocol

# Gemini embeds course chunks and student questions differently for better retrieval;
# other providers ignore the distinction.
EmbeddingTask = Literal["document", "query"]


class EmbeddingModel(Protocol):
    """Adapter for one embedding backend.

    `embed` makes one call for at most `max_batch_size` texts and maps vendor errors onto
    `app.providers.errors`. Batching, retries, checks and normalisation live in
    `EmbeddingClient`.
    """

    provider: str
    model: str
    dimensions: int
    max_batch_size: int

    async def embed(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]: ...
