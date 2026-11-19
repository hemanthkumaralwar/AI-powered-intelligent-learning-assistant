"""Request and response bodies for /auth. Passwords are `SecretStr` so they never appear
in reprs, logs, or tracebacks."""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.db.repositories.users import normalize_username
from app.llm.prompt_levels import Level

USERNAME_PATTERN = r"^[a-z0-9._-]+$"


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    # 128 is generous for passphrases yet caps the hashing work per request.
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def _normalize(cls, value: object) -> object:
        return normalize_username(value) if isinstance(value, str) else value


class LoginRequest(BaseModel):
    # No pattern here: a login form should not reveal the username rules.
    username: str = Field(min_length=1, max_length=50)
    password: SecretStr = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    role: Literal["admin", "student"]
    level: Level


class UpdateMeRequest(BaseModel):
    # extra="forbid": a body like {"role": "admin"} is rejected, not silently ignored.
    model_config = ConfigDict(extra="forbid")

    level: Level
