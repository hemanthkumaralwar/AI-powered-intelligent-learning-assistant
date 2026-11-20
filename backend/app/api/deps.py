"""Request-scoped dependencies: database session, current user, role checks, and the
guest check for public endpoints."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.http_errors import too_many_requests
from app.auth.errors import InvalidTokenError
from app.auth.service import AuthService
from app.core.cache import TTLCache
from app.core.quota import QuotaExceededError
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


async def allow_guests(
    request: Request,
    session: Session,
    auth: Auth,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """For the public course endpoints (Step 24). A valid token passes freely; anything
    else (no token, or a bad or expired one) is a guest and counts against one app-wide
    guest quota: every guest arrives through the same Streamlit server, so guests cannot
    be told apart, and only a real token can skip the count."""
    if credentials is not None:
        try:
            await auth.user_from_token(session, credentials.credentials)
        except InvalidTokenError:
            pass  # treated as a guest below
        else:
            return
    try:
        request.app.state.guest_quota.consume("guests")
    except QuotaExceededError as exc:
        raise too_many_requests(exc) from exc


GuestOrUser = Depends(allow_guests)


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def get_content_cache(request: Request) -> TTLCache:
    """Course outlines and lessons; admins clear it whenever course content changes."""
    return request.app.state.content_cache


ContentCache = Annotated[TTLCache, Depends(get_content_cache)]
