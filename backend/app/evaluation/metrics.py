"""Retrieval metrics (pure functions: no I/O, fully deterministic).

- hit@k: share of questions with an acceptable lesson among the top-k chunks.
- MRR: mean of 1/rank of the first acceptable chunk (0 when none in the window).
- Threshold: the similarity score that best separates answerable from unanswerable
  questions; Step 12 uses it to decide when to say "not in the course materials".
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalResult:
    case_id: str
    module: str | None
    # Rank (1-based) of the first chunk from an acceptable lesson; None if not retrieved.
    rank: int | None
    top_score: float
    top_lessons: list[str | None]


@dataclass(frozen=True)
class Threshold:
    value: float
    accuracy: float  # share of all questions classified correctly at this threshold


def first_correct_rank(retrieved: Sequence[str | None], expected: set[str]) -> int | None:
    for position, lesson_id in enumerate(retrieved, 1):
        if lesson_id in expected:
            return position
    return None


def hit_rate(results: Sequence[RetrievalResult], k: int) -> float:
    if not results:
        return 0.0
    return sum(r.rank is not None and r.rank <= k for r in results) / len(results)


def mean_reciprocal_rank(results: Sequence[RetrievalResult]) -> float:
    if not results:
        return 0.0
    return sum(1 / r.rank for r in results if r.rank) / len(results)


def best_threshold(answerable: Sequence[float], unanswerable: Sequence[float]) -> Threshold | None:
    """Score cut-off maximising correct "answer vs refuse" decisions.

    Answerable questions should score at or above the threshold, unanswerable ones
    below it. Candidates are midpoints between neighbouring observed scores; ties keep
    the lower threshold, which refuses less and so favours answering.
    """
    if not answerable or not unanswerable:
        return None
    scores = sorted(set(answerable) | set(unanswerable))
    candidates = [(a + b) / 2 for a, b in zip(scores, scores[1:], strict=False)] or scores
    total = len(answerable) + len(unanswerable)
    best: Threshold | None = None
    for value in candidates:
        correct = sum(s >= value for s in answerable) + sum(s < value for s in unanswerable)
        if best is None or correct / total > best.accuracy:
            best = Threshold(value=value, accuracy=correct / total)
    return best


def by_module(results: Sequence[RetrievalResult], k: int) -> dict[str, float]:
    """hit@k per course module, to show which parts of the course retrieve worst."""
    modules: dict[str, list[RetrievalResult]] = {}
    for result in results:
        modules.setdefault(result.module or "unknown", []).append(result)
    return {module: hit_rate(group, k) for module, group in sorted(modules.items())}
