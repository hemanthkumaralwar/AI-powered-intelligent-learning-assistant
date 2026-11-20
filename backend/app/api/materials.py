"""Course content, public (Step 24): anyone may browse courses and read lessons, guests
within an app-wide guest quota. Answers are never part of these responses: the original
course JSON is admin-only, and the response models have no answer fields, so making
these public exposes course text only.

Responses are cached (the same for every student, read on every page view); admin
uploads and deletions clear the cache, so students never see a removed course.
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ContentCache, GuestOrUser, Session
from app.api.schemas.materials import CourseOutline, CourseSummary, LessonResponse
from app.db.repositories.courses import CourseRepository

router = APIRouter(tags=["courses"], dependencies=[GuestOrUser])


@router.get("/courses")
async def list_courses(session: Session, cache: ContentCache) -> list[CourseSummary]:
    if (cached := cache.get(("courses",))) is not None:
        return cached
    courses = await CourseRepository(session).list_courses()
    response = [CourseSummary.model_validate(c) for c in courses]
    cache.set(("courses",), response)
    return response


@router.get("/courses/{course_id}")
async def course_outline(course_id: str, session: Session, cache: ContentCache) -> CourseOutline:
    """Modules (with their explanations) and lesson titles, in order."""
    if (cached := cache.get(("course", course_id))) is not None:
        return cached
    course = await CourseRepository(session).get(course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    response = CourseOutline.model_validate(course, from_attributes=True)
    cache.set(("course", course_id), response)
    return response


@router.get("/lessons/{lesson_id}")
async def lesson(lesson_id: str, session: Session, cache: ContentCache) -> LessonResponse:
    """Teaching content and exercises (starter code, hints), without any solutions."""
    if (cached := cache.get(("lesson", lesson_id))) is not None:
        return cached
    found = await CourseRepository(session).get_lesson(lesson_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    response = LessonResponse.model_validate(found)
    cache.set(("lesson", lesson_id), response)
    return response
