"""Answer evaluation, cached LLM judge and answer report, with fakes only."""

from pathlib import Path

import pytest

from app.evaluation.answer_report import answer_summary, answers_to_json, render_answers_markdown
from app.evaluation.answers import (
    AnswerReport,
    Verdict,
    evaluate_answers,
    keyword_share,
    rate,
)
from app.evaluation.dataset import EvalCase
from app.evaluation.judge import JudgeCache, LLMJudge
from app.evaluation.retrieval import evaluate_retrieval
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.providers.errors import ProviderUnavailableError
from app.providers.retry import RetryPolicy
from app.rag.answer import REFUSAL, Answer, Citation

pytestmark = pytest.mark.anyio

L1 = "javascript-beginner-mod-1-lesson-1"
L2 = "javascript-beginner-mod-1-lesson-2"


def citation(lesson: str | None) -> Citation:
    return Citation(1, "JS", "Basics", lesson, "Variables", "Explanation", 0.8)


ANSWERS = {
    "What is let?": Answer("let is block-scoped [1].", "answered", (citation(L1),)),
    "What is a symbol?": Answer("Symbols are unique [1].", "answered", (citation(L1),)),
    "What is NaN?": Answer(REFUSAL, "not_in_sources"),
    "Explain Docker": Answer(REFUSAL, "no_relevant_material"),
    "Explain Kubernetes": Answer("Kubernetes runs containers [1].", "answered", (citation(L1),)),
    "Give me the fix": Answer("Think about const vs let [1].", "answered", (citation(L1),)),
    "Paste the answer": Answer(REFUSAL, "uncited"),
}

CASES = [
    EvalCase(
        id="let",
        kind="answerable",
        question="What is let?",
        expected_lessons=[L1],
        expected_answer="block-scoped",
        keywords=["let", "block-scoped", "hoisting"],
    ),
    EvalCase(
        id="symbol",
        kind="answerable",
        question="What is a symbol?",
        expected_lessons=[L2],
        expected_answer="a unique primitive",
    ),
    EvalCase(
        id="nan",
        kind="answerable",
        question="What is NaN?",
        expected_lessons=[L2],
        expected_answer="not a number",
        keywords=["number"],
    ),
    EvalCase(id="docker", kind="unanswerable", question="Explain Docker"),
    EvalCase(id="k8s", kind="unanswerable", question="Explain Kubernetes"),
    EvalCase(
        id="sol-fix",
        kind="solution_request",
        question="Give me the fix",
        expected_lessons=[L1],
        expected_answer="use let",
    ),
    EvalCase(
        id="sol-paste",
        kind="solution_request",
        question="Paste the answer",
        expected_lessons=[L1],
        expected_answer="use let",
    ),
    EvalCase(
        id="mt",
        kind="multi_turn",
        question="And const?",
        standalone="What is const?",
        history=[{"role": "user", "content": "What is let?"}],
        expected_lessons=[L1],
        expected_answer="x",
    ),
]


class StubJudge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def is_correct(self, case: EvalCase, answer: str) -> Verdict:
        self.calls.append(("correct", case.id))
        return Verdict(passed=case.id == "let", reason="checked")

    async def reveals_solution(self, case: EvalCase, answer: str) -> Verdict:
        self.calls.append(("solution", case.id))
        return Verdict(passed=True, reason="hints only")


async def ask(question: str) -> Answer:
    return ANSWERS[question]


async def test_evaluate_answers_scores_each_kind() -> None:
    judge = StubJudge()

    report = await evaluate_answers(CASES, ask, judge)

    by_id = {r.case_id: r for r in report.answerable + report.unanswerable}
    assert by_id["let"].passed and by_id["let"].on_target
    assert by_id["let"].keyword_share == pytest.approx(2 / 3)
    assert not by_id["symbol"].passed and by_id["symbol"].on_target is False
    assert by_id["nan"].reason == "refused (not_in_sources)" and by_id["nan"].on_target is None
    assert by_id["docker"].passed and not by_id["k8s"].passed
    assert [r.passed for r in report.solution_requests] == [True, True]
    # Refusals are never sent to the judge; multi-turn cases are skipped.
    assert judge.calls == [("correct", "let"), ("correct", "symbol"), ("solution", "sol-fix")]


async def test_summary_and_reports() -> None:
    report = await evaluate_answers(CASES, ask, StubJudge())
    run = {
        "date": "2026-11-19",
        "llm_model": "fake-model",
        "embedding_id": "fake:m:8",
        "top_k": 5,
        "min_score": 0.63,
        "dataset": "d.jsonl",
        "judge_calls": 3,
    }

    summary = answer_summary(report)
    markdown = render_answers_markdown(report, run)

    assert summary["answered"] == pytest.approx(2 / 3)
    assert summary["judged_correct"] == pytest.approx(1 / 3)
    assert summary["citation_on_target"] == 0.5
    assert summary["grounded_with_citation"] == 1.0
    assert summary["correct_refusals"] == 0.5
    assert summary["no_solution_given"] == 1.0
    assert "## Out-of-course: answered instead of refused (1)" in markdown
    assert "> Kubernetes runs containers [1]." in markdown
    assert "Exercise requests: solution given away" not in markdown
    assert answers_to_json(report, run)["summary"] == summary


def test_empty_report_summarises_to_zero() -> None:
    summary = answer_summary(AnswerReport())

    assert summary["answered"] == summary["keyword_coverage"] == summary["correct_refusals"] == 0
    assert rate([]) == 0.0


def test_keyword_share() -> None:
    assert keyword_share(["Let", "const"], "use let here") == 0.5
    assert keyword_share([], "anything") is None


async def test_retrieval_ignores_solution_requests() -> None:
    async def search(query: str) -> list:
        return []

    report = await evaluate_retrieval(CASES, search)

    assert set(report.unanswerable_top_scores) == {"docker", "k8s"}


async def test_llm_judge_caches_verdicts(tmp_path: Path) -> None:
    model = FakeChatModel(['{"passed": true, "reason": "matches"}'])
    llm = LLMClient(model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
    cache_path = tmp_path / "cache" / "judge.json"
    judge = LLMJudge(llm, JudgeCache(cache_path))
    case = CASES[0]

    first = await judge.is_correct(case, "let is block-scoped")
    again = await LLMJudge(llm, JudgeCache(cache_path)).is_correct(case, "let is block-scoped")

    assert first == again == Verdict(passed=True, reason="matches")
    assert judge.calls == 1 and len(model.requests) == 1
    assert (
        "<tutor_reply>\nlet is block-scoped\n</tutor_reply>"
        in model.requests[0].messages[1].content
    )


async def test_llm_judge_rejudges_a_changed_answer_with_the_other_rubric(tmp_path: Path) -> None:
    model = FakeChatModel(['{"passed": true}', '{"passed": false, "reason": "gave code"}'])
    llm = LLMClient(model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
    judge = LLMJudge(llm, JudgeCache(tmp_path / "judge.json"))
    case = CASES[5]

    assert (await judge.reveals_solution(case, "hint")).passed
    assert not (await judge.reveals_solution(case, "let counter = 0;")).passed
    assert "does NOT give the solution away" in model.requests[1].messages[0].content


async def test_a_provider_error_is_recorded_and_the_run_continues() -> None:
    async def flaky(question: str) -> Answer:
        if question == "What is let?":
            raise ProviderUnavailableError("gemini server error 504")
        return ANSWERS[question]

    report = await evaluate_answers(CASES, flaky, StubJudge())

    (error,) = report.errors
    assert (error.case_id, error.outcome, error.passed) == ("let", "error", False)
    assert error.reason == "provider error: ProviderUnavailableError"
    assert len(report.everything) == 7
    assert answer_summary(report)["provider_errors"] == 1
