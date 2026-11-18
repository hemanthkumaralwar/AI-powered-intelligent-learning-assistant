"""Request and response bodies for /code."""

from pydantic import BaseModel, Field, field_validator

from app.runner.base import Language, Outcome

# Byte limits, not character limits: what the runner services meter is bytes.
MAX_CODE_BYTES = 20 * 1024
MAX_STDIN_BYTES = 8 * 1024


class CodeRequest(BaseModel):
    language: Language
    code: str = Field(min_length=1)

    @field_validator("code")
    @classmethod
    def _code_size(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Code must not be empty")
        if len(value.encode()) > MAX_CODE_BYTES:
            raise ValueError("Code must be at most 20 KB")
        return value


class RunCodeRequest(CodeRequest):
    stdin: str = ""

    @field_validator("stdin")
    @classmethod
    def _stdin_size(cls, value: str) -> str:
        if len(value.encode()) > MAX_STDIN_BYTES:
            raise ValueError("Input must be at most 8 KB")
        return value


class RunCodeResponse(BaseModel):
    outcome: Outcome
    stdout: str
    stderr: str
    compile_output: str
    exit_code: int | None
    time_ms: int | None
    provider: str
    truncated: bool


class ShareCodeRequest(CodeRequest):
    pass


class ShareCodeResponse(BaseModel):
    url: str
    warning: str = (
        "This link is public and permanent: anyone with it can see the code. "
        "Do not include personal information."
    )
