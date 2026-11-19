"""Run the dataset through a search function and summarise retrieval quality.

The search function is injected, so the same evaluation runs against the live index
rebuilt from Postgres (Gemini vectors) or an in-memory index built offline (local
Hugging Face vectors) without changing this code.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field

from app.evaluation.dataset import EvalCase
from app.evaluation.metrics import (
    RetrievalResult,
    Threshold,
    best_threshold,
    by_module,
    first_correct_rank,
    hit_rate,
    mean_reciprocal_rank,
)
from app.vectorstore.index import SearchHit

type Search = Callable[[str], Awaitable[list[SearchHit]]]

K_VALUES = (1, 3, 5, 10)


@dataclass(frozen=True)
class GroupSummary:
    count: int
    hit_at: dict[int, float]
    mrr: float


@dataclass(frozen=True)
class RetrievalReport:
    answerable: GroupSummary
    multi_turn_raw: GroupSummary
    multi_turn_rewritten: GroupSummary
    hit_at_5_by_module: dict[str, float]
    threshold: Threshold | None
    unanswerable_top_scores: dict[str, float]
    results: dict[str, list[RetrievalResult]] = field(default_factory=dict)


async def evaluate_retrieval(cases: Sequence[EvalCase], search: Search) -> RetrievalReport:
    answerable: list[RetrievalResult] = []
    raw: list[RetrievalResult] = []
    rewritten: list[RetrievalResult] = []
    refused_scores: dict[str, float] = {}
    for case in cases:
        if case.kind == "answerable":
            answerable.append(await _run(case, case.question, search))
        elif case.kind == "multi_turn":
            raw.append(await _run(case, case.question, search))
            rewritten.append(await _run(case, case.standalone or case.question, search))
        elif case.kind == "unanswerable":
            hits = await search(case.question)
            refused_scores[case.id] = hits[0].score if hits else 0.0
    threshold = best_threshold([r.top_score for r in answerable], list(refused_scores.values()))
    return RetrievalReport(
        answerable=_summary(answerable),
        multi_turn_raw=_summary(raw),
        multi_turn_rewritten=_summary(rewritten),
        hit_at_5_by_module=by_module(answerable, 5),
        threshold=threshold,
        unanswerable_top_scores=refused_scores,
        results={
            "answerable": answerable,
            "multi_turn_raw": raw,
            "multi_turn_rewritten": rewritten,
        },
    )


async def _run(case: EvalCase, query: str, search: Search) -> RetrievalResult:
    hits = await search(query)
    lessons = [hit.lesson_id for hit in hits]
    return RetrievalResult(
        case_id=case.id,
        module=_module(case.expected_lessons[0]),
        rank=first_correct_rank(lessons, set(case.expected_lessons)),
        top_score=hits[0].score if hits else 0.0,
        top_lessons=lessons[:3],
    )


def _summary(results: Sequence[RetrievalResult]) -> GroupSummary:
    return GroupSummary(
        count=len(results),
        hit_at={k: hit_rate(results, k) for k in K_VALUES},
        mrr=mean_reciprocal_rank(results),
    )


def _module(lesson_id: str) -> str:
    """'javascript-beginner-mod-3-lesson-2' -> 'mod-3'."""
    parts = lesson_id.split("-")
    return "-".join(parts[-4:-2]) if len(parts) >= 4 else lesson_id
