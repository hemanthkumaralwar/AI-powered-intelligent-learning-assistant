"""Your progress and what to do next. Only ever the caller's own data: there is no
parameter that names a student."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, Session
from app.api.schemas.practice import ActivityResponse
from app.api.schemas.progress import (
    ExerciseToDoResponse,
    LessonProgressResponse,
    ModuleProgressResponse,
    ProgressResponse,
    RecommendationResponse,
    RecommendationsResponse,
)
from app.db.models import Course
from app.db.repositories.courses import CourseRepository
from app.db.repositories.exercises import ExerciseRepository
from app.learning.practice import PracticeFinder
from app.learning.progress import (
    ExerciseInfo,
    LessonInfo,
    ModuleInfo,
    ModuleProgress,
    compute_progress,
)
from app.learning.recommend import Recommendation, recommend

router = APIRouter(prefix="/me", tags=["progress"])

CourseId = Annotated[str | None, Query(min_length=1, max_length=100)]


def get_practice_finder(request: Request) -> PracticeFinder:
    return request.app.state.practice


def get_weak_threshold(request: Request) -> float:
    return request.app.state.settings.weak_mastery_threshold


Practice = Annotated[PracticeFinder, Depends(get_practice_finder)]
WeakThreshold = Annotated[float, Depends(get_weak_threshold)]


@router.get("/progress")
async def my_progress(
    user: CurrentUser, session: Session, threshold: WeakThreshold, course_id: CourseId = None
) -> ProgressResponse:
    """Mastery per module and lesson, from your graded exercise attempts (recent ones
    count most). `course_id` defaults to the course you have worked on most."""
    course, modules = await _progress(session, user.id, course_id)
    return ProgressResponse(
        course_id=course.id,
        course_title=course.title,
        weak_threshold=threshold,
        modules=[_module_response(module, threshold) for module in modules],
    )


@router.get("/recommendations")
async def my_recommendations(
    user: CurrentUser,
    session: Session,
    threshold: WeakThreshold,
    practice: Practice,
    course_id: CourseId = None,
) -> RecommendationsResponse:
    """Weak lessons to review (weakest first), then the next lessons in the course, each
    with its exercises and its extra practice on the learning platform."""
    course, modules = await _progress(session, user.id, course_id)
    return RecommendationsResponse(
        course_id=course.id,
        course_title=course.title,
        recommendations=[
            _recommendation_response(pick, practice) for pick in recommend(modules, threshold)
        ],
    )


async def _progress(
    session: AsyncSession, user_id: uuid.UUID, course_id: str | None
) -> tuple[Course, list[ModuleProgress]]:
    courses = CourseRepository(session)
    exercises = ExerciseRepository(session)
    course_id = course_id or await exercises.most_attempted_course(user_id)
    if course_id is None:
        listed = await courses.list_courses()
        course_id = listed[0].id if listed else None
    course = await courses.get_full(course_id) if course_id else None
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    results = await exercises.results_by_exercise(user_id, course.id)
    return course, compute_progress(_outline(course), results)


def _outline(course: Course) -> list[ModuleInfo]:
    return [
        ModuleInfo(
            id=module.id,
            title=module.title,
            lessons=tuple(
                LessonInfo(
                    id=lesson.id,
                    title=lesson.title,
                    exercises=tuple(
                        ExerciseInfo(str(e.id), e.title, e.kind) for e in lesson.exercises
                    ),
                    practice=tuple(lesson.content.get("practice", [])),
                )
                for lesson in module.lessons
            ),
        )
        for module in course.modules
    ]


def _module_response(module: ModuleProgress, threshold: float) -> ModuleProgressResponse:
    return ModuleProgressResponse(
        module_id=module.module.id,
        title=module.module.title,
        mastery=module.mastery,
        coverage=module.coverage,
        lessons=[
            LessonProgressResponse(
                lesson_id=lesson.lesson.id,
                title=lesson.lesson.title,
                mastery=lesson.mastery,
                weak=lesson.started and lesson.mastery < threshold,
            )
            for lesson in module.lessons
        ],
    )


def _recommendation_response(
    pick: Recommendation, practice: PracticeFinder
) -> RecommendationResponse:
    lesson = pick.progress.lesson
    return RecommendationResponse(
        kind=pick.kind,
        lesson_id=lesson.id,
        lesson_title=lesson.title,
        module_title=pick.progress.module_title,
        reason=pick.reason,
        mastery=pick.progress.mastery,
        exercises=[
            ExerciseToDoResponse(
                exercise_id=item.exercise.id,
                title=item.exercise.title,
                kind=item.exercise.kind,
                score=item.score,
            )
            for item in pick.exercises
        ],
        practice=[ActivityResponse.model_validate(a) for a in lesson.practice],
        practice_url=practice.url(lesson.id),
    )
