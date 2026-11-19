from collections import Counter

import pytest

from app.ingestion.course_json import parse_course
from app.ingestion.errors import InvalidUploadError

ANSWER_KEYS = (
    "quiz",
    "bugHunt",
    "fixedCode",
    "correctAnswer",
    "codereordering",
    "correctOrder",
    "dragandropp",
    "correctpairs",
    "cardmatching",
    "matches",
    "interactiveExercise",
    "miniChallenge",
)


def test_real_course_has_the_expected_shape(real_course_bytes: bytes) -> None:
    course = parse_course(real_course_bytes, "javascript")

    lessons = [lesson for module in course.modules for lesson in module.lessons]
    exercises = [e for lesson in lessons for e in lesson.exercises]
    assert (course.id, course.language, course.level) == (
        "javascript-beginner-v1",
        "javascript",
        "Beginner",
    )
    assert len(course.modules) == 8
    assert len(lessons) == 64
    assert sum(len(lesson.quiz_questions) for lesson in lessons) == 640
    assert Counter(e.kind for e in exercises) == {
        "interactive": 64,
        "mini_challenge": 64,
        "bug_hunt": 64,
    }
    assert [m.position for m in course.modules] == list(range(1, 9))


def test_student_content_never_contains_answers(real_course_bytes: bytes) -> None:
    course = parse_course(real_course_bytes, "javascript")

    for module in course.modules:
        for lesson in module.lessons:
            keys = set(_all_keys(lesson.content))
            assert not keys & set(ANSWER_KEYS), lesson.id


def _all_keys(value: object):
    """Every dict key at any depth (values like `"kind": "quiz"` are not keys)."""
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from _all_keys(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _all_keys(inner)


def test_practice_lists_activities_by_name_and_size_only(real_course_bytes: bytes) -> None:
    lesson = parse_course(real_course_bytes, "javascript").modules[0].lessons[0]

    practice = lesson.content["practice"]

    assert [a["kind"] for a in practice] == [
        "quiz",
        "drag_and_drop",
        "card_matching",
        "code_reordering",
    ]
    assert practice[0] == {"kind": "quiz", "title": "Quiz", "count": 10}
    assert all(set(a) == {"kind", "title", "count"} for a in practice)


def test_quiz_and_exercises_are_mapped(small_course: dict, to_bytes) -> None:
    lesson = parse_course(to_bytes(small_course), "python").modules[0].lessons[0]
    source = small_course["course"]["modules"][0]["lessons"][0]

    first = lesson.quiz_questions[0]
    assert first.position == 1
    assert first.correct_index == int(source["quiz"][0]["correctAnswer"])
    assert first.options == source["quiz"][0]["options"]
    bug_hunt = next(e for e in lesson.exercises if e.kind == "bug_hunt")
    assert bug_hunt.starter_code == source["bugHunt"]["buggyCode"]
    assert bug_hunt.solution == source["bugHunt"]["fixedCode"]
    assert bug_hunt.hints == [source["bugHunt"]["hint"]]
    challenge = next(e for e in lesson.exercises if e.kind == "mini_challenge")
    assert challenge.difficulty == source["miniChallenge"]["difficulty"]
    assert source["miniChallenge"]["prompt"] in challenge.instructions


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"{not json", "Invalid JSON at line 1"),
        (b"[1, 2]", "must contain a JSON object"),
        (b"\xff\xfe", "not valid UTF-8"),
        (b"[" * 100_000 + b"]" * 100_000, "Invalid JSON|nested too deeply|must contain"),
        (b'{"nothing": 1}', "'course' is a required property"),
    ],
    ids=["broken", "not-object", "not-utf8", "deep-nesting", "missing-course"],
)
def test_malformed_files_are_rejected(raw: bytes, message: str) -> None:
    with pytest.raises(InvalidUploadError, match=message):
        parse_course(raw, "javascript")


def test_schema_type_errors_name_the_place_not_the_value(small_course: dict, to_bytes) -> None:
    small_course["course"]["modules"][1]["lessons"][0]["title"] = 12345

    with pytest.raises(InvalidUploadError) as excinfo:
        parse_course(to_bytes(small_course), "javascript")

    message = str(excinfo.value)
    assert "course.modules[1].lessons[0].title" in message
    assert "12345" not in message


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda c: c["modules"][0].update(moduleId="Bad ID!"), "should match pattern"),
        (lambda c: c.update(courseId="x" * 101), "should match pattern"),
        (
            lambda c: c["modules"][0]["lessons"][0]["quiz"][0].update(correctAnswer="4"),
            "index of one of the options",
        ),
        (
            lambda c: c["modules"][0]["lessons"][0]["quiz"][0].update(correctAnswer="B"),
            "index of one of the options",
        ),
        (
            lambda c: c["modules"][0]["lessons"][0]["quiz"][0].update(options=["only one"]),
            "at least 2",
        ),
        (lambda c: c["modules"][0].update(lessons=[]), "at least 1"),
        (lambda c: c.update(courseTitle=""), "at least 1 character"),
    ],
    ids=[
        "bad-id",
        "long-id",
        "answer-out-of-range",
        "answer-not-index",
        "one-option",
        "no-lessons",
        "empty-title",
    ],
)
def test_course_rules_beyond_the_schema(small_course: dict, to_bytes, change, message: str) -> None:
    change(small_course["course"])

    with pytest.raises(InvalidUploadError, match=message):
        parse_course(to_bytes(small_course), "javascript")


def test_duplicate_ids_are_rejected(small_course: dict, to_bytes) -> None:
    lessons = small_course["course"]["modules"][1]["lessons"]
    lessons[1]["lessonId"] = lessons[0]["lessonId"]

    with pytest.raises(InvalidUploadError, match="Duplicate ids.*small-js-mod-2-lesson-1"):
        parse_course(to_bytes(small_course), "javascript")


def test_bom_is_tolerated(small_course: dict, to_bytes) -> None:
    course = parse_course(b"\xef\xbb\xbf" + to_bytes(small_course), "javascript")

    assert course.id == "small-js"
