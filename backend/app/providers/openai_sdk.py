"""OpenAI SDK plumbing shared by the LLM and embedding adapters."""

from collections.abc import Iterator
from contextlib import contextmanager

import openai

from app.providers.errors import (
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)


def make_openai_client(api_key: str, timeout_seconds: float) -> openai.AsyncOpenAI:
    # max_retries=0: our retry policy handles retries.
    return openai.AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=0)


@contextmanager
def translate_openai_errors() -> Iterator[None]:
    """Re-raise OpenAI SDK errors as `app.providers.errors` types."""
    try:
        yield
    except openai.APIError as exc:
        raise map_api_error(exc) from exc


def map_api_error(exc: openai.APIError) -> Exception:
    # Order matters: APITimeoutError is a subclass of APIConnectionError.
    if isinstance(exc, openai.APITimeoutError):
        return ProviderTimeoutError("openai request timed out")
    if isinstance(exc, openai.APIConnectionError):
        return ProviderUnavailableError("openai connection failed")
    if isinstance(exc, openai.RateLimitError):
        return RateLimitedError("openai rate limit reached", parse_retry_after(exc))
    if isinstance(exc, openai.InternalServerError):
        return ProviderUnavailableError(f"openai server error {exc.status_code}")
    status = getattr(exc, "status_code", None)
    return ProviderRequestError(f"openai request failed with status {status}")


def parse_retry_after(exc: openai.APIStatusError) -> float | None:
    try:
        return float(exc.response.headers["retry-after"])
    except (KeyError, ValueError):
        return None
