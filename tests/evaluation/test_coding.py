"""Coding evaluation scoring and report, plus the paced LLM used by evaluation scripts."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.coding.schemas import DebugOutput, Issue
from app.coding.service import CodingResult
from app.core.config import Settings
from app.evaluation.coding import (
    CodeCase,
    coding_summary,
    evaluate_debug,
    identified,
    render_coding_markdown,
)
from app.evaluation.dataset import load_cases
from app.evaluation.pacing import PacedChatModel, paced_llm
from app.llm.base import ChatMessage, CompletionRequest, GenerationOptions
from app.llm.fake import FakeChatModel
from app.providers.errors import ProviderUnavailableError

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]


def case(**overrides) -> CodeCase:
    fields = {
        "id": "py-range",
        "language": "python",
        "source": "handwritten",
        "code": "s = 0\nfor i in range(1, n):\n    s += i",
        "bug_line": 2,
        "keywords": ["range", "off-by-one"],
    }
    return CodeCase.model_validate(fields | overrides)


def output(*issues: tuple[int, str]) -> DebugOutput:
    return DebugOutput(
        summary="s",
        issues=[Issue(line=line, problem=text, fix_hint="") for line, text in issues],
        corrected_code=None,
        concepts=[],
    )


def test_the_real_code_cases_are_valid() -> None:
    cases = load_cases(ROOT / "eval" / "code_cases.jsonl", CodeCase)

    assert len(cases) == 18
    for language in ("javascript", "python", "c", "cpp", "java", "sql"):
        assert sum(c.language == language for c in cases) == 3
    assert {c.source for c in cases if c.language == "javascript"} == {"course"}


def test_bug_line_must_exist() -> None:
    with pytest.raises(ValidationError, match="past the end"):
        case(bug_line=9)


@pytest.mark.parametrize(
    ("issues", "expected"),
    [
        ([(2, "The RANGE stops early")], True),
        ([(3, "Off-by-one error")], True),
        ([(4, "range stops early")], False),
        ([(2, "Missing colon")], False),
        ([], False),
    ],
    ids=["exact-line", "next-line", "too-far", "no-keyword", "no-issues"],
)
def test_identified(issues: list, expected: bool) -> None:
    assert identified(case(), output(*issues)) is expected


async def test_evaluate_debug_records_failures_and_renders() -> None:
    cases = [case(), case(id="py-other"), case(id="py-down", language="python")]

    async def debug(c: CodeCase) -> CodingResult[DebugOutput]:
        if c.id == "py-down":
            raise ProviderUnavailableError("504")
        found = output((2, "range is off-by-one")) if c.id == "py-range" else output()
        return CodingResult(found, exercise=c.id == "py-range")

    results = await evaluate_debug(cases, debug)
    summary = coding_summary(results)
    markdown = render_coding_markdown(results, {"date": "d", "llm_model": "m", "dataset": "x"})

    assert [r.identified for r in results] == [True, False, False]
    assert results[2].valid_json is False and "ProviderUnavailableError" in results[2].reason
    assert summary["identified"] == pytest.approx(1 / 3)
    assert summary["valid_json"] == pytest.approx(2 / 3)
    assert summary["by_language"] == {"python": pytest.approx(1 / 3)}
    assert "| py-range | yes | 2 | yes |" in markdown
    assert "| py-other | **no** | — |" in markdown


def test_empty_summary() -> None:
    assert coding_summary([])["identified"] == 0.0


class Limiter:
    def __init__(self) -> None:
        self.calls = 0

    async def acquire(self) -> None:
        self.calls += 1


async def test_paced_model_waits_for_the_limiter_and_closes_the_inner_model() -> None:
    inner = FakeChatModel(["ok"])
    limiter = Limiter()
    paced = PacedChatModel(inner, limiter)  # type: ignore[arg-type]
    request = CompletionRequest(
        messages=(ChatMessage(role="user", content="hi"),), options=GenerationOptions()
    )

    assert (await paced.complete(request)).text == "ok"
    await paced.aclose()

    assert limiter.calls == 1 and inner.closed
    assert (paced.provider, paced.model) == ("fake", "fake-model")


def test_paced_llm_uses_the_configured_model() -> None:
    llm = paced_llm(Settings(_env_file=None, llm_provider="fake"), per_minute=60)

    assert llm.model == "fake-model"
