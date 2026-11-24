"""Response bodies for course materials. None of these models has a field for quiz
answers, exercise solutions or bug explanations, so they cannot leak by accident."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    # Why indexing failed (fixed, safe wording); None unless status is "failed".
    error_message: str | None
    created_at: datetime


class CourseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    level: str | None
    language: str


class LessonSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    position: int
    title: str


class ModuleOutline(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    position: int
    title: str
    description: str | None
    content: dict[str, Any]
    lessons: list[LessonSummary]


class CourseOutline(CourseSummary):
    modules: list[ModuleOutline]


class ExerciseResponse(BaseModel):
    """What a student sees of an exercise: no `solution`, no `bug_explanation`."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    instructions: str
    starter_code: str
    expected_output: str | None
    hints: list[str]
    difficulty: str | None


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    module_id: str
    position: int
    title: str
    objective: str | None
    content: dict[str, Any]
    exercises: list[ExerciseResponse]
