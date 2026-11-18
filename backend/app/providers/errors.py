"""Errors shared by every external AI provider (LLMs, embeddings, later the code runner).

Messages carry only status codes and error kinds, never prompt text, responses, or keys,
so callers can log them or turn them into HTTP errors safely.
"""


class ProviderCallError(Exception):
    """Base class for every failure raised when calling an external provider."""


class ProviderConfigurationError(ProviderCallError):
    """The selected provider is missing required settings (e.g. an API key)."""


class RateLimitedError(ProviderCallError):
    """The provider rejected the request because a quota or rate limit was hit."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ProviderTimeoutError(ProviderCallError):
    """The provider did not answer within the configured timeout."""


class ProviderUnavailableError(ProviderCallError):
    """Transient failure: 5xx response or network/connection problem."""


class ProviderRequestError(ProviderCallError):
    """Non-retryable failure such as bad credentials or an invalid request."""


class InvalidResponseError(ProviderCallError):
    """The provider answered, but the content was empty, malformed, or off-contract."""


RETRYABLE_ERRORS: tuple[type[ProviderCallError], ...] = (
    RateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
