"""Request and response bodies for /coding."""

from pydantic import BaseModel, Field, field_validator

from app.coding.schemas import Issue, LineNote, PracticeQuestion
from app.coding.service import CodingResult, RelatedLesson
from app.runner.base import Language, Outcome

# Smaller than /code/run's 20 KB: a line-by-line explanation of more would not fit the
# model's answer, and long code costs free-tier tokens on every request.
MAX_CODE_BYTES = 8 * 1024
MAX_CODE_LINES = 200
MAX_TOPIC_CHARS = 200
# Accepted as sent by /code/run; only the end of each stream reaches the model.
MAX_RUN_STREAM_CHARS = 20_000


class CodeInput(BaseModel):
    language: Language
    code: str = Field(min_length=1)

    @field_validator("code")
    @classmethod
    def _code_size(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Code must not be empty")
        if len(value.encode()) > MAX_CODE_BYTES:
            raise ValueError("Code must be at most 8 KB")
        if len(value.splitlines()) > MAX_CODE_LINES:
            raise ValueError(f"Code must be at most {MAX_CODE_LINES} lines")
        return value


class RunOutput(BaseModel):
    """The /code/run result for the same code (optional evidence for debugging). Output
    the student ran elsewhere and pasted in has no outcome."""

    outcome: Outcome | None = None
    stdout: str = Field(default="", max_length=MAX_RUN_STREAM_CHARS)
    stderr: str = Field(default="", max_length=MAX_RUN_STREAM_CHARS)
    compile_output: str = Field(default="", max_length=MAX_RUN_STREAM_CHARS)


class DebugRequest(CodeInput):
    run: RunOutput | None = None


class TopicInput(BaseModel):
    language: Language
    topic: str = Field(min_length=1, max_length=MAX_TOPIC_CHARS)

    @field_validator("topic")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic must not be empty")
        return value


class RelatedLessonResponse(BaseModel):
    lesson_id: str
    lesson_title: str | None
    module_title: str
    course_title: str
    link: str

    @classmethod
    def from_lesson(cls, lesson: RelatedLesson) -> "RelatedLessonResponse":
        return cls(
            lesson_id=lesson.lesson_id,
            lesson_title=lesson.lesson_title,
            module_title=lesson.module_title,
            course_title=lesson.course_title,
            link=lesson.link,
        )


class CodingResponse(BaseModel):
    related_lessons: list[RelatedLessonResponse]


def _related(result: CodingResult) -> list[RelatedLessonResponse]:
    return [RelatedLessonResponse.from_lesson(lesson) for lesson in result.related_lessons]


class ExplainResponse(CodingResponse):
    summary: str
    lines: list[LineNote]

    @classmethod
    def from_result(cls, result: CodingResult) -> "ExplainResponse":
        out = result.output
        return cls(summary=out.summary, lines=out.lines, related_lessons=_related(result))


class DebugResponse(CodingResponse):
    summary: str
    issues: list[Issue]
    corrected_code: str | None
    # True when the code is a course exercise: hints only, no corrected code.
    exercise: bool

    @classmethod
    def from_result(cls, result: CodingResult) -> "DebugResponse":
        out = result.output
        return cls(
            summary=out.summary,
            issues=out.issues,
            corrected_code=out.corrected_code,
            exercise=result.exercise,
            related_lessons=_related(result),
        )


class ExampleResponse(CodingResponse):
    title: str
    code: str
    explanation: str

    @classmethod
    def from_result(cls, result: CodingResult) -> "ExampleResponse":
        out = result.output
        return cls(
            title=out.title,
            code=out.code,
            explanation=out.explanation,
            related_lessons=_related(result),
        )


class PracticeResponse(CodingResponse):
    questions: list[PracticeQuestion]

    @classmethod
    def from_result(cls, result: CodingResult) -> "PracticeResponse":
        return cls(questions=result.output.questions, related_lessons=_related(result))
