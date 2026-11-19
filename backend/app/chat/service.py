"""`ChatService`: sessions, ownership and history around `AnswerService`.

`ask` runs two short transactions of its own around the provider calls (load before,
save after), so a pooled connection is never held while the model thinks; a failed
answer saves nothing and the student simply asks again. The quick read and delete
paths use the request's own database session instead of taking a second connection.
"""

import uuid
from dataclasses import asdict, dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage as StoredMessage
from app.db.models import ChatSession
from app.db.repositories.chats import ChatRepository, NewMessage
from app.db.repositories.courses import CourseRepository
from app.db.session import Database
from app.llm.base import ChatMessage
from app.llm.prompt_levels import DEFAULT_LEVEL, Level
from app.rag.answer import Answer, AnswerService
from app.rag.condense import HISTORY_MESSAGES

# One question and one answer per exchange: 50 exchanges per session, which bounds
# free-tier storage and keeps a session a reviewable size.
MAX_MESSAGES_PER_SESSION = 100
TITLE_CHARS = 80


class ChatError(Exception):
    """Base for the errors the chat endpoints turn into HTTP responses."""


class CourseNotFoundError(ChatError):
    pass


class SessionNotFoundError(ChatError):
    pass


class SessionForbiddenError(ChatError):
    """The session exists but belongs to someone else."""


class SessionFullError(ChatError):
    pass


@dataclass(frozen=True)
class ChatReply:
    session_id: uuid.UUID
    answer: Answer


class ChatService:
    def __init__(self, database: Database, answers: AnswerService) -> None:
        self._database = database
        self._answers = answers

    async def ask(
        self,
        user_id: uuid.UUID,
        question: str,
        course_id: str | None = None,
        session_id: uuid.UUID | None = None,
        level: Level = DEFAULT_LEVEL,
    ) -> ChatReply:
        """Answer `question` in `session_id` (a new session when None) and save the exchange.

        Raises the `ChatError`s above, `QuotaExceededError`, `ProviderCallError`, and
        `DuplicateError` if the same session is written concurrently.
        """
        history, position = [], 0
        async with self._database.session() as db:
            if course_id is not None and not await CourseRepository(db).exists(course_id):
                raise CourseNotFoundError(course_id)
            if session_id is not None:
                repo = ChatRepository(db)
                await _owned(repo, session_id, user_id)
                position = await repo.count_messages(session_id)
                if position + 2 > MAX_MESSAGES_PER_SESSION:
                    raise SessionFullError(session_id)
                history = [
                    _as_turn(m) for m in await repo.recent_messages(session_id, HISTORY_MESSAGES)
                ]

        answer = await self._answers.ask(user_id, question, course_id, history, level)

        async with self._database.session() as db:
            repo = ChatRepository(db)
            if session_id is None:
                session_id = (await repo.create_session(user_id, _title(question))).id
            await repo.add_messages(session_id, position, _exchange(question, answer))
        return ChatReply(session_id, answer)

    @staticmethod
    async def list_sessions(
        db: AsyncSession, user_id: uuid.UUID, limit: int, offset: int = 0
    ) -> list[ChatSession]:
        return await ChatRepository(db).list_sessions(user_id, limit, offset)

    @staticmethod
    async def history(
        db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> tuple[ChatSession, list[StoredMessage]]:
        repo = ChatRepository(db)
        chat = await _owned(repo, session_id, user_id)
        return chat, await repo.messages(session_id)

    @staticmethod
    async def delete(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        repo = ChatRepository(db)
        await _owned(repo, session_id, user_id)
        await repo.delete_session(session_id)


async def _owned(repo: ChatRepository, session_id: uuid.UUID, user_id: uuid.UUID) -> ChatSession:
    """The session if `user_id` owns it. Nobody else may read it, admins included."""
    chat = await repo.get_session(session_id)
    if chat is None:
        raise SessionNotFoundError(session_id)
    if chat.user_id != user_id:
        raise SessionForbiddenError(session_id)
    return chat


def _as_turn(message: StoredMessage) -> ChatMessage:
    role = "user" if message.role == "user" else "assistant"
    return ChatMessage(role=role, content=message.content)


def _title(question: str) -> str:
    line = " ".join(question.split())
    return line if len(line) <= TITLE_CHARS else line[: TITLE_CHARS - 1] + "…"


def _exchange(question: str, answer: Answer) -> list[NewMessage]:
    return [
        NewMessage(role="user", content=question, standalone=answer.standalone),
        NewMessage(
            role="assistant",
            content=answer.text,
            grounded=answer.grounded,
            citations=[asdict(c) | {"link": c.link} for c in answer.citations],
        ),
    ]
