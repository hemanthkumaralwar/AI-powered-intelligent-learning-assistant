"""Request and response bodies for a lesson's quiz. The question model has no answer field:
answers appear only in an attempt's results, after the student has answered."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

MAX_QUESTIONS = 100


class QuizOption(BaseModel):
    id: int  # what to send back as the answer
    text: str


class QuizQuestionResponse(BaseModel):
    id: uuid.UUID
    position: int
    question: str
    options: list[QuizOption]  # shuffled, in the same order for this student every time


class QuizResponse(BaseModel):
    lesson_id: str
    questions: list[QuizQuestionResponse]


class QuizAttemptRequest(BaseModel):
    # Question id -> chosen option id; a question left out (or null) counts as wrong.
    answers: dict[uuid.UUID, int | None] = Field(max_length=MAX_QUESTIONS)


class QuestionResultResponse(BaseModel):
    question_id: uuid.UUID
    chosen: int | None
    correct_option: int
    correct: bool
    explanation: str | None


class QuizAttemptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    correct: int
    total: int
    created_at: datetime


class QuizAttemptResponse(QuizAttemptSummary):
    results: list[QuestionResultResponse]
