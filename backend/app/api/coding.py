"""Coding assistant: explain, debug, example and practice, for any logged-in user.

Each endpoint hands its database connection back before the slow model call (the pool
is small); only /debug reads the database first, to recognise course exercises.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.ai_errors import ai_errors
from app.api.deps import CurrentUser, Session
from app.api.schemas.coding import (
    CodeInput,
    DebugRequest,
    DebugResponse,
    ExampleResponse,
    ExplainResponse,
    PracticeResponse,
    TopicInput,
)
from app.coding.prompts import run_output_text
from app.coding.service import CodingService
from app.db.repositories.courses import CourseRepository

router = APIRouter(prefix="/coding", tags=["coding"])


def get_coding_service(request: Request) -> CodingService:
    return request.app.state.coding


Coding = Annotated[CodingService, Depends(get_coding_service)]


@router.post("/explain")
async def explain(
    body: CodeInput, user: CurrentUser, session: Session, coding: Coding
) -> ExplainResponse:
    """Line-by-line explanation of the code."""
    user_id, level = user.id, body.level or user.level
    await session.commit()
    with ai_errors():
        result = await coding.explain(user_id, body.language, body.code, level)
    return ExplainResponse.from_result(result)


@router.post("/debug")
async def debug(
    body: DebugRequest, user: CurrentUser, session: Session, coding: Coding
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
    return DebugResponse.from_result(result)


@router.post("/example")
async def example(
    body: TopicInput, user: CurrentUser, session: Session, coding: Coding
) -> ExampleResponse:
    """A short runnable example that teaches the topic."""
    user_id, level = user.id, body.level or user.level
    await session.commit()
    with ai_errors():
        result = await coding.example(user_id, body.language, body.topic, level)
    return ExampleResponse.from_result(result)


@router.post("/practice")
async def practice(
    body: TopicInput, user: CurrentUser, session: Session, coding: Coding
) -> PracticeResponse:
    """Practice questions with hints and expected output, never solutions."""
    user_id, level = user.id, body.level or user.level
    await session.commit()
    with ai_errors():
        result = await coding.practice(user_id, body.language, body.topic, level)
    return PracticeResponse.from_result(result)
