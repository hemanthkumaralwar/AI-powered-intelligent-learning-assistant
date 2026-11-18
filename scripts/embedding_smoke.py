"""Embed a few lesson snippets and a question with the configured provider, then rank them.

Usage (from the repository root):
    python scripts/embedding_smoke.py
    EMBEDDING_PROVIDER=huggingface python scripts/embedding_smoke.py

Uses real API quota for gemini/openai, so it is not part of the test suite. A working
provider ranks the `const` snippet first for the question below.
"""

import asyncio
import sys
from pathlib import Path

# Make the backend package importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import Settings  # noqa: E402
from app.embeddings.factory import build_embedding_client  # noqa: E402
from app.providers.errors import ProviderCallError  # noqa: E402

SNIPPETS = [
    "Use const for a binding that should never be reassigned after it is declared.",
    "A for loop repeats a block of code a set number of times.",
    "Arrays store an ordered list of values that you access by index.",
]
QUESTION = "How do I make a variable that cannot change?"


async def main() -> int:
    try:
        client = build_embedding_client(Settings())
        documents = await client.embed_documents(SNIPPETS)
        query = await client.embed_query(QUESTION)
    except ProviderCallError as exc:
        print(f"FAILED    {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"ok        embedding_id={client.embedding_id} vectors={len(documents)}")
    # Vectors are unit length, so the dot product is the cosine similarity.
    scores = [sum(q * d for q, d in zip(query, doc, strict=True)) for doc in documents]
    for score, snippet in sorted(zip(scores, SNIPPETS, strict=True), reverse=True):
        print(f"          {score:.3f}  {snippet[:60]}")
    best = max(range(len(scores)), key=scores.__getitem__)
    print("ranking   PASS" if best == 0 else "ranking   FAIL (expected the const snippet first)")
    return 0 if best == 0 else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
