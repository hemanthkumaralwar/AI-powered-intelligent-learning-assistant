"""Retrieval (and answer) evaluation: runs eval/dataset.jsonl and writes reports.

Live (default): rebuild the FAISS index from DATABASE_URL (the course must already be
indexed there, e.g. Neon dev) and embed only the questions with the configured provider.
Costs one embedding per question (~90; Gemini free tier: ~1,000/day), none for documents.

    python eval/run_eval.py

Answers (Step 12) add grounded answering and an LLM judge on top of a live run, reusing
the question embeddings: up to ~76 answer calls plus one judge call per grounded answer,
paced to --llm-per-minute.
Judge verdicts are cached in eval/cache/ (gitignored), so a re-run only judges answers
that changed.

    python eval/run_eval.py --answers

Offline: chunk eval/materials/<course>.json with a chosen size and embed everything
locally with Hugging Face (needs requirements-local.txt). Costs no quota; use it to
compare chunk sizes before re-indexing anything on Gemini.

    python eval/run_eval.py --offline --max-body 1000 --overlap 150

Reports go to eval/reports/{retrieval,answers}-<date>-<label>.{md,json}.
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
from app.core.quota import Quota  # noqa: E402
from app.db.session import build_database  # noqa: E402
from app.embeddings.client import EmbeddingClient  # noqa: E402
from app.embeddings.factory import build_embedding_client  # noqa: E402
from app.evaluation.answer_report import (  # noqa: E402
    answer_summary,
    answers_to_json,
    render_answers_markdown,
)
from app.evaluation.answers import AnswerReport, evaluate_answers  # noqa: E402
from app.evaluation.dataset import load_dataset, unknown_lessons  # noqa: E402
from app.evaluation.judge import JudgeCache, LLMJudge  # noqa: E402
from app.evaluation.report import render_markdown, to_json  # noqa: E402
from app.evaluation.retrieval import RetrievalReport, evaluate_retrieval  # noqa: E402
from app.indexing.service import IndexingService  # noqa: E402
from app.ingestion.chunking import ChunkingConfig, chunk_course  # noqa: E402
from app.ingestion.course_json import parse_course  # noqa: E402
from app.llm.base import ChatModel, CompletionRequest, LLMResponse  # noqa: E402
from app.llm.client import LLMClient  # noqa: E402
from app.llm.factory import build_chat_model  # noqa: E402
from app.providers.rate_limit import RateLimiter  # noqa: E402
from app.providers.retry import RetryPolicy  # noqa: E402
from app.rag.answer import AnswerService  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402
from app.vectorstore.index import IndexEntry, VectorIndex  # noqa: E402

COURSE_FILE = ROOT / "eval" / "materials" / "javascript-beginner.json"
JUDGE_CACHE = ROOT / "eval" / "cache" / "judge.json"
COURSE_ID = "javascript-beginner-v1"
TOP_K = 10


class PacedChatModel:
    """Spaces out LLM calls (answers and judge alike) to stay inside the free tier."""

    def __init__(self, inner: ChatModel, limiter: RateLimiter) -> None:
        self._inner = inner
        self._limiter = limiter
        self.provider = inner.provider
        self.model = inner.model

    async def complete(self, request: CompletionRequest) -> LLMResponse:
        await self._limiter.acquire()
        return await self._inner.complete(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


class CachedSearch:
    """Embeds each distinct question once, so the retrieval and answer phases share one
    embedding per question (the free tier counts every text)."""

    def __init__(self, embedder: EmbeddingClient, index: VectorIndex) -> None:
        self._embedder = embedder
        self._index = index
        self._vectors: dict[str, list[float]] = {}

    async def __call__(self, query: str, k: int, course_id: str | None = None) -> list:
        if query not in self._vectors:
            self._vectors[query] = await self._embedder.embed_query(query)
        return self._index.search(self._vectors[query], k, course_id)


async def live(
    settings: Settings, dataset: list, llm_per_minute: int | None
) -> tuple[RetrievalReport, dict, AnswerReport | None]:
    database = build_database(settings)
    embedder = build_embedding_client(settings)
    service = IndexingService(database, embedder)
    search = CachedSearch(embedder, service.index)
    try:
        chunks = await service.rebuild_index()
        report = await evaluate_retrieval(dataset, lambda q: search(q, TOP_K, COURSE_ID))
        run = {
            "index": "live (rebuilt from the database)",
            "chunks": chunks,
            "embedding_id": service.embedding_id,
        }
        answers = None
        if llm_per_minute is not None:
            answers = await evaluate_live_answers(settings, dataset, search, llm_per_minute, run)
        return report, run, answers
    finally:
        await service.aclose()
        await database.dispose()


async def evaluate_live_answers(
    settings: Settings, dataset: list, search: CachedSearch, per_minute: int, run: dict
) -> AnswerReport:
    model = PacedChatModel(build_chat_model(settings), RateLimiter(per_minute))
    llm = LLMClient(
        model,
        timeout_seconds=settings.llm_timeout_seconds,
        retry_policy=RetryPolicy(max_attempts=settings.llm_max_attempts),
    )
    retriever = Retriever(search, settings.rag_top_k, settings.rag_min_score)
    # No per-user quota: this script paces its own calls.
    answers = AnswerService(retriever, llm, Quota([]))
    judge = LLMJudge(llm, JudgeCache(JUDGE_CACHE))
    try:
        report = await evaluate_answers(dataset, lambda q: answers.ask("eval", q, COURSE_ID), judge)
    finally:
        await llm.aclose()
    run |= {
        "llm_model": llm.model,
        "top_k": settings.rag_top_k,
        "min_score": settings.rag_min_score,
        "judge_calls": judge.calls,
    }
    return report


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


def write_reports(
    name: str, run: dict, retrieval: RetrievalReport, answers: AnswerReport | None
) -> None:
    out = ROOT / "eval" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"retrieval-{name}.md").write_text(render_markdown(retrieval, run), encoding="utf-8")
    (out / f"retrieval-{name}.json").write_text(
        json.dumps(to_json(retrieval, run), indent=2), encoding="utf-8"
    )
    summary = retrieval.answerable
    print(
        f"{name}: answerable hit@1 {summary.hit_at[1]:.0%} hit@5 {summary.hit_at[5]:.0%} "
        f"MRR {summary.mrr:.3f} | eval/reports/retrieval-{name}.md"
    )
    if answers is None:
        return
    (out / f"answers-{name}.md").write_text(render_answers_markdown(answers, run), encoding="utf-8")
    (out / f"answers-{name}.json").write_text(
        json.dumps(answers_to_json(answers, run), indent=2), encoding="utf-8"
    )
    s = answer_summary(answers)
    print(
        f"answers: correct {s['judged_correct']:.0%}, refusals {s['correct_refusals']:.0%}, "
        f"cited {s['grounded_with_citation']:.0%}, hints-only {s['no_solution_given']:.0%} "
        f"| eval/reports/answers-{name}.md"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=ROOT / "eval" / "dataset.jsonl")
    parser.add_argument("--offline", action="store_true", help="local Hugging Face index")
    parser.add_argument("--max-body", type=int, default=ChunkingConfig().max_body_chars)
    parser.add_argument("--overlap", type=int, default=ChunkingConfig().overlap_chars)
    parser.add_argument("--answers", action="store_true", help="also evaluate answers (live)")
    parser.add_argument("--llm-per-minute", type=int, default=8, help="pace for LLM calls")
    args = parser.parse_args()
    if args.offline and args.answers:
        parser.error("--answers needs the live index (its threshold is for Gemini embeddings)")

    dataset = load_dataset(args.dataset)
    course = json.loads(COURSE_FILE.read_text(encoding="utf-8"))["course"]
    unknown = unknown_lessons(
        dataset, {lesson["lessonId"] for m in course["modules"] for lesson in m["lessons"]}
    )
    if unknown:
        print(f"dataset names lessons that do not exist: {unknown}", file=sys.stderr)
        return 1

    answers = None
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
        pace = args.llm_per_minute if args.answers else None
        report, run, answers = asyncio.run(
            live(Settings(), dataset, pace), loop_factory=asyncio.SelectorEventLoop
        )
        label = run["embedding_id"].split(":")[0]

    today = datetime.date.today().isoformat()
    run |= {"date": today, "dataset": args.dataset.name, "cases": len(dataset)}
    write_reports(f"{today}-{label}", run, report, answers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
