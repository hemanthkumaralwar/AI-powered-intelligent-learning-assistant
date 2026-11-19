"""Request and response bodies for /chat."""

from pydantic import BaseModel, Field, field_validator

from app.rag.answer import Answer, Citation

MAX_QUESTION_CHARS = 1000


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    # Limits the search to one course; omitted, every course is searched.
    course_id: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question must not be empty")
        return value


class CitationResponse(BaseModel):
    number: int
    course_title: str
    module_title: str
    lesson_id: str | None
    lesson_title: str | None
    section: str
    link: str | None

    @classmethod
    def from_citation(cls, citation: Citation) -> "CitationResponse":
        return cls(
            number=citation.number,
            course_title=citation.course_title,
            module_title=citation.module_title,
            lesson_id=citation.lesson_id,
            lesson_title=citation.lesson_title,
            section=citation.section,
            link=citation.link,
        )


class AskResponse(BaseModel):
    answer: str
    # False means the course materials do not cover the question and `answer` says so.
    grounded: bool
    citations: list[CitationResponse]

    @classmethod
    def from_answer(cls, answer: Answer) -> "AskResponse":
        return cls(
            answer=answer.text,
            grounded=answer.grounded,
            citations=[CitationResponse.from_citation(c) for c in answer.citations],
        )
