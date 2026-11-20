"""Production evaluation: a small, quota-friendly subset of the dataset asked through the
live API, scored only from what the API returns (no LLM judge; answer correctness is
measured offline in Step 12)."""

import math
import statistics
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.evaluation.dataset import CaseKind, EvalCase

# 10 + 4 + 3 + 3 cases = 23 questions (each follow-up needs its opening question).
SUBSET: dict[CaseKind, int] = {
    "answerable": 10,
    "unanswerable": 4,
    "multi_turn": 3,
    "solution_request": 3,
}
CODE_FENCE = "```"


@dataclass(frozen=True)
class Reply:
    """One /chat/ask call: the HTTP status, how long it took, and the JSON body if 200."""

    status: int
    seconds: float
    body: dict[str, Any] | None = None


# ask(question, session_id) -> Reply
type Ask = Callable[[str, str | None], Awaitable[Reply]]


@dataclass(frozen=True)
class LiveResult:
    case_id: str
    kind: CaseKind
    passed: bool
    note: str
    seconds: float
    status: int


@dataclass(frozen=True)
class LiveReport:
    results: list[LiveResult]
    run: dict[str, Any] = field(default_factory=dict)


def pick_cases(cases: Sequence[EvalCase], subset: dict[CaseKind, int] = SUBSET) -> list[EvalCase]:
    """Evenly spaced cases of each kind (deterministic, spread across the course)."""
    picked: list[EvalCase] = []
    for kind, wanted in subset.items():
        of_kind = [case for case in cases if case.kind == kind]
        step = max(1, len(of_kind) // wanted) if wanted else 1
        picked.extend(of_kind[::step][:wanted])
    return picked


def score(case: EvalCase, reply: Reply) -> tuple[bool, str]:
    """Pass or fail from the response alone, with a short reason."""
    if reply.body is None:
        return False, f"HTTP {reply.status}"
    grounded = bool(reply.body.get("grounded"))
    if case.kind == "unanswerable":
        return (not grounded, "refused" if not grounded else "answered an out-of-course question")
    if case.kind == "solution_request":
        if CODE_FENCE in str(reply.body.get("answer", "")):
            return False, "answer contains a code block"
        return True, "no solution code"
    if not grounded:
        return False, "refused a covered question"
    cited = {c.get("lesson_id") for c in reply.body.get("citations", [])}
    if cited & set(case.expected_lessons):
        return True, "cited an expected lesson"
    return False, "no expected lesson cited" if cited else "no citations"


async def evaluate(cases: Sequence[EvalCase], ask: Ask) -> list[LiveResult]:
    """Ask each case; a follow-up first opens its chat with the case's opening question."""
    results: list[LiveResult] = []
    for case in cases:
        session_id = None
        if case.kind == "multi_turn":
            opening = await ask(case.history[0].content, None)
            if opening.body is None:
                results.append(_result(case, opening, False, f"opening HTTP {opening.status}"))
                continue
            session_id = str(opening.body["session_id"])
        reply = await ask(case.question, session_id)
        results.append(_result(case, reply, *score(case, reply)))
    return results


def _result(case: EvalCase, reply: Reply, passed: bool, note: str) -> LiveResult:
    return LiveResult(case.id, case.kind, passed, note, reply.seconds, reply.status)


def summary(results: Sequence[LiveResult]) -> dict[str, Any]:
    by_kind = {}
    for kind in SUBSET:
        of_kind = [r for r in results if r.kind == kind]
        if of_kind:
            by_kind[kind] = {"passed": sum(r.passed for r in of_kind), "total": len(of_kind)}
    answered = sorted(r.seconds for r in results if r.status == 200)
    return {
        "passed": sum(r.passed for r in results),
        "total": len(results),
        "errors": sum(r.status != 200 for r in results),
        "by_kind": by_kind,
        "seconds": _latency(answered),
    }


def _latency(seconds: Sequence[float]) -> dict[str, float] | None:
    if not seconds:
        return None
    p95 = seconds[min(len(seconds) - 1, math.ceil(0.95 * len(seconds)) - 1)]
    return {"median": statistics.median(seconds), "p95": p95, "max": seconds[-1]}


LABELS: dict[CaseKind, str] = {
    "answerable": "Covered questions: grounded, citing an expected lesson",
    "unanswerable": "Out-of-course questions refused",
    "multi_turn": "Follow-ups in a chat: grounded, citing an expected lesson",
    "solution_request": "Exercise-solution requests answered without code",
}


def render_markdown(report: LiveReport) -> str:
    stats = summary(report.results)
    run = report.run
    lines = [
        f"# Production evaluation ({run.get('date', '')})",
        "",
        f"Live API `{run.get('api', '')}`, course `{run.get('course_id', '')}`. "
        "Scored from API responses only (no LLM judge); "
        "answer correctness is measured offline (Step 12 reports).",
        "",
        "| Check | Result |",
        "|---|---|",
        f"| Cold start (`/health` after idle) | {_seconds(run.get('health_seconds'))} |",
    ]
    for kind, counts in stats["by_kind"].items():
        lines.append(f"| {LABELS[kind]} | {counts['passed']}/{counts['total']} |")
    lines.append(f"| Errors (non-200) | {stats['errors']} of {stats['total']} |")
    latency = stats["seconds"]
    if latency:
        lines.append(
            f"| Answer time (warm) | median {_seconds(latency['median'])}, "
            f"p95 {_seconds(latency['p95'])}, max {_seconds(latency['max'])} |"
        )
    lines += ["", f"**Total: {stats['passed']}/{stats['total']} passed.**", ""]
    failures = [r for r in report.results if not r.passed]
    if failures:
        lines += ["## Failures", ""]
        lines += [f"- `{r.case_id}` ({r.kind}): {r.note}" for r in failures]
        lines.append("")
    return "\n".join(lines)


def _seconds(value: float | None) -> str:
    return "not measured" if value is None else f"{value:.1f} s"
