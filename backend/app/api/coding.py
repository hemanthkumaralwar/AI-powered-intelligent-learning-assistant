"""Coding assistant: explain, debug, example and practice, for any logged-in user.

Each endpoint hands its database connection back before the slow model call (the pool
is small); only /debug reads the database first, to recognise course exercises. After
the call, a short query adds the related lessons' activities on the learning platform.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ai_errors import ai_errors
from app.api.deps import CurrentUser, Session
from app.api.schemas.coding import (
    CodeInput,
    CodingResponse,
    DebugRequest,
    DebugResponse,
    ExampleResponse,
    ExplainResponse,
    PracticeResponse,
    TopicInput,
)
from app.api.schemas.practice import PracticePointerResponse
from app.coding.prompts import run_output_text
from app.coding.service import CodingResult, CodingService
from app.db.repositories.courses import CourseRepository
from app.learning.practice import PracticeFinder

router = APIRouter(prefix="/coding", tags=["coding"])


def get_coding_service(request: Request) -> CodingService:
    return request.app.state.coding


Coding = Annotated[CodingService, Depends(get_coding_service)]


def get_practice_finder(request: Request) -> PracticeFinder:
    return request.app.state.practice


Practice = Annotated[PracticeFinder, Depends(get_practice_finder)]


async def _with_practice[ResponseT: CodingResponse](
    response: ResponseT, result: CodingResult, session: AsyncSession, practice: PracticeFinder
) -> ResponseT:
    lessons = [lesson.lesson_id for lesson in result.related_lessons]
    pointers = await practice.for_lessons(session, lessons)
    response.practice = [PracticePointerResponse.from_pointer(p) for p in pointers]
    return response


@router.post("/explain")
async def explain(
    body: CodeInput, user: CurrentUser, session: Session, coding: Coding, practice: Practice
) -> ExplainResponse:
    """Line-by-line explanation of the code."""
    user_id, level = user.id, body.level or user.level
    await session.commit()
    with ai_errors():
        result = await coding.explain(user_id, body.language, body.code, level)
    return await _with_practice(ExplainResponse.from_result(result), result, session, practice)


@router.post("/debug")
async def debug(
    body: DebugRequest, user: CurrentUser, session: Session, coding: Coding, practice: Practice
) -> DebugResponse:
    """Bugs with line numbers and a corrected program. Pass the `/code/run` result as
    `run` for better answers. Course exercises get hints only (`exercise: true`)."""
    user_id, level = user.id, body.level or user.level
    exercise_code = await CourseRepository(session).exercise_code(body.language)
    await session.commit()
    run = body.run
    run_text = (
        run_output_text(run.outcome, run.stdout, run.stderr, run.compile_output) if run else None
    )
    with ai_errors():
        result = await coding.debug(
            user_id, body.language, body.code, run_text, exercise_code, level
        )
    return await _with_practice(DebugResponse.from_result(result), result, session, practice)


@router.post("/example")
async def example(
    body: TopicInput, user: CurrentUser, session: Session, coding: Coding, practice: Practice
) -> ExampleResponse:
    """A short runnable example that teaches the topic."""
    user_id, level = user.id, body.level or user.level
    await session.commit()
    with ai_errors():
        result = await coding.example(user_id, body.language, body.topic, level)
    return await _with_practice(ExampleResponse.from_result(result), result, session, practice)


@router.post("/practice")
async def practice_questions(
    body: TopicInput, user: CurrentUser, session: Session, coding: Coding, practice: Practice
) -> PracticeResponse:
    """Practice questions with hints and expected output, never solutions."""
    user_id, level = user.id, body.level or user.level
    await session.commit()
    with ai_errors():
        result = await coding.practice(user_id, body.language, body.topic, level)
    return await _with_practice(PracticeResponse.from_result(result), result, session, practice)
