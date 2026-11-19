"""ExerciseGrader with a scripted model: verdicts, and the answer-leak guard."""

import json
import uuid

import pytest

from app.core.quota import MINUTE, Quota, QuotaExceededError, QuotaRule
from app.db.repositories.exercises import ExerciseTask
from app.learning.grading import GENERIC_HINT, ExerciseGrader, leaks_reference
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.providers.errors import InvalidResponseError
from app.providers.retry import RetryPolicy

pytestmark = pytest.mark.anyio

SOLUTION = "let counter = 0;\ncounter = counter + 1;\nconsole.log(counter);"
TASK = ExerciseTask(
    id=uuid.uuid4(),
    kind="bug_hunt",
    title="Fix the counter",
    instructions="Find the bug.",
    starter_code="const counter = 0;\ncounter = counter + 1;",
    language="javascript",
    solution=SOLUTION,
    expected_output=None,
)


def grader(*replies, per_minute: int = 100) -> tuple[ExerciseGrader, FakeChatModel]:
    model = FakeChatModel([json.dumps(r) if isinstance(r, dict) else r for r in replies])
    llm = LLMClient(model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
    return ExerciseGrader(llm, Quota([QuotaRule("slow", per_minute, MINUTE)])), model


async def test_pass_with_feedback_and_the_reference_only_in_the_prompt() -> None:
    grade_it, model = grader({"passed": True, "feedback": "Right: a value that changes needs let."})

    grade = await grade_it.grade("asha", TASK, SOLUTION, "advanced")

    assert (grade.passed, grade.feedback) == (True, "Right: a value that changes needs let.")
    system, user = model.requests[0].messages
    assert "Never reveal the reference" in system.content
    assert "Explanation level: advanced." in system.content
    assert "<reference>\nlet counter = 0;" in user.content


@pytest.mark.parametrize(
    "feedback",
    [
        "Change it to: let counter = 0; and it works.",
        "Try this:\n```js\nlet x = 1\n```",
        "   ",
    ],
    ids=["quotes-solution-line", "code-block", "empty"],
)
async def test_leaky_or_empty_feedback_is_replaced(feedback: str) -> None:
    grade_it, _ = grader({"passed": False, "feedback": feedback})

    grade = await grade_it.grade("asha", TASK, "const counter = 0;")

    assert grade.feedback == GENERIC_HINT
    assert grade.passed is False


async def test_expected_output_is_the_reference_when_there_is_no_solution() -> None:
    task = TASK.__class__(**{**TASK.__dict__, "solution": None, "expected_output": "Total: 6"})
    grade_it, model = grader({"passed": True, "feedback": "Good."})

    await grade_it.grade("asha", task, "print(6)")

    assert "<reference>\nTotal: 6\n</reference>" in model.requests[0].messages[1].content


async def test_unusable_reply_is_retried_once_then_raises() -> None:
    grade_it, model = grader("nope", {"passed": False, "feedback": "Check line 1."})
    assert (await grade_it.grade("asha", TASK, "x")).feedback == "Check line 1."
    assert len(model.requests) == 2

    grade_it, _ = grader("nope", "still nope")
    with pytest.raises(InvalidResponseError):
        await grade_it.grade("asha", TASK, "x")


async def test_quota_is_checked_first() -> None:
    grade_it, model = grader({"passed": True, "feedback": "ok"}, per_minute=1)
    await grade_it.grade("asha", TASK, "x")

    with pytest.raises(QuotaExceededError):
        await grade_it.grade("asha", TASK, "x")
    assert len(model.requests) == 1


def test_leak_detection() -> None:
    assert leaks_reference("You should write   let counter = 0; there", SOLUTION)
    assert not leaks_reference("Think about let versus const.", SOLUTION)
    assert not leaks_reference("Use counter.", "x = 1")  # short reference lines do not count
    assert not leaks_reference("Any text", None)
