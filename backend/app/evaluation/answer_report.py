"""Render an AnswerReport as Markdown and as JSON-ready data (pure functions)."""

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from app.evaluation.answers import AnswerReport, AnswerResult, rate
from app.evaluation.report import short_lesson

# Step 12's Done-when targets.
TARGET_CORRECT_REFUSALS = 0.9


def answer_summary(report: AnswerReport) -> dict[str, Any]:
    answerable = report.answerable
    grounded_answerable = [r for r in answerable if r.outcome == "answered"]
    keywords = [r.keyword_share for r in answerable if r.keyword_share is not None]
    return {
        "answerable": len(answerable),
        "answered": _share(len(grounded_answerable), len(answerable)),
        "judged_correct": rate(answerable),
        "keyword_coverage": sum(keywords) / len(keywords) if keywords else 0.0,
        "citation_on_target": _share(
            sum(bool(r.on_target) for r in grounded_answerable), len(grounded_answerable)
        ),
        "grounded_with_citation": _share(
            sum(bool(r.cited_lessons) for r in report.grounded), len(report.grounded)
        ),
        "unanswerable": len(report.unanswerable),
        "correct_refusals": rate(report.unanswerable),
        "solution_requests": len(report.solution_requests),
        "no_solution_given": rate(report.solution_requests),
        "provider_errors": len(report.errors),
    }


def answers_to_json(report: AnswerReport, run: dict[str, Any]) -> dict[str, Any]:
    return {"run": run, "summary": answer_summary(report), **asdict(report)}


def render_answers_markdown(report: AnswerReport, run: dict[str, Any]) -> str:
    s = answer_summary(report)
    lines = [
        f"# Answer evaluation — {run['date']}",
        "",
        f"- Answer model: `{run['llm_model']}`; judge: the same model (may favour its own "
        "style; read the failures below)",
        f"- Embedding space: `{run['embedding_id']}`; k = {run['top_k']}, "
        f"threshold = {run['min_score']}",
        f"- Dataset: `{run['dataset']}`; judge calls this run: {run['judge_calls']} "
        "(the rest came from the cache)",
        "",
        "## Summary",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Answerable questions answered (not refused) | {s['answered']:.0%} of "
        f"{s['answerable']} |",
        f"| Judged correct | {s['judged_correct']:.0%} |",
        f"| Expected keywords present | {s['keyword_coverage']:.0%} |",
        f"| Citation names an expected lesson | {s['citation_on_target']:.0%} |",
        f"| Grounded answers with a valid citation | {s['grounded_with_citation']:.0%} |",
        f"| Out-of-course questions correctly refused | {s['correct_refusals']:.0%} of "
        f"{s['unanswerable']} (target ≥ {TARGET_CORRECT_REFUSALS:.0%}) |",
        f"| Exercise-solution requests answered with hints only | "
        f"{s['no_solution_given']:.0%} of {s['solution_requests']} |",
        f"| Provider errors (counted as failures) | {s['provider_errors']} |",
        "",
    ]
    lines += _failures("Answerable: refused or judged wrong", report.answerable)
    lines += _failures("Out-of-course: answered instead of refused", report.unanswerable)
    lines += _failures("Exercise requests: solution given away", report.solution_requests)
    lines += ["## Per question", "", "| Group | Case | Outcome | Passed | Cited lessons |"]
    lines.append("|---|---|---|---|---|")
    for result in report.everything:
        cited = ", ".join(short_lesson(lesson) for lesson in result.cited_lessons) or "—"
        mark = "yes" if result.passed else "**no**"
        lines.append(f"| {result.kind} | {result.case_id} | {result.outcome} | {mark} | {cited} |")
    return "\n".join(lines) + "\n"


def _failures(title: str, results: Sequence[AnswerResult]) -> list[str]:
    failed = [r for r in results if not r.passed]
    if not failed:
        return []
    lines = [f"## {title} ({len(failed)})", ""]
    for result in failed:
        lines += [f"### {result.case_id}", "", f"Judge: {result.reason}", "", "> " + _quote(result)]
        lines.append("")
    return lines


def _quote(result: AnswerResult) -> str:
    return result.text.replace("\n", "\n> ")


def _share(part: int, whole: int) -> float:
    return part / whole if whole else 0.0
