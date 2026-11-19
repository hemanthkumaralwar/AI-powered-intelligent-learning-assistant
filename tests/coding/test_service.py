"""CodingService with a scripted fake model and a fake search (no network)."""

import json
import logging

import pytest

from app.coding.service import MAX_TEXT_CHARS, CodingService
from app.core.quota import MINUTE, Quota, QuotaExceededError, QuotaRule
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.providers.errors import InvalidResponseError
from app.providers.retry import RetryPolicy
from app.rag.retriever import Retriever
from app.vectorstore.index import SearchHit

pytestmark = pytest.mark.anyio

CODE = "const counter = 0;\ncounter = counter + 1;\nconsole.log(counter);"


def hit(lesson: str | None, score: float = 0.8) -> SearchHit:
    return SearchHit(
        chunk_id=f"{lesson}-{score}",
        score=score,
        course_id="js",
        lesson_id=lesson,
        section="Explanation",
        text="t",
        metadata={"course_title": "JS", "module_title": "Basics", "lesson_title": "Variables"},
    )


class Search:
    def __init__(self, hits: list[SearchHit]) -> None:
        self.hits = hits
        self.queries: list[str] = []

    async def __call__(self, query: str, k: int, course_id: str | None) -> list[SearchHit]:
        self.queries.append(query)
        return self.hits


def build(*replies, hits=(), per_minute: int = 100) -> tuple[CodingService, FakeChatModel, Search]:
    model = FakeChatModel([json.dumps(r) if isinstance(r, dict) else r for r in replies])
    llm = LLMClient(model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
    search = Search(list(hits))
    quota = Quota([QuotaRule("slow down", per_minute, MINUTE)])
    return CodingService(llm, quota, Retriever(search, 5, 0.63)), model, search


DEBUG_REPLY = {
    "summary": "counter is const.",
    "issues": [
        {"line": 2, "problem": "Reassigns a const.", "fix_hint": "Use let."},
        {"line": 99, "problem": "Out of range.", "fix_hint": "x"},
        {"line": 1, "problem": "Declared with const.", "fix_hint": "Use let."},
    ],
    "corrected_code": "let counter = 0;\ncounter = counter + 1;\nconsole.log(counter);",
    "concepts": ["let vs const", "  ", "reassignment"],
}


async def test_debug_checks_lines_and_finds_related_lessons() -> None:
    hits = [hit("l1"), hit("l1", 0.75), hit(None), hit("l2", 0.7), hit("l3", 0.5)]
    service, model, search = build(DEBUG_REPLY, hits=hits)

    result = await service.debug("asha", "javascript", CODE, "outcome: runtime_error", [])

    assert [i.line for i in result.output.issues] == [1, 2]
    assert result.output.corrected_code.startswith("let counter")
    assert result.exercise is False
    assert [lesson.lesson_id for lesson in result.related_lessons] == ["l1", "l2"]
    assert result.related_lessons[0].link == "/lessons/l1"
    assert search.queries == ["JavaScript: let vs const, reassignment"]
    (request,) = model.requests
    assert request.json_schema is not None
    assert "<run_output>\noutcome: runtime_error" in request.messages[1].content


async def test_course_exercise_gets_hints_only_even_if_the_model_answers() -> None:
    service, model, _ = build(DEBUG_REPLY)

    result = await service.debug("asha", "javascript", CODE, None, [CODE])

    assert result.exercise is True
    assert result.output.corrected_code is None
    assert "never give the solution" in model.requests[0].messages[0].content


async def test_explain_drops_out_of_range_lines_and_cuts_long_text() -> None:
    reply = {
        "summary": "x" * (MAX_TEXT_CHARS + 50),
        "lines": [
            {"line": 3, "explanation": "Logs it."},
            {"line": 0, "explanation": "?"},
            {"line": 1, "explanation": "Declares it."},
        ],
        "concepts": [],
    }
    service, _, search = build(reply)

    result = await service.explain("asha", "javascript", CODE)

    assert [n.line for n in result.output.lines] == [1, 3]
    assert len(result.output.summary) == MAX_TEXT_CHARS and result.output.summary.endswith("…")
    assert result.related_lessons == [] and search.queries == []  # no concepts, no search


async def test_example_and_practice() -> None:
    example = {"title": "Rest", "code": "f(...a)", "explanation": "Collects.", "concepts": ["rest"]}
    practice = {
        "questions": [
            {"question": f"Q{n}", "hints": ["a", "b", "c", "d"], "expected_output": None}
            for n in range(7)
        ],
        "concepts": ["loops"],
    }
    service, _, _ = build(example, practice)

    shown = await service.example("asha", "python", "rest parameters")
    drills = await service.practice("asha", "python", "loops")

    assert (shown.output.title, shown.output.code) == ("Rest", "f(...a)")
    assert len(drills.output.questions) == 5
    assert drills.output.questions[0].hints == ["a", "b", "c"]


async def test_invalid_json_is_retried_once() -> None:
    service, model, _ = build("not json", DEBUG_REPLY)

    result = await service.debug("asha", "javascript", CODE, None, [])

    assert len(model.requests) == 2 and result.output.issues


async def test_invalid_json_twice_raises() -> None:
    service, _, _ = build("not json", '{"summary": 1}')

    with pytest.raises(InvalidResponseError):
        await service.explain("asha", "javascript", CODE)


async def test_quota_is_checked_before_the_model() -> None:
    service, model, _ = build(DEBUG_REPLY, per_minute=1)
    await service.debug("asha", "javascript", CODE, None, [])

    with pytest.raises(QuotaExceededError):
        await service.example("asha", "javascript", "loops")
    assert len(model.requests) == 1


async def test_logs_metadata_only(caplog: pytest.LogCaptureFixture) -> None:
    service, _, _ = build(DEBUG_REPLY)

    with caplog.at_level(logging.INFO, logger="app.coding.service"):
        await service.debug("asha", "javascript", "// secret student code\n" + CODE, None, [])

    assert "kind=DebugOutput language=javascript" in caplog.text
    assert "secret" not in caplog.text and "counter" not in caplog.text
