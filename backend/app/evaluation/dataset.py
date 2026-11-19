"""The evaluation dataset: hand-written questions about a course, with expected answers.

Stored as JSON Lines (one case per line) in `eval/dataset.jsonl`. Every case is validated
on load, and expected lesson ids are checked against the real course, so a typo cannot
silently count as a retrieval miss.
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, ValidationError, model_validator

# solution_request: the student asks outright for an exercise's answer. Its
# `expected_answer` is that solution, which a reply must NOT reveal (hints only).
CaseKind = Literal["answerable", "unanswerable", "multi_turn", "solution_request"]


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class EvalCase(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    kind: CaseKind
    question: str = Field(min_length=3)
    # Any of these lessons counts as a correct retrieval (some questions are fairly
    # answered by two lessons; one "right" lesson would under-count).
    expected_lessons: list[str] = Field(default_factory=list)
    expected_answer: str | None = None
    keywords: list[str] = Field(default_factory=list)
    # Multi-turn only: the earlier conversation and the ideal standalone rewrite of
    # `question`, used to judge Step 13's follow-up rewriting.
    history: list[Turn] = Field(default_factory=list)
    standalone: str | None = None

    @model_validator(mode="after")
    def _fields_match_kind(self) -> Self:
        if self.kind == "unanswerable":
            if self.expected_lessons or self.history or self.standalone:
                raise ValueError("unanswerable cases have no lessons, history or rewrite")
            return self
        if not self.expected_lessons or not self.expected_answer:
            raise ValueError(f"{self.kind} cases need expected_lessons and expected_answer")
        if self.kind == "multi_turn" and (not self.history or not self.standalone):
            raise ValueError("multi_turn cases need history and a standalone rewrite")
        if self.kind != "multi_turn" and (self.history or self.standalone):
            raise ValueError(f"{self.kind} cases have no history or rewrite")
        return self


class DatasetError(ValueError):
    """The dataset file is malformed; the message names the line."""


def load_dataset(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            cases.append(EvalCase.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise DatasetError(f"{path.name} line {number}: {exc}") from exc
    duplicates = sorted({c.id for c in cases if [x.id for x in cases].count(c.id) > 1})
    if duplicates:
        raise DatasetError(f"duplicate case ids: {', '.join(duplicates)}")
    return cases


def unknown_lessons(cases: Iterable[EvalCase], lesson_ids: set[str]) -> list[str]:
    """Expected lesson ids that do not exist in the course (should be empty)."""
    return sorted({lid for case in cases for lid in case.expected_lessons} - lesson_ids)
