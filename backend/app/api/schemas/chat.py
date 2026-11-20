"""Request and response bodies for /chat."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.schemas.practice import PracticePointerResponse
from app.chat.service import ChatReply
from app.llm.prompt_levels import Level
from app.rag.answer import Citation

MAX_QUESTION_CHARS = 1000


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    # Limits the search to one course; omitted, every course is searched.
    course_id: str | None = Field(default=None, min_length=1, max_length=100)
    # Continue this conversation; omitted, a new session is started.
    session_id: uuid.UUID | None = None
    # Explanation level for this answer only; omitted, the profile's level is used.
    level: Level | None = None

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
    # None for citations saved before Step 23a (chat history keeps them as stored).
    course_id: str | None = None

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
            course_id=citation.course_id,
        )


class AskResponse(BaseModel):
    session_id: uuid.UUID
    answer: str
    # False means the course materials do not cover the question and `answer` says so.
    grounded: bool
    citations: list[CitationResponse]
    # The cited lessons' quizzes and activities on the learning platform.
    practice: list[PracticePointerResponse]

    @classmethod
    def from_reply(cls, reply: ChatReply) -> "AskResponse":
        answer = reply.answer
        return cls(
            session_id=reply.session_id,
            answer=answer.text,
            grounded=answer.grounded,
            citations=[CitationResponse.from_citation(c) for c in answer.citations],
            practice=[PracticePointerResponse.from_pointer(p) for p in reply.practice],
        )


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "assistant"]
    content: str
    # Assistant messages only.
    grounded: bool | None
    citations: list[CitationResponse] | None
    created_at: datetime


class SessionDetail(SessionSummary):
    messages: list[MessageResponse]
