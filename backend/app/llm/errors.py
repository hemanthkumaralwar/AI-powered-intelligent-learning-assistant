"""Provider-neutral LLM errors.

Messages carry only status codes and error kinds, never prompt text, responses, or keys,
so callers can log them or turn them into HTTP errors safely.
"""


class LLMError(Exception):
    """Base class for every failure raised by the LLM layer."""


class LLMConfigurationError(LLMError):
    """The selected provider is missing required settings (e.g. an API key)."""


class RateLimitedError(LLMError):
    """The provider rejected the request because a quota or rate limit was hit."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMTimeoutError(LLMError):
    """The provider did not answer within the configured timeout."""


class ProviderUnavailableError(LLMError):
    """Transient failure: 5xx response or network/connection problem."""


class ProviderError(LLMError):
    """Non-retryable provider failure such as bad credentials or an invalid request."""


class InvalidResponseError(LLMError):
    """The provider answered, but the content was empty, not JSON, or off-schema."""


RETRYABLE_ERRORS: tuple[type[LLMError], ...] = (
    RateLimitedError,
    LLMTimeoutError,
    ProviderUnavailableError,
)
