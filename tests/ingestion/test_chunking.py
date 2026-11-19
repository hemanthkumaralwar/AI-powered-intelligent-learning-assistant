import json
import uuid
from collections import Counter

import pytest

from app.db.models import Course, Exercise, Lesson, Module
from app.ingestion.chunking import (
    MAX_BODY_CHARS,
    MAX_CHUNK_CHARS,
    ChunkTooLargeError,
    chunk_course,
    chunk_id,
)
from app.ingestion.course_json import parse_course

DOC = uuid.UUID("11111111-1111-1111-1111-111111111111")
SENTINELS = {
    "fixedCode": "SENTINEL_FIXED_CODE_7f3a",
    "bug": "SENTINEL_BUG_EXPLANATION_7f3a",
    "correctAnswerOption": "SENTINEL_CORRECT_OPTION_7f3a",
    "dragandropp": "SENTINEL_DRAG_DROP_7f3a",
    "cardmatching": "SENTINEL_CARD_MATCH_7f3a",
    "codereordering": "SENTINEL_REORDER_7f3a",
}


@pytest.fixture(scope="module")
def real_chunks(real_course_bytes: bytes):
    return chunk_course(parse_course(real_course_bytes, "javascript"), DOC)


# ---- Done-when on the real course --------------------------------------------------------


def test_real_course_chunk_count_and_size(real_chunks) -> None:
    # ~424: coarse sections keep a course inside one day of Gemini's free embedding quota.
    assert 380 <= len(real_chunks) <= 480
    assert max(len(c.text) for c in real_chunks) <= MAX_CHUNK_CHARS
    assert [c.position for c in real_chunks] == list(range(len(real_chunks)))


def test_ids_are_unique_and_stable(real_course_bytes: bytes, real_chunks) -> None:
    again = chunk_course(parse_course(real_course_bytes, "javascript"), DOC)

    assert len({c.id for c in real_chunks}) == len(real_chunks)
    assert [c.id for c in again] == [c.id for c in real_chunks]
    assert all(len(c.id) == 64 for c in real_chunks)


def test_ids_differ_between_documents(real_course_bytes: bytes, real_chunks) -> None:
    other = chunk_course(parse_course(real_course_bytes, "javascript"), uuid.uuid4())

    assert not {c.id for c in other} & {c.id for c in real_chunks}


def test_every_lesson_has_all_sections(real_chunks) -> None:
    per_lesson = Counter(c.lesson_id for c in real_chunks if c.lesson_id)
    sections = Counter(c.section for c in real_chunks)

    assert len(per_lesson) == 64
    for name in ("Explanation", "Summary", "Analogy, story and use cases", "Practice exercises"):
        assert len({c.lesson_id for c in real_chunks if c.section == name}) == 64, name
    lessons_with_examples = {c.lesson_id for c in real_chunks if c.section.startswith("Example")}
    assert len(lessons_with_examples) == 64
    assert sections["Module overview"] >= 8


def test_exercise_chunks_are_tagged_for_hint_only_tutoring(real_chunks) -> None:
    exercises = [c for c in real_chunks if c.metadata["type"] == "exercise"]

    assert {c.section for c in exercises} == {"Practice exercises"}
    assert len({c.lesson_id for c in exercises}) == 64
    assert all(
        c.metadata["exercise_kinds"] == ["interactive", "mini_challenge", "bug_hunt"]
        for c in exercises
    )
    all_text = "\n".join(c.text for c in exercises)
    for heading in ("Try it yourself:", "Mini challenge:", "Bug hunt:", "Buggy code:"):
        assert heading in all_text


def test_real_course_fixes_appear_only_where_the_lesson_itself_teaches_them(
    real_course_bytes: bytes, real_chunks
) -> None:
    source = json.loads(real_course_bytes)["course"]
    for module in source["modules"]:
        for lesson in module["lessons"]:
            bug_hunt = lesson["bugHunt"]
            for chunk in real_chunks:
                assert bug_hunt["bug"] not in chunk.text
                if bug_hunt["fixedCode"].strip() in chunk.text:
                    # Only when an example shows the same code, never from the bug hunt.
                    assert chunk.metadata["type"] == "content"
                    assert chunk.section.startswith("Example")


def test_chunk_text_has_context_header_and_metadata(real_chunks) -> None:
    first_lesson_chunk = next(c for c in real_chunks if c.lesson_id)

    assert first_lesson_chunk.text.startswith(
        "JavaScript Fundamentals › Variables and Data Types › "
    )
    meta = first_lesson_chunk.metadata
    assert meta["course_id"] == "javascript-beginner-v1"
    assert meta["lesson_id"] == first_lesson_chunk.lesson_id
    assert meta["source"] == "course"
    assert "```javascript" in "\n".join(c.text for c in real_chunks)
    assert "```mermaid" in "\n".join(c.text for c in real_chunks if c.section == "Summary")


# ---- answers can never reach a chunk (sentinel values in every answer field) --------------


def test_no_answer_field_ever_reaches_a_chunk(small_course: dict, to_bytes) -> None:
    for module in small_course["course"]["modules"]:
        for lesson in module["lessons"]:
            lesson["bugHunt"]["fixedCode"] = SENTINELS["fixedCode"]
            lesson["bugHunt"]["bug"] = SENTINELS["bug"]
            for question in lesson["quiz"]:
                question["options"][int(question["correctAnswer"])] = SENTINELS[
                    "correctAnswerOption"
                ]
            lesson["dragandropp"]["title"] = SENTINELS["dragandropp"]
            lesson["cardmatching"]["title"] = SENTINELS["cardmatching"]
            lesson["codereordering"]["title"] = SENTINELS["codereordering"]

    chunks = chunk_course(parse_course(to_bytes(small_course), "javascript"), DOC)
    text = "\n".join(c.text + json.dumps(c.metadata) for c in chunks)

    assert chunks
    for name, sentinel in SENTINELS.items():
        assert sentinel not in text, name


# ---- edge cases with hand-built objects --------------------------------------------------


def build(content: dict, exercises: list[Exercise] | None = None, module_content=None) -> Course:
    lesson = Lesson(
        id="l1",
        position=1,
        title="Loops",
        objective=None,
        content=content,
        exercises=exercises or [],
    )
    module = Module(
        id="m1",
        position=1,
        title="Basics",
        description=None,
        content=module_content or {},
        lessons=[lesson],
    )
    return Course(id="c1", title="Course", language="python", modules=[module])


def test_empty_sections_produce_no_chunks() -> None:
    chunks = chunk_course(build({}), DOC)

    assert chunks == []


def test_long_section_is_split_with_overlap() -> None:
    points = [f"Point {i}: " + "word " * 30 for i in range(30)]
    content = {"lessonExplanation": [{"topic": "Loops", "points": points}]}

    chunks = chunk_course(build(content), DOC)

    assert len(chunks) >= 4
    assert all(len(c.text) <= MAX_CHUNK_CHARS for c in chunks)
    bodies = [c.text.split("\n\n", 1)[1] for c in chunks]
    assert all(len(b) <= MAX_BODY_CHARS for b in bodies)
    assert bodies[0][-40:].split()[-1] in bodies[1]  # overlap carries text across
    assert [c.metadata["part"] for c in chunks] == list(range(1, len(chunks) + 1))
    assert len({c.id for c in chunks}) == len(chunks)


def test_exercise_chunk_uses_prompt_fields_only() -> None:
    exercise = Exercise(
        kind="bug_hunt",
        title="Fix it",
        instructions="Find the bug.",
        starter_code="x = 1\nx(",
        expected_output=None,
        hints=["Look at line 2"],
        solution="SOLUTION-NEVER",
        bug_explanation="EXPLANATION-NEVER",
    )

    (chunk,) = chunk_course(build({}, [exercise]), DOC)

    assert chunk.section == "Practice exercises"
    assert chunk.text.split("\n\n")[1] == "Bug hunt: Fix it"
    assert "Buggy code:\n```python\nx = 1\nx(\n```" in chunk.text
    assert "- Look at line 2" in chunk.text
    assert "NEVER" not in chunk.text
    assert chunk.metadata["type"] == "exercise"


def test_module_overview_has_no_lesson() -> None:
    overview = {"moduleExplanation": [{"topic": "Basics", "points": ["Start here"]}]}

    (chunk,) = chunk_course(build({}, module_content=overview), DOC)

    assert chunk.lesson_id is None
    assert chunk.text.startswith("Course › Basics — Module overview")


def test_oversized_header_is_an_error_not_truncation() -> None:
    course = build({"keyTakeaways": ["short"]})
    course.title = "T" * (MAX_CHUNK_CHARS + 1)

    with pytest.raises(ChunkTooLargeError):
        chunk_course(course, DOC)


def test_chunk_id_is_deterministic() -> None:
    assert chunk_id(DOC, "l1:analogy", 0) == chunk_id(DOC, "l1:analogy", 0)
    assert chunk_id(DOC, "l1:analogy", 0) != chunk_id(DOC, "l1:analogy", 1)


def test_exercise_order_does_not_depend_on_load_order() -> None:
    def make(kind: str) -> Exercise:
        return Exercise(
            kind=kind,
            title=kind,
            instructions="Do it.",
            starter_code="",
            expected_output=None,
            hints=[],
        )

    loaded = [make("bug_hunt"), make("interactive"), make("mini_challenge")]  # database order
    as_file = [make("interactive"), make("mini_challenge"), make("bug_hunt")]  # file order

    (from_db,) = chunk_course(build({}, loaded), DOC)
    (from_file,) = chunk_course(build({}, as_file), DOC)

    assert from_db.text == from_file.text
    assert from_db.metadata["exercise_kinds"] == ["interactive", "mini_challenge", "bug_hunt"]
