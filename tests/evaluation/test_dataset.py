import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.evaluation.dataset import DatasetError, EvalCase, load_dataset, unknown_lessons

ROOT = Path(__file__).resolve().parents[2]


def answerable(**overrides) -> dict:
    return {
        "id": "q1",
        "kind": "answerable",
        "question": "What is let?",
        "expected_lessons": ["js-l1"],
        "expected_answer": "A block-scoped binding.",
        **overrides,
    }


def test_the_real_dataset_is_valid_and_matches_the_course() -> None:
    cases = load_dataset(ROOT / "eval" / "dataset.jsonl")
    course = json.loads(
        (ROOT / "eval" / "materials" / "javascript-beginner.json").read_text("utf-8")
    )
    lessons = {lesson["lessonId"] for m in course["course"]["modules"] for lesson in m["lessons"]}

    assert unknown_lessons(cases, lessons) == []
    kinds = [c.kind for c in cases]
    assert kinds.count("answerable") >= 50
    assert kinds.count("unanswerable") >= 10
    assert kinds.count("multi_turn") >= 8


@pytest.mark.parametrize(
    "case",
    [
        answerable(expected_lessons=[]),
        answerable(expected_answer=None),
        answerable(history=[{"role": "user", "content": "hi"}]),
        {
            "id": "u1",
            "kind": "unanswerable",
            "question": "What is Docker?",
            "expected_lessons": ["x"],
        },
        answerable(kind="multi_turn"),
        answerable(id="Bad Id"),
    ],
    ids=[
        "no-lessons",
        "no-answer",
        "history-on-answerable",
        "lessons-on-unanswerable",
        "multi-turn-without-history",
        "bad-id",
    ],
)
def test_invalid_cases_are_rejected(case: dict) -> None:
    with pytest.raises(ValidationError):
        EvalCase.model_validate(case)


def test_valid_multi_turn_case() -> None:
    case = EvalCase.model_validate(
        answerable(
            kind="multi_turn",
            question="And const?",
            standalone="What is const?",
            history=[{"role": "user", "content": "What is let?"}],
        )
    )

    assert case.standalone == "What is const?"


def test_load_reports_the_bad_line(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text(json.dumps(answerable()) + "\n\n{broken\n", encoding="utf-8")

    with pytest.raises(DatasetError, match="line 3"):
        load_dataset(path)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text(json.dumps(answerable()) + "\n" + json.dumps(answerable()) + "\n", "utf-8")

    with pytest.raises(DatasetError, match="duplicate case ids: q1"):
        load_dataset(path)


def test_unknown_lessons_are_listed() -> None:
    cases = [EvalCase.model_validate(answerable(expected_lessons=["js-l1", "js-typo"]))]

    assert unknown_lessons(cases, {"js-l1"}) == ["js-typo"]
