"""Response bodies for /me/progress and /me/recommendations."""

from typing import Literal

from pydantic import BaseModel

from app.api.schemas.practice import ActivityResponse


class LessonProgressResponse(BaseModel):
    lesson_id: str
    title: str
    # None: not started yet (no exercise attempted), which is not the same as 0.
    mastery: float | None
    weak: bool


class ModuleProgressResponse(BaseModel):
    module_id: str
    title: str
    mastery: float | None
    # Share of the module's lessons with at least one attempted exercise.
    coverage: float
    lessons: list[LessonProgressResponse]


class ProgressResponse(BaseModel):
    course_id: str
    course_title: str
    weak_threshold: float
    modules: list[ModuleProgressResponse]


class ExerciseToDoResponse(BaseModel):
    exercise_id: str
    title: str
    kind: str
    # None: never attempted.
    score: float | None


class RecommendationResponse(BaseModel):
    kind: Literal["review", "next"]
    lesson_id: str
    lesson_title: str
    module_title: str
    reason: str
    mastery: float | None
    exercises: list[ExerciseToDoResponse]
    # Extra practice on the learning platform for this lesson.
    practice: list[ActivityResponse]
    practice_url: str | None


class RecommendationsResponse(BaseModel):
    course_id: str
    course_title: str
    recommendations: list[RecommendationResponse]
