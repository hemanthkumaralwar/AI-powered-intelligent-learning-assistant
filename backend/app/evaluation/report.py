"""Render a RetrievalReport as Markdown and as JSON-ready data (pure functions)."""

from dataclasses import asdict
from typing import Any

from app.evaluation.retrieval import K_VALUES, GroupSummary, RetrievalReport


def to_json(report: RetrievalReport, run: dict[str, Any]) -> dict[str, Any]:
    return {"run": run, **asdict(report)}


def render_markdown(report: RetrievalReport, run: dict[str, Any]) -> str:
    lines = [
        f"# Retrieval evaluation — {run['date']}",
        "",
        f"- Embedding space: `{run['embedding_id']}`",
        f"- Index: {run['index']} ({run['chunks']} chunks)",
        f"- Dataset: `{run['dataset']}` ({run['cases']} cases)",
        "",
        "## Summary",
        "",
        "| Questions | n | " + " | ".join(f"hit@{k}" for k in K_VALUES) + " | MRR |",
        "|---|---|" + "---|" * len(K_VALUES) + "---|",
        _row("Answerable", report.answerable),
        _row("Follow-ups, as asked", report.multi_turn_raw),
        _row("Follow-ups, rewritten (gold)", report.multi_turn_rewritten),
        *_condensed_row(report),
        "",
        "**hit@k**: an acceptable lesson is among the top-k chunks. "
        "**MRR**: average of 1/rank of the first acceptable chunk.",
        "",
        *_rewrite_lines(report),
        "## Answer-or-refuse threshold (for Step 12)",
        "",
        *_threshold_lines(report),
        "",
        "## hit@5 by module (answerable)",
        "",
        "| Module | hit@5 |",
        "|---|---|",
        *(f"| {module} | {rate:.0%} |" for module, rate in report.hit_at_5_by_module.items()),
        "",
        "## Per question",
        "",
        "| Group | Case | Rank | Top score | Top lessons |",
        "|---|---|---|---|---|",
    ]
    for group, results in report.results.items():
        for r in results:
            rank = str(r.rank) if r.rank else "**miss**"
            top = ", ".join(short_lesson(lesson) for lesson in r.top_lessons)
            lines.append(f"| {group} | {r.case_id} | {rank} | {r.top_score:.3f} | {top} |")
    return "\n".join(lines) + "\n"


def _row(label: str, summary: GroupSummary) -> str:
    hits = " | ".join(f"{summary.hit_at[k]:.0%}" for k in K_VALUES)
    return f"| {label} | {summary.count} | {hits} | {summary.mrr:.3f} |"


def _condensed_row(report: RetrievalReport) -> list[str]:
    if report.multi_turn_condensed is None:
        return []
    return [_row("Follow-ups, rewritten by the app", report.multi_turn_condensed)]


def _rewrite_lines(report: RetrievalReport) -> list[str]:
    """The app's rewrites, for checking by eye that they kept the student's meaning."""
    if not report.rewrites:
        return []
    lines = ["## Follow-up rewrites (Step 13)", "", "| Case | Rewritten question |", "|---|---|"]
    lines += [f"| {case} | {text.replace('|', '/')} |" for case, text in report.rewrites.items()]
    return [*lines, ""]


def _threshold_lines(report: RetrievalReport) -> list[str]:
    if report.threshold is None:
        return ["Not enough answerable and unanswerable questions to calibrate."]
    scores = report.unanswerable_top_scores
    answerable = report.results.get("answerable", [])
    lowest_answerable = min((r.top_score for r in answerable), default=0.0)
    return [
        f"- Recommended similarity threshold: **{report.threshold.value:.3f}** "
        f"({report.threshold.accuracy:.0%} of answerable/unanswerable questions "
        "classified correctly).",
        f"- Highest top score among out-of-course questions: {max(scores.values()):.3f}; "
        f"lowest among answerable questions: {lowest_answerable:.3f}.",
        "- Below the threshold, the assistant should say the course materials do not cover it.",
    ]


def short_lesson(lesson_id: str | None) -> str:
    if lesson_id is None:
        return "(module overview)"
    return lesson_id.removeprefix("javascript-beginner-")
