"""Signed access tokens (JWT, HS256). They carry only the user id; roles are read from the
database on every request so role changes and deleted accounts take effect at once."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.auth.errors import InvalidTokenError

# Pinned on decode: a token must never be able to choose its own algorithm (e.g. "none").
ALGORITHM = "HS256"
REQUIRED_CLAIMS = ["exp", "iat", "sub"]

type Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class IssuedToken:
    access_token: str
    expires_in: int


class TokenService:
    def __init__(self, secret: str, ttl: timedelta, clock: Clock = utc_now) -> None:
        self._secret = secret
        self._ttl = ttl
        self._clock = clock

    def issue(self, user_id: uuid.UUID) -> IssuedToken:
        now = self._clock()
        claims = {"sub": str(user_id), "iat": now, "exp": now + self._ttl}
        token = jwt.encode(claims, self._secret, algorithm=ALGORITHM)
        return IssuedToken(access_token=token, expires_in=int(self._ttl.total_seconds()))

    def subject(self, token: str) -> uuid.UUID:
        """Return the user id in a valid token; raise `InvalidTokenError` otherwise."""
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                # Expiry is checked below against the injected clock, so tests are exact.
                options={"require": REQUIRED_CLAIMS, "verify_exp": False, "verify_iat": False},
            )
            expires = datetime.fromtimestamp(claims["exp"], UTC)
            user_id = uuid.UUID(claims["sub"])
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError) as exc:
            raise InvalidTokenError("invalid token") from exc
        if expires <= self._clock():
            raise InvalidTokenError("token expired")
        return user_id
