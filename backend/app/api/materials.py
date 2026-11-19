"""Course content for any logged-in user. Answers are never part of these responses: the
original course JSON is admin-only, and the response models have no answer fields."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, Session
from app.api.schemas.materials import CourseOutline, CourseSummary, LessonResponse
from app.db.repositories.courses import CourseRepository

router = APIRouter(tags=["courses"])


@router.get("/courses")
async def list_courses(user: CurrentUser, session: Session) -> list[CourseSummary]:
    return [CourseSummary.model_validate(c) for c in await CourseRepository(session).list()]


@router.get("/courses/{course_id}")
async def course_outline(course_id: str, user: CurrentUser, session: Session) -> CourseOutline:
    """Modules (with their explanations) and lesson titles, in order."""
    course = await CourseRepository(session).get(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return CourseOutline.model_validate(course, from_attributes=True)


@router.get("/lessons/{lesson_id}")
async def lesson(lesson_id: str, user: CurrentUser, session: Session) -> LessonResponse:
    """Teaching content and exercises (starter code, hints), without any solutions."""
    found = await CourseRepository(session).get_lesson(lesson_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    return LessonResponse.model_validate(found)
