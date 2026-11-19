"""Coding-assistant evaluation (Step 14): does /coding/debug find known bugs?

A bug counts as identified when one reported issue sits within one line of the known
bug line and names one of the case's keywords. Deterministic, so no LLM judge is
needed. A provider failure or an unusable reply is recorded per case, not fatal.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.coding.schemas import DebugOutput
from app.coding.service import CodingResult
from app.providers.errors import ProviderCallError
from app.runner.base import LANGUAGES, Language

# A bug often shows on the line next to its cause (const declared on line 1, the
# reassignment on line 2), so either neighbour counts.
LINE_TOLERANCE = 1
TARGET_IDENTIFIED = 0.8


class CodeCase(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    language: Language
    source: Literal["course", "handwritten"]
    code: str = Field(min_length=1)
    bug_line: int = Field(ge=1)
    keywords: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _bug_line_exists(self) -> Self:
        if self.bug_line > len(self.code.splitlines()):
            raise ValueError("bug_line is past the end of the code")
        return self


type Debug = Callable[[CodeCase], Awaitable[CodingResult[DebugOutput]]]


@dataclass(frozen=True)
class CodeResult:
    case_id: str
    language: str
    identified: bool
    valid_json: bool
    exercise: bool
    reported_lines: list[int]
    reason: str


def identified(case: CodeCase, output: DebugOutput) -> bool:
    keywords = [k.lower() for k in case.keywords]
    for issue in output.issues:
        if abs(issue.line - case.bug_line) > LINE_TOLERANCE:
            continue
        text = f"{issue.problem} {issue.fix_hint}".lower()
        if any(keyword in text for keyword in keywords):
            return True
    return False


async def evaluate_debug(cases: Sequence[CodeCase], debug: Debug) -> list[CodeResult]:
    results = []
    for case in cases:
        try:
            result = await debug(case)
        except ProviderCallError as exc:
            reason = f"provider error: {type(exc).__name__}"
            results.append(CodeResult(case.id, case.language, False, False, False, [], reason))
            continue
        found = identified(case, result.output)
        results.append(
            CodeResult(
                case_id=case.id,
                language=case.language,
                identified=found,
                valid_json=True,
                exercise=result.exercise,
                reported_lines=[issue.line for issue in result.output.issues],
                reason="" if found else "no issue near the bug line with a keyword",
            )
        )
    return results


def coding_summary(results: Sequence[CodeResult]) -> dict[str, Any]:
    by_language = {
        language: _rate([r for r in results if r.language == language], "identified")
        for language in LANGUAGES
        if any(r.language == language for r in results)
    }
    return {
        "cases": len(results),
        "identified": _rate(results, "identified"),
        "valid_json": _rate(results, "valid_json"),
        "by_language": by_language,
    }


def render_coding_markdown(results: Sequence[CodeResult], run: dict[str, Any]) -> str:
    s = coding_summary(results)
    lines = [
        f"# Coding assistant evaluation — {run['date']}",
        "",
        f"- Model: `{run['llm_model']}`; dataset: `{run['dataset']}` ({s['cases']} cases)",
        "- Identified: an issue within one line of the known bug that names a keyword.",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Bugs identified | {s['identified']:.0%} (target ≥ {TARGET_IDENTIFIED:.0%}) |",
        f"| Responses that passed JSON validation | {s['valid_json']:.0%} |",
        "",
        "| Language | Identified |",
        "|---|---|",
        *(f"| {lang} | {rate:.0%} |" for lang, rate in s["by_language"].items()),
        "",
        "## Per case",
        "",
        "| Case | Identified | Reported lines | Course exercise (hints only) | Note |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        mark = "yes" if r.identified else "**no**"
        reported = ", ".join(map(str, r.reported_lines)) or "—"
        lines.append(
            f"| {r.case_id} | {mark} | {reported} | {'yes' if r.exercise else ''} | {r.reason} |"
        )
    return "\n".join(lines) + "\n"


def _rate(results: Sequence[CodeResult], attribute: str) -> float:
    return sum(getattr(r, attribute) for r in results) / len(results) if results else 0.0
