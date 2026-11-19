"""Retrieval evaluation: runs eval/dataset.jsonl against an index and writes a report.

Live (default): rebuild the FAISS index from DATABASE_URL (the course must already be
indexed there, e.g. Neon dev) and embed only the questions with the configured provider.
Costs ~86 embedding requests (Gemini free tier: ~1,000/day), no document embeddings.

    python eval/run_eval.py

Offline: chunk eval/materials/<course>.json with a chosen size and embed everything
locally with Hugging Face (needs requirements-local.txt). Costs no quota; use it to
compare chunk sizes before re-indexing anything on Gemini.

    python eval/run_eval.py --offline --max-body 1000 --overlap 150

Reports go to eval/reports/retrieval-<date>-<label>.{md,json}.
"""

import argparse
import asyncio
import datetime
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.db.session import build_database  # noqa: E402
from app.embeddings.client import EmbeddingClient  # noqa: E402
from app.embeddings.factory import build_embedding_client  # noqa: E402
from app.evaluation.dataset import load_dataset, unknown_lessons  # noqa: E402
from app.evaluation.report import render_markdown, to_json  # noqa: E402
from app.evaluation.retrieval import RetrievalReport, evaluate_retrieval  # noqa: E402
from app.indexing.service import IndexingService  # noqa: E402
from app.ingestion.chunking import ChunkingConfig, chunk_course  # noqa: E402
from app.ingestion.course_json import parse_course  # noqa: E402
from app.vectorstore.index import IndexEntry, VectorIndex  # noqa: E402

COURSE_FILE = ROOT / "eval" / "materials" / "javascript-beginner.json"
COURSE_ID = "javascript-beginner-v1"
TOP_K = 10


async def live(settings: Settings, dataset: list) -> tuple[RetrievalReport, dict]:
    database = build_database(settings)
    service = IndexingService(database, build_embedding_client(settings))
    try:
        chunks = await service.rebuild_index()
        report = await evaluate_retrieval(
            dataset, lambda q: service.search(q, TOP_K, course_id=COURSE_ID)
        )
        return report, {
            "index": "live (rebuilt from the database)",
            "chunks": chunks,
            "embedding_id": service._embedder.embedding_id,
        }
    finally:
        await service.aclose()
        await database.dispose()


async def offline(settings: Settings, dataset: list, config: ChunkingConfig) -> tuple:
    embedder: EmbeddingClient = build_embedding_client(settings)
    try:
        course = parse_course(COURSE_FILE.read_bytes(), "javascript")
        document_id = uuid.UUID(int=0)
        chunks = chunk_course(course, document_id, config)
        vectors = await embedder.embed_documents([c.text for c in chunks])
        index = VectorIndex(embedder.dimensions)
        index.add(
            IndexEntry(c.id, document_id, course.id, c.lesson_id, c.section, c.text, v, c.metadata)
            for c, v in zip(chunks, vectors, strict=True)
        )

        async def search(query: str):
            return index.search(await embedder.embed_query(query), TOP_K, COURSE_ID)

        report = await evaluate_retrieval(dataset, search)
        label = f"offline, body {config.max_body_chars} / overlap {config.overlap_chars}"
        return report, {
            "index": label,
            "chunks": len(chunks),
            "embedding_id": embedder.embedding_id,
        }
    finally:
        await embedder.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=ROOT / "eval" / "dataset.jsonl")
    parser.add_argument("--offline", action="store_true", help="local Hugging Face index")
    parser.add_argument("--max-body", type=int, default=ChunkingConfig().max_body_chars)
    parser.add_argument("--overlap", type=int, default=ChunkingConfig().overlap_chars)
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    course = json.loads(COURSE_FILE.read_text(encoding="utf-8"))["course"]
    unknown = unknown_lessons(
        dataset, {lesson["lessonId"] for m in course["modules"] for lesson in m["lessons"]}
    )
    if unknown:
        print(f"dataset names lessons that do not exist: {unknown}", file=sys.stderr)
        return 1

    if args.offline:
        settings = Settings(
            embedding_provider="huggingface",
            embedding_batch_size=16,
            embedding_timeout_seconds=120,
            embedding_document_texts_per_minute=100_000,
            embedding_query_texts_per_minute=100_000,
        )
        config = ChunkingConfig(args.max_body, args.overlap)
        report, run = asyncio.run(
            offline(settings, dataset, config), loop_factory=asyncio.SelectorEventLoop
        )
        label = f"hf-{args.max_body}"
    else:
        report, run = asyncio.run(live(Settings(), dataset), loop_factory=asyncio.SelectorEventLoop)
        label = run["embedding_id"].split(":")[0]

    today = datetime.date.today().isoformat()
    run |= {"date": today, "dataset": args.dataset.name, "cases": len(dataset)}
    out = ROOT / "eval" / "reports" / f"retrieval-{today}-{label}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".md").write_text(render_markdown(report, run), encoding="utf-8")
    out.with_suffix(".json").write_text(
        json.dumps(to_json(report, run), indent=2), encoding="utf-8"
    )
    summary = report.answerable
    print(
        f"{label}: answerable hit@1 {summary.hit_at[1]:.0%} hit@5 {summary.hit_at[5]:.0%} "
        f"MRR {summary.mrr:.3f} | report: {out.with_suffix('.md').relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
