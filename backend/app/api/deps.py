"""Request-scoped dependencies: database session, current user, and role checks."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.errors import InvalidTokenError
from app.auth.service import AuthService
from app.db.models import User
from app.db.session import Database

_bearer = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")
_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    """One transaction per request: committed if the endpoint succeeds, else rolled back."""
    async with database.session() as session:
        yield session


# scope="function": commit before the response is sent, so a failed commit can never
# follow a success response the client has already received.
Session = Annotated[AsyncSession, Depends(get_session, scope="function")]
Auth = Annotated[AuthService, Depends(get_auth_service)]


async def require_user(
    session: Session,
    auth: Auth,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Any logged-in user. Missing, bad, or expired tokens all get the same 401."""
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers=_UNAUTHORIZED_HEADERS
        )
    try:
        return await auth.user_from_token(session, credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers=_UNAUTHORIZED_HEADERS,
        ) from exc


CurrentUser = Annotated[User, Depends(require_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
