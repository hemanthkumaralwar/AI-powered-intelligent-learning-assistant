"""Make one real call to the configured LLM provider and report the outcome.

Usage (from the repository root, with the key in `.env`):
    python scripts/llm_smoke.py

Uses real API quota, so it is not part of the test suite. Prints only the reply and
metadata, never the API key.
"""

import asyncio
import sys
from pathlib import Path

from pydantic import BaseModel

# Make the backend package importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import Settings  # noqa: E402
from app.llm.base import ChatMessage, GenerationOptions  # noqa: E402
from app.llm.factory import build_llm_client  # noqa: E402
from app.providers.errors import ProviderCallError  # noqa: E402


class Capital(BaseModel):
    country: str
    capital: str


async def main() -> int:
    settings = Settings()
    try:
        client = build_llm_client(settings)
        options = GenerationOptions(temperature=0.0, max_output_tokens=256)

        reply = await client.chat(
            [ChatMessage(role="user", content="Reply with exactly one word: pong")], options
        )
        print(f"chat ok   provider={client.provider} model={reply.model}")
        print(f"          reply={reply.text.strip()!r} tokens={reply.output_tokens}")

        capital = await client.generate_json(
            [ChatMessage(role="user", content="What is the capital of India?")], Capital, options
        )
        print(f"json ok   {capital.model_dump()}")
    except ProviderCallError as exc:
        print(f"FAILED    {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
