import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Role, User
from app.db.repositories._integrity import unique_violation_as


def normalize_username(username: str) -> str:
    """Usernames are case-insensitive: "Asha" and "asha" are the same account."""
    return username.strip().lower()


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, username: str, password_hash: str, role: Role) -> User:
        """Create a user. Raises `DuplicateError` if the username is taken."""
        user = User(username=normalize_username(username), password_hash=password_hash, role=role)
        self._session.add(user)
        with unique_violation_as("username already exists"):
            await self._session.flush()
        return user

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def set_level(self, user: User, level: str) -> User:
        user.level = level
        await self._session.flush()
        return user

    async def get_by_username(self, username: str) -> User | None:
        query = select(User).where(User.username == normalize_username(username))
        return await self._session.scalar(query)
