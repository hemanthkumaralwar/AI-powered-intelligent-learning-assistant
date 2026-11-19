"""Deterministic offline `EmbeddingModel` for tests and keyless development.

Vectors come from a SHA-256 hash of the text: the same text always gives the same vector,
but similar texts do NOT give similar vectors. Fine for plumbing tests, useless for
judging retrieval quality.
"""

import hashlib
from collections.abc import Sequence

from app.embeddings.base import EmbeddingTask


class FakeEmbeddingModel:
    provider = "fake"
    model = "fake-embedding"
    max_batch_size = 100

    def __init__(self, dimensions: int = 8) -> None:
        self.dimensions = dimensions
        self.calls: list[tuple[list[str], EmbeddingTask]] = []
        self.closed = False

    async def embed(self, texts: Sequence[str], task: EmbeddingTask) -> list[list[float]]:
        self.calls.append((list(texts), task))
        return [fake_vector(text, self.dimensions) for text in texts]

    async def aclose(self) -> None:
        self.closed = True


def fake_vector(text: str, dimensions: int) -> list[float]:
    """Map each component to [-1, 1] from 4 bytes of sha256(index:text)."""
    vector = []
    for index in range(dimensions):
        digest = hashlib.sha256(f"{index}:{text}".encode()).digest()
        vector.append(int.from_bytes(digest[:4], "big") / 2**31 - 1.0)
    return vector
