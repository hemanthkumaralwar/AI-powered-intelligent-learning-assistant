"""Account endpoints: register (students only), login, and who-am-I."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import Auth, CurrentUser, Session
from app.api.http_errors import too_many_requests
from app.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserResponse,
)
from app.auth.errors import InvalidCredentialsError
from app.auth.limits import LoginGuard
from app.core.quota import QuotaExceededError
from app.db.errors import DuplicateError
from app.db.repositories.users import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


def get_login_guard(request: Request) -> LoginGuard:
    return request.app.state.login_guard


Guard = Annotated[LoginGuard, Depends(get_login_guard)]


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, session: Session, auth: Auth, guard: Guard
) -> UserResponse:
    """Create a student account. Admins are only created from ADMIN_USERNAME at startup."""
    try:
        guard.check_registration()
    except QuotaExceededError as exc:
        raise too_many_requests(exc) from exc
    try:
        user = await auth.register(session, body.username, body.password.get_secret_value())
    except DuplicateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken") from exc
    return UserResponse.model_validate(user)


@router.post("/login")
async def login(body: LoginRequest, session: Session, auth: Auth, guard: Guard) -> TokenResponse:
    """Exchange username and password for a bearer token. After repeated failures for one
    username, sign-in for it pauses (429 with Retry-After)."""
    try:
        guard.check_login(body.username)
    except QuotaExceededError as exc:
        raise too_many_requests(exc) from exc
    try:
        issued = await auth.login(session, body.username, body.password.get_secret_value())
    except InvalidCredentialsError as exc:
        guard.record_failure(body.username)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenResponse(access_token=issued.access_token, expires_in=issued.expires_in)


@router.get("/me")
async def me(user: CurrentUser) -> UserResponse:
    """The account the bearer token belongs to."""
    return UserResponse.model_validate(user)


@router.patch("/me")
async def update_me(body: UpdateMeRequest, user: CurrentUser, session: Session) -> UserResponse:
    """Change your own explanation level. Only `level` is accepted: role and username
    cannot be changed here (any other field is a 422)."""
    await UserRepository(session).set_level(user, body.level)
    return UserResponse.model_validate(user)
