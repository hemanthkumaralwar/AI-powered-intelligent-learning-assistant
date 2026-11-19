"""Chat sessions and their messages. Ownership is checked by the caller (ChatService)."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatRole, ChatSession
from app.db.repositories._integrity import unique_violation_as


@dataclass(frozen=True)
class NewMessage:
    role: ChatRole
    content: str
    standalone: str | None = None
    grounded: bool | None = None
    citations: list[dict[str, Any]] | None = None


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_session(self, user_id: uuid.UUID, title: str) -> ChatSession:
        chat = ChatSession(user_id=user_id, title=title)
        self._session.add(chat)
        await self._session.flush()
        return chat

    async def get_session(self, session_id: uuid.UUID) -> ChatSession | None:
        return await self._session.get(ChatSession, session_id)

    async def list_sessions(
        self, user_id: uuid.UUID, limit: int, offset: int = 0
    ) -> list[ChatSession]:
        """A user's sessions, most recently active first."""
        rows = await self._session.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id)
            .limit(limit)
            .offset(offset)
        )
        return list(rows)

    async def count_messages(self, session_id: uuid.UUID) -> int:
        return await self._session.scalar(
            select(func.count()).where(ChatMessage.session_id == session_id)
        )

    async def messages(self, session_id: uuid.UUID) -> list[ChatMessage]:
        rows = await self._session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.position)
        )
        return list(rows)

    async def recent_messages(self, session_id: uuid.UUID, limit: int) -> list[ChatMessage]:
        """The last `limit` messages, oldest first."""
        rows = await self._session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.position.desc())
            .limit(limit)
        )
        return list(reversed(list(rows)))

    async def add_messages(
        self, session_id: uuid.UUID, start: int, messages: Sequence[NewMessage]
    ) -> None:
        """Append `messages` at positions start, start+1, ... and mark the session active.

        A concurrent append to the same session hits the (session, position) unique
        constraint, raising `DuplicateError` instead of interleaving the two exchanges.
        """
        for offset, message in enumerate(messages):
            self._session.add(
                ChatMessage(
                    session_id=session_id,
                    position=start + offset,
                    role=message.role,
                    content=message.content,
                    standalone=message.standalone,
                    grounded=message.grounded,
                    citations=message.citations,
                )
            )
        # Flush the inserts first: the UPDATE below would autoflush them outside this guard.
        with unique_violation_as("the chat changed while this answer was being written"):
            await self._session.flush()
        await self._session.execute(
            update(ChatSession).where(ChatSession.id == session_id).values(updated_at=func.now())
        )

    async def delete_session(self, session_id: uuid.UUID) -> None:
        """Delete a session; its messages go with it (ON DELETE CASCADE)."""
        await self._session.execute(delete(ChatSession).where(ChatSession.id == session_id))
