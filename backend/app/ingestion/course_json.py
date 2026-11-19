"""Parse an ArchintX course JSON into ORM objects (pure: no database access).

Two layers of checks:
1. `course_schema.json` (the course generator's contract): structure and types.
2. Stricter rules of our own (`_CourseIn`): id format, unique ids, sizes, and that every
   quiz answer points at one of its options. The generator's schema checks none of these.
"""

import json
from collections.abc import Iterable, Sequence
from functools import cache
from pathlib import Path
from typing import Annotated, Any

import jsonschema
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from app.db.models import Course, Exercise, Lesson, Module, QuizQuestion
from app.ingestion.errors import InvalidUploadError

SCHEMA_PATH = Path(__file__).with_name("course_schema.json")
MAX_MODULES = 50
MAX_LESSONS_PER_MODULE = 50

# Copied into lessons.content: what students may see. Quizzes and exercises get their own
# tables; codereordering, dragandropp and cardmatching are left out because they embed
# their answers (correctOrder, correctpairs, matches).
TEACHING_KEYS = (
    "lessonExplanation",
    "duration",
    "hooklines_title",
    "hooklines",
    "concepts",
    "syntax",
    "parts",
    "analogy",
    "example",
    "flowchart",
    "useCaseCards",
    "realWorldStory",
    "keyTakeaways",
)

Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,100}$")]
Title = Annotated[str, StringConstraints(min_length=1, max_length=255)]


class _Quiz(BaseModel):
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=6)
    correctAnswer: str  # noqa: N815 - names follow the course JSON
    explanation: str

    @model_validator(mode="after")
    def _answer_is_an_option(self) -> "_Quiz":
        if not self.correctAnswer.isdigit() or int(self.correctAnswer) >= len(self.options):
            raise ValueError("correctAnswer must be the index of one of the options")
        return self


class _LessonIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    lessonId: Id  # noqa: N815
    title: Title
    quiz: list[_Quiz]


class _ModuleIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    moduleId: Id  # noqa: N815
    title: Title
    lessons: list[_LessonIn] = Field(min_length=1, max_length=MAX_LESSONS_PER_MODULE)


class _CourseIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    courseId: Id  # noqa: N815
    courseTitle: Title  # noqa: N815
    modules: list[_ModuleIn] = Field(min_length=1, max_length=MAX_MODULES)


@cache
def _validator() -> jsonschema.Draft7Validator:
    return jsonschema.Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def parse_course(raw: bytes, language: str) -> Course:
    """Validate a course file and build its Course/Module/Lesson/quiz/exercise objects."""
    document = _load_json(raw)
    _check_schema(document)
    data = document["course"]
    try:
        _CourseIn.model_validate(data)
    except ValidationError as exc:
        error = exc.errors()[0]
        raise InvalidUploadError(f"{_where(('course', *error['loc']))}: {error['msg']}") from exc
    _check_unique_ids(data)
    return _build_course(data, language)


def _load_json(raw: bytes) -> dict[str, Any]:
    try:
        document = json.loads(raw.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise InvalidUploadError("The file is not valid UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise InvalidUploadError(f"Invalid JSON at line {exc.lineno}, column {exc.colno}.") from exc
    except RecursionError as exc:
        raise InvalidUploadError("The JSON is nested too deeply.") from exc
    if not isinstance(document, dict):
        raise InvalidUploadError("The file must contain a JSON object with a 'course' key.")
    return document


def _check_schema(document: dict[str, Any]) -> None:
    error = jsonschema.exceptions.best_match(_validator().iter_errors(document))
    if error is None:
        return
    # `required` messages name the missing key; for the rest, describe the rule rather
    # than echo the offending value.
    detail = (
        error.message
        if error.validator == "required"
        else (f"expected {error.validator} {error.validator_value!r}")
    )
    raise InvalidUploadError(
        f"Does not match the course schema at {_where(error.absolute_path)}: {detail}"
    )


def _check_unique_ids(data: dict[str, Any]) -> None:
    ids = [data["courseId"]]
    for module in data["modules"]:
        ids.append(module["moduleId"])
        ids.extend(lesson["lessonId"] for lesson in module["lessons"])
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise InvalidUploadError(f"Duplicate ids in the course: {', '.join(duplicates[:5])}")


def _build_course(data: dict[str, Any], language: str) -> Course:
    return Course(
        id=data["courseId"],
        title=data["courseTitle"],
        description=data.get("courseDescription"),
        level=data.get("level"),
        language=language,
        modules=[
            Module(
                id=module["moduleId"],
                position=position,
                title=module["title"],
                description=module.get("description"),
                content={"moduleExplanation": module.get("moduleExplanation", [])},
                lessons=[
                    _build_lesson(lesson, index)
                    for index, lesson in enumerate(module["lessons"], 1)
                ],
            )
            for position, module in enumerate(data["modules"], 1)
        ],
    )


def _build_lesson(lesson: dict[str, Any], position: int) -> Lesson:
    return Lesson(
        id=lesson["lessonId"],
        position=position,
        title=lesson["title"],
        objective=lesson.get("objective"),
        content={key: lesson[key] for key in TEACHING_KEYS if key in lesson}
        | {"practice": practice_activities(lesson)},
        quiz_questions=[
            QuizQuestion(
                position=index,
                question=item["question"],
                options=item["options"],
                correct_index=int(item["correctAnswer"]),
                explanation=item.get("explanation"),
            )
            for index, item in enumerate(lesson["quiz"], 1)
        ],
        exercises=list(_build_exercises(lesson)),
    )


# (course JSON key, kind, default title, what the count measures). The activities themselves
# run on the learning platform; the assistant only points students to them.
_PRACTICE = (
    ("quiz", "quiz", "Quiz", None),
    ("dragandropp", "drag_and_drop", "Drag and drop", "items"),
    ("cardmatching", "card_matching", "Card matching", "cards"),
    ("codereordering", "code_reordering", "Code reordering", "codelines"),
)


def practice_activities(lesson: dict[str, Any]) -> list[dict[str, Any]]:
    """The lesson's practice activities as names and sizes only: never their content or
    answers (correctAnswer, correctOrder, correctpairs, matches)."""
    found = []
    for key, kind, default_title, counted in _PRACTICE:
        activity = lesson.get(key)
        if not activity:
            continue
        if counted is None:  # the quiz is a plain list of questions
            title, count = default_title, len(activity)
        else:
            title = str(activity.get("title") or default_title)[:255]
            count = len(activity.get(counted) or [])
            if kind == "card_matching":
                count //= 2  # cards come in pairs
        found.append({"kind": kind, "title": title, "count": count})
    return found


def _build_exercises(lesson: dict[str, Any]) -> Iterable[Exercise]:
    if exercise := lesson.get("interactiveExercise"):
        yield Exercise(
            kind="interactive",
            title=exercise["title"][:255],
            instructions=exercise["instruction"],
            starter_code=exercise["starterCode"],
            expected_output=exercise.get("expectebehavior"),  # sic: the schema's spelling
            hints=[],
        )
    if challenge := lesson.get("miniChallenge"):
        yield Exercise(
            kind="mini_challenge",
            title=challenge["title"][:255],
            instructions=f"{challenge['scenario']}\n\n{challenge['prompt']}",
            starter_code=challenge["starterCode"],
            expected_output=challenge.get("expectedOutput"),
            hints=list(challenge.get("hints", [])),
            difficulty=challenge.get("difficulty"),
        )
    if bug_hunt := lesson.get("bugHunt"):
        yield Exercise(
            kind="bug_hunt",
            title=bug_hunt["title"][:255],
            instructions=bug_hunt["instruction"],
            starter_code=bug_hunt["buggyCode"],
            hints=[bug_hunt["hint"]] if bug_hunt.get("hint") else [],
            solution=bug_hunt.get("fixedCode"),
            bug_explanation=bug_hunt.get("bug"),
        )


def _where(path: Sequence[Any]) -> str:
    """Render a JSON path like course.modules[2].lessons[0].quiz[3]."""
    text = ""
    for part in path:
        text += f"[{part}]" if isinstance(part, int) else (f".{part}" if text else str(part))
    return text or "the top level"
