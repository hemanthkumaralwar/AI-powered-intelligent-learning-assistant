"""Registration, login, and resolving the user behind a token."""

import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.errors import AuthConfigurationError, InvalidCredentialsError, InvalidTokenError
from app.auth.passwords import PasswordHasher
from app.auth.tokens import IssuedToken, TokenService
from app.core.config import Settings
from app.db.models import Role, User
from app.db.repositories.users import UserRepository

logger = logging.getLogger(__name__)


class AuthService:
    """App-lifetime service; each call works inside the caller's database session.

    Logs user ids only: never usernames on failure (people type passwords there),
    passwords, or tokens.
    """

    def __init__(self, hasher: PasswordHasher, tokens: TokenService) -> None:
        self._hasher = hasher
        self._tokens = tokens

    async def register(
        self, session: AsyncSession, username: str, password: str, role: Role = "student"
    ) -> User:
        """Create an account. Raises `DuplicateError` if the username is taken."""
        password_hash = await self._hasher.hash(password)
        user = await UserRepository(session).add(username, password_hash, role)
        logger.info("user registered user_id=%s role=%s", user.id, role)
        return user

    async def login(self, session: AsyncSession, username: str, password: str) -> IssuedToken:
        """Return a token, or raise `InvalidCredentialsError` for any mismatch."""
        user = await UserRepository(session).get_by_username(username)
        if user is None:
            await self._hasher.burn_time(password)
            logger.warning("login failed")
            raise InvalidCredentialsError("invalid username or password")
        if not await self._hasher.verify(user.password_hash, password):
            logger.warning("login failed")
            raise InvalidCredentialsError("invalid username or password")
        logger.info("login succeeded user_id=%s", user.id)
        return self._tokens.issue(user.id)

    async def user_from_token(self, session: AsyncSession, token: str) -> User:
        """Resolve a bearer token to a current user, or raise `InvalidTokenError`."""
        user = await UserRepository(session).get(self._tokens.subject(token))
        if user is None:
            raise InvalidTokenError("user no longer exists")
        return user


def build_auth_service(settings: Settings) -> AuthService:
    if settings.jwt_secret_key is None:
        raise AuthConfigurationError("JWT_SECRET_KEY is required to start the API")
    tokens = TokenService(
        settings.jwt_secret_key.get_secret_value(),
        timedelta(minutes=settings.access_token_minutes),
    )
    return AuthService(PasswordHasher(), tokens)
