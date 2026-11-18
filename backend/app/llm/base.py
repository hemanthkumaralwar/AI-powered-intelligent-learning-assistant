"""Provider-neutral request/response types and the adapter contract."""

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Role
    content: str = Field(min_length=1)


class GenerationOptions(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Low default temperature: answers should stay close to the course material.
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=1024, ge=1, le=8192)


class CompletionRequest(BaseModel):
    """What an adapter receives: already-validated messages plus optional JSON schema."""

    model_config = ConfigDict(frozen=True)

    messages: tuple[ChatMessage, ...]
    options: GenerationOptions
    json_schema: dict[str, Any] | None = None


class LLMResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    # True when generation stopped at max_output_tokens, so `text` is incomplete.
    truncated: bool = False


class ChatModel(Protocol):
    """Adapter for one vendor SDK.

    Implementations translate a `CompletionRequest` into a single API call and map
    vendor exceptions onto `app.llm.errors`. They must not retry; `LLMClient` does.
    """

    provider: str
    model: str

    async def complete(self, request: CompletionRequest) -> LLMResponse: ...
