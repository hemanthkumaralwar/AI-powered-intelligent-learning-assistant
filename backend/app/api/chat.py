"""Course questions answered from the course materials, with citations and history."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.api.ai_errors import ai_errors
from app.api.deps import CurrentUser, Session
from app.api.schemas.chat import AskRequest, AskResponse, SessionDetail, SessionSummary
from app.chat.service import (
    ChatError,
    ChatService,
    CourseNotFoundError,
    SessionForbiddenError,
    SessionFullError,
    SessionNotFoundError,
)
from app.db.errors import DuplicateError

router = APIRouter(prefix="/chat", tags=["chat"])

_CHAT_ERRORS: dict[type[ChatError], tuple[int, str]] = {
    CourseNotFoundError: (status.HTTP_404_NOT_FOUND, "Course not found"),
    SessionNotFoundError: (status.HTTP_404_NOT_FOUND, "Chat not found"),
    SessionForbiddenError: (status.HTTP_403_FORBIDDEN, "This chat belongs to another user"),
    SessionFullError: (
        status.HTTP_409_CONFLICT,
        "This chat is full; start a new chat to keep asking questions.",
    ),
}


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chats


Chats = Annotated[ChatService, Depends(get_chat_service)]


def _http_error(exc: ChatError) -> HTTPException:
    code, detail = _CHAT_ERRORS[type(exc)]
    return HTTPException(code, detail)


@router.post("/ask")
async def ask(body: AskRequest, user: CurrentUser, session: Session, chats: Chats) -> AskResponse:
    """Answer from the course, or say it is not covered (`grounded: false`). Pass the
    returned `session_id` back to ask a follow-up in the same conversation."""
    user_id = user.id
    # Hand back the connection that loaded the user: the provider calls below are slow
    # and the pool is small. ChatService opens its own short transactions.
    await session.commit()
    try:
        with ai_errors():
            reply = await chats.ask(user_id, body.question, body.course_id, body.session_id)
    except ChatError as exc:
        raise _http_error(exc) from exc
    except DuplicateError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This chat changed while answering; please ask again.",
        ) from exc
    return AskResponse.from_reply(reply)


@router.get("/sessions")
async def list_sessions(
    user: CurrentUser,
    session: Session,
    chats: Chats,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SessionSummary]:
    """Your chats, most recently active first."""
    sessions = await chats.list_sessions(session, user.id, limit, offset)
    return [SessionSummary.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}")
async def session_history(
    session_id: uuid.UUID, user: CurrentUser, session: Session, chats: Chats
) -> SessionDetail:
    """One of your chats with all its messages. Other users' chats are 403."""
    try:
        chat, messages = await chats.history(session, user.id, session_id)
    except ChatError as exc:
        raise _http_error(exc) from exc
    return SessionDetail.model_validate(
        {**SessionSummary.model_validate(chat).model_dump(), "messages": messages}
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID, user: CurrentUser, session: Session, chats: Chats
) -> Response:
    """Delete one of your chats and all its messages. Other users' chats are 403."""
    try:
        await chats.delete(session, user.id, session_id)
    except ChatError as exc:
        raise _http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
