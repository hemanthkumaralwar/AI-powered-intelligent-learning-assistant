import pytest

from app.evaluation.metrics import (
    RetrievalResult,
    best_threshold,
    by_module,
    first_correct_rank,
    hit_rate,
    mean_reciprocal_rank,
)


def result(rank: int | None, module: str = "mod-1", score: float = 0.5) -> RetrievalResult:
    return RetrievalResult(case_id="c", module=module, rank=rank, top_score=score, top_lessons=[])


def test_first_correct_rank() -> None:
    assert first_correct_rank(["a", None, "b", "c"], {"b", "c"}) == 3
    assert first_correct_rank(["a"], {"z"}) is None
    assert first_correct_rank([], {"z"}) is None


def test_hit_rate_and_mrr() -> None:
    results = [result(1), result(3), result(None), result(6)]

    assert hit_rate(results, 1) == 0.25
    assert hit_rate(results, 5) == 0.5
    assert hit_rate(results, 10) == 0.75
    assert mean_reciprocal_rank(results) == pytest.approx((1 + 1 / 3 + 1 / 6) / 4)


def test_empty_results_score_zero() -> None:
    assert hit_rate([], 5) == 0.0
    assert mean_reciprocal_rank([]) == 0.0


def test_threshold_separates_clean_groups() -> None:
    threshold = best_threshold([0.8, 0.75, 0.7], [0.5, 0.55])

    assert threshold is not None
    assert 0.55 < threshold.value < 0.7
    assert threshold.accuracy == 1.0


def test_threshold_with_overlap_maximises_accuracy() -> None:
    threshold = best_threshold([0.8, 0.6, 0.55], [0.58, 0.4])

    assert threshold is not None
    assert threshold.accuracy == pytest.approx(4 / 5)


def test_threshold_needs_both_groups() -> None:
    assert best_threshold([0.8], []) is None
    assert best_threshold([], [0.3]) is None


def test_threshold_with_a_single_shared_score() -> None:
    threshold = best_threshold([0.6], [0.6])

    assert threshold is not None and threshold.value == 0.6


def test_by_module() -> None:
    results = [result(1, "mod-1"), result(None, "mod-1"), result(2, "mod-2"), result(1, None)]

    assert by_module(results, 5) == {"mod-1": 0.5, "mod-2": 1.0, "unknown": 1.0}
