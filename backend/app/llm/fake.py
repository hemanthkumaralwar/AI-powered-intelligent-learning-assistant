"""Deterministic offline `ChatModel` for tests and for developing without an API key."""

import asyncio
from collections import deque
from collections.abc import Iterable

from app.llm.base import CompletionRequest, LLMResponse

DEFAULT_REPLY = "This is a fake response."


class FakeChatModel:
    """Replays scripted replies in order; an `Exception` in the script is raised instead.

    When the script is used up it answers `default_reply`. Every request is recorded in
    `requests` so tests can assert on what the client sent.
    """

    provider = "fake"
    model = "fake-model"

    def __init__(
        self,
        script: Iterable[str | Exception] = (),
        *,
        default_reply: str = DEFAULT_REPLY,
        delay_seconds: float = 0.0,
    ) -> None:
        self._script = deque(script)
        self._default_reply = default_reply
        self._delay_seconds = delay_seconds
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> LLMResponse:
        self.requests.append(request)
        if self._delay_seconds:
            await asyncio.sleep(self._delay_seconds)
        step = self._script.popleft() if self._script else self._default_reply
        if isinstance(step, Exception):
            raise step
        return LLMResponse(text=step, model=self.model, input_tokens=0, output_tokens=0)
