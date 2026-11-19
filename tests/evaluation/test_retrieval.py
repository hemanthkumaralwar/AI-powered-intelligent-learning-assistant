"""evaluate_retrieval + report rendering with a fake search (no index, no network)."""

import pytest

from app.evaluation.dataset import EvalCase
from app.evaluation.report import render_markdown, to_json
from app.evaluation.retrieval import evaluate_retrieval
from app.vectorstore.index import SearchHit

pytestmark = pytest.mark.anyio

P = "javascript-beginner-"


def hit(lesson: str | None, score: float) -> SearchHit:
    return SearchHit(
        chunk_id=f"{lesson}-{score}",
        score=score,
        course_id="c",
        lesson_id=lesson,
        section="Explanation",
        text="t",
        metadata={},
    )


# Canned results per query text.
RESULTS = {
    "What is let?": [hit(P + "mod-1-lesson-1", 0.8), hit(P + "mod-1-lesson-2", 0.7)],
    "How does map work?": [
        hit(None, 0.75),
        hit(P + "mod-2-lesson-1", 0.7),
        hit(P + "mod-4-lesson-4", 0.65),
    ],
    "Explain Docker": [hit(P + "mod-8-lesson-1", 0.55)],
    "And const?": [hit(P + "mod-3-lesson-1", 0.6)],
    "What is const?": [hit(P + "mod-1-lesson-1", 0.78)],
}


async def fake_search(query: str) -> list[SearchHit]:
    return RESULTS.get(query, [])


CASES = [
    EvalCase(
        id="let",
        kind="answerable",
        question="What is let?",
        expected_lessons=[P + "mod-1-lesson-1"],
        expected_answer="x",
    ),
    EvalCase(
        id="map",
        kind="answerable",
        question="How does map work?",
        expected_lessons=[P + "mod-4-lesson-4"],
        expected_answer="x",
    ),
    EvalCase(
        id="nothing",
        kind="answerable",
        question="Unmatched question",
        expected_lessons=[P + "mod-5-lesson-1"],
        expected_answer="x",
    ),
    EvalCase(id="docker", kind="unanswerable", question="Explain Docker"),
    EvalCase(
        id="mt",
        kind="multi_turn",
        question="And const?",
        standalone="What is const?",
        history=[{"role": "user", "content": "What is let?"}],
        expected_lessons=[P + "mod-1-lesson-1"],
        expected_answer="x",
    ),
]


async def test_evaluation_groups_and_scores_cases() -> None:
    report = await evaluate_retrieval(CASES, fake_search)

    ranks = {r.case_id: r.rank for r in report.results["answerable"]}
    assert ranks == {"let": 1, "map": 3, "nothing": None}
    assert report.answerable.count == 3
    assert report.answerable.hit_at[1] == pytest.approx(1 / 3)
    assert report.answerable.hit_at[3] == pytest.approx(2 / 3)
    assert report.multi_turn_raw.hit_at[10] == 0.0
    assert report.multi_turn_rewritten.hit_at[1] == 1.0
    assert report.unanswerable_top_scores == {"docker": 0.55}
    assert report.hit_at_5_by_module == {"mod-1": 1.0, "mod-4": 1.0, "mod-5": 0.0}
    assert report.threshold is not None


async def test_report_renders_markdown_and_json() -> None:
    report = await evaluate_retrieval(CASES, fake_search)
    run = {
        "date": "2026-11-19",
        "embedding_id": "fake:m:8",
        "index": "test",
        "chunks": 5,
        "dataset": "d.jsonl",
        "cases": len(CASES),
    }

    markdown = render_markdown(report, run)
    data = to_json(report, run)

    assert "| Answerable | 3 |" in markdown
    assert "**miss**" in markdown
    assert "(module overview)" in markdown
    assert "Recommended similarity threshold" in markdown
    assert data["run"]["chunks"] == 5
    assert data["answerable"]["count"] == 3


async def test_threshold_section_without_unanswerable_cases() -> None:
    answerable_only = [c for c in CASES if c.kind == "answerable"]
    report = await evaluate_retrieval(answerable_only, fake_search)
    run = {"date": "d", "embedding_id": "e", "index": "i", "chunks": 0, "dataset": "x", "cases": 3}

    assert "Not enough answerable and unanswerable" in render_markdown(report, run)


async def test_app_rewrites_are_scored_and_reported() -> None:
    async def rewrite(case: EvalCase) -> str:
        return "What is const?"

    report = await evaluate_retrieval(CASES, fake_search, rewrite)
    run = {"date": "d", "embedding_id": "e", "index": "i", "chunks": 0, "dataset": "x", "cases": 5}
    markdown = render_markdown(report, run)

    assert report.rewrites == {"mt": "What is const?"}
    assert report.multi_turn_condensed is not None
    assert report.multi_turn_condensed.hit_at[1] == 1.0
    assert "| Follow-ups, rewritten by the app | 1 | 100%" in markdown
    assert "| mt | What is const? |" in markdown
    assert "multi_turn_condensed" in report.results


async def test_without_a_rewriter_there_is_no_app_row() -> None:
    report = await evaluate_retrieval(CASES, fake_search)
    run = {"date": "d", "embedding_id": "e", "index": "i", "chunks": 0, "dataset": "x", "cases": 5}

    assert report.multi_turn_condensed is None
    assert "rewritten by the app" not in render_markdown(report, run)
