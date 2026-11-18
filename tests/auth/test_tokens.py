import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.errors import InvalidTokenError
from app.auth.tokens import ALGORITHM, TokenService

SECRET = "s" * 64
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
USER_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def service(clock: FixedClock | None = None) -> TokenService:
    return TokenService(SECRET, timedelta(minutes=60), clock or FixedClock(NOW))


def test_issued_token_round_trips_to_the_user_id() -> None:
    issued = service().issue(USER_ID)

    assert issued.expires_in == 3600
    assert service().subject(issued.access_token) == USER_ID


def test_token_carries_only_standard_claims() -> None:
    claims = jwt.decode(
        service().issue(USER_ID).access_token,
        SECRET,
        algorithms=[ALGORITHM],
        options={"verify_exp": False, "verify_iat": False},
    )

    assert set(claims) == {"sub", "iat", "exp"}


def test_token_expires_exactly_at_ttl() -> None:
    clock = FixedClock(NOW)
    tokens = service(clock)
    token = tokens.issue(USER_ID).access_token

    clock.now = NOW + timedelta(minutes=59, seconds=59)
    assert tokens.subject(token) == USER_ID

    clock.now = NOW + timedelta(minutes=60)
    with pytest.raises(InvalidTokenError, match="expired"):
        tokens.subject(token)


def forge(claims: dict, secret: str = SECRET, algorithm: str = ALGORITHM) -> str:
    return jwt.encode(claims, secret, algorithm=algorithm)


VALID = {"sub": str(USER_ID), "iat": NOW, "exp": NOW + timedelta(hours=1)}


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not.a.token",
        forge(VALID, secret="t" * 64),
        forge({k: v for k, v in VALID.items() if k != "exp"}),
        forge({k: v for k, v in VALID.items() if k != "sub"}),
        forge({k: v for k, v in VALID.items() if k != "iat"}),
        forge({**VALID, "sub": "not-a-uuid"}),
        forge(VALID, algorithm="HS512"),
        jwt.encode(VALID, None, algorithm="none"),
    ],
    ids=[
        "empty",
        "garbage",
        "wrong-secret",
        "no-exp",
        "no-sub",
        "no-iat",
        "bad-sub",
        "other-algorithm",
        "alg-none",
    ],
)
def test_bad_tokens_are_rejected(token: str) -> None:
    with pytest.raises(InvalidTokenError):
        service().subject(token)


def test_tampered_payload_is_rejected() -> None:
    header, _, signature = service().issue(USER_ID).access_token.split(".")
    other = forge({**VALID, "sub": str(uuid.uuid4())}).split(".")[1]

    with pytest.raises(InvalidTokenError):
        service().subject(f"{header}.{other}.{signature}")
