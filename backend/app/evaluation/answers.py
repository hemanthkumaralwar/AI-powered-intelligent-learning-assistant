"""Answer quality (Step 12): accuracy, correct refusals, citations, hints-not-solutions.

Multi-turn cases are skipped here: answering follow-ups needs Step 13's rewriting.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol

from pydantic import BaseModel, Field

from app.evaluation.dataset import EvalCase
from app.providers.errors import ProviderCallError
from app.rag.answer import Answer

type Ask = Callable[[str], Awaitable[Answer]]


class Verdict(BaseModel):
    passed: bool
    reason: str = Field(default="", max_length=500)


class Judge(Protocol):
    async def is_correct(self, case: EvalCase, answer: str) -> Verdict:
        """Does `answer` agree with the case's expected answer?"""

    async def reveals_solution(self, case: EvalCase, answer: str) -> Verdict:
        """`passed` is True when `answer` does NOT give away the exercise's solution."""


@dataclass(frozen=True)
class AnswerResult:
    case_id: str
    kind: str
    outcome: str
    text: str
    cited_lessons: list[str | None]
    # Answerable: share of expected keywords present. Others: None.
    keyword_share: float | None = None
    # Answerable: judged correct. Unanswerable: refused. Solution request: no solution.
    passed: bool = False
    reason: str = ""
    # Grounded answerable only: a citation names one of the expected lessons.
    on_target: bool | None = None


@dataclass
class AnswerReport:
    answerable: list[AnswerResult] = field(default_factory=list)
    unanswerable: list[AnswerResult] = field(default_factory=list)
    solution_requests: list[AnswerResult] = field(default_factory=list)

    @property
    def grounded(self) -> list[AnswerResult]:
        return [r for r in self.everything if r.outcome == "answered"]

    @property
    def errors(self) -> list[AnswerResult]:
        return [r for r in self.everything if r.outcome == "error"]

    @property
    def everything(self) -> list[AnswerResult]:
        return self.answerable + self.unanswerable + self.solution_requests


async def evaluate_answers(cases: Sequence[EvalCase], ask: Ask, judge: Judge) -> AnswerReport:
    """Score every answerable, unanswerable and solution-request case.

    A provider failure on one case is recorded as a failed `error` result and the run
    goes on: one bad call should not discard an hour of free-tier quota."""
    report = AnswerReport()
    groups = {
        "answerable": (report.answerable, _answerable),
        "unanswerable": (report.unanswerable, _unanswerable),
        "solution_request": (report.solution_requests, _solution_request),
    }
    for case in cases:
        if case.kind not in groups:
            continue
        results, score = groups[case.kind]
        try:
            results.append(await score(case, await ask(case.question), judge))
        except ProviderCallError as exc:
            reason = f"provider error: {type(exc).__name__}"
            results.append(AnswerResult(case.id, case.kind, "error", "", [], reason=reason))
    return report


async def _answerable(case: EvalCase, answer: Answer, judge: Judge) -> AnswerResult:
    if not answer.grounded:
        verdict = Verdict(passed=False, reason=f"refused ({answer.outcome})")
    else:
        verdict = await judge.is_correct(case, answer.text)
    result = _result(case, answer, verdict, keyword_share(case.keywords, answer.text))
    if answer.grounded:
        cited = {c.lesson_id for c in answer.citations}
        result = replace(result, on_target=bool(cited & set(case.expected_lessons)))
    return result


async def _unanswerable(case: EvalCase, answer: Answer, judge: Judge) -> AnswerResult:
    verdict = Verdict(passed=not answer.grounded, reason=answer.outcome)
    return _result(case, answer, verdict)


async def _solution_request(case: EvalCase, answer: Answer, judge: Judge) -> AnswerResult:
    if not answer.grounded:
        verdict = Verdict(passed=True, reason=f"refused ({answer.outcome})")
    else:
        verdict = await judge.reveals_solution(case, answer.text)
    return _result(case, answer, verdict)


def _result(
    case: EvalCase, answer: Answer, verdict: Verdict, keywords: float | None = None
) -> AnswerResult:
    return AnswerResult(
        case_id=case.id,
        kind=case.kind,
        outcome=answer.outcome,
        text=answer.text,
        cited_lessons=[c.lesson_id for c in answer.citations],
        keyword_share=keywords,
        passed=verdict.passed,
        reason=verdict.reason,
    )


def keyword_share(keywords: Sequence[str], text: str) -> float | None:
    """Share of `keywords` found in `text`, ignoring case; None when there are none."""
    if not keywords:
        return None
    lowered = text.lower()
    return sum(k.lower() in lowered for k in keywords) / len(keywords)


def rate(results: Sequence[AnswerResult]) -> float:
    return sum(r.passed for r in results) / len(results) if results else 0.0
