"""Request and response bodies for /exercises."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.schemas.coding import check_code_size
from app.llm.prompt_levels import Level


class AttemptRequest(BaseModel):
    code: str = Field(min_length=1)
    # Feedback level for this attempt only; omitted, the profile's level is used.
    level: Level | None = None

    @field_validator("code")
    @classmethod
    def _code_size(cls, value: str) -> str:
        return check_code_size(value)


class AttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    passed: bool
    feedback: str
    created_at: datetime
