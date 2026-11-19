"""Course questions answered from the course materials, with citations."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, Session
from app.api.schemas.chat import AskRequest, AskResponse
from app.core.quota import QuotaExceededError
from app.db.repositories.courses import CourseRepository
from app.providers.errors import ProviderCallError
from app.rag.answer import AnswerService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def get_answer_service(request: Request) -> AnswerService:
    return request.app.state.answers


Answers = Annotated[AnswerService, Depends(get_answer_service)]


@router.post("/ask")
async def ask(
    body: AskRequest, user: CurrentUser, session: Session, answers: Answers
) -> AskResponse:
    """Answer from the course, or say it is not covered (`grounded: false`)."""
    if body.course_id is not None and not await CourseRepository(session).exists(body.course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    user_id = user.id
    # Hand the database connection back before the slow provider calls: the pool is
    # small, and nothing below needs the database.
    await session.commit()
    try:
        answer = await answers.ask(user_id, body.question, body.course_id)
    except QuotaExceededError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            str(exc),
            headers={"Retry-After": str(max(1, round(exc.retry_after)))},
        ) from exc
    except ProviderCallError as exc:
        logger.warning("chat provider failure: %s", type(exc).__name__)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The assistant is unavailable right now. Please try again shortly.",
        ) from exc
    return AskResponse.from_answer(answer)
