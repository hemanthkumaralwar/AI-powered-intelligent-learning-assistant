"""Error mapping for plain-HTTP providers (those without an official SDK)."""

from collections.abc import Iterator
from contextlib import contextmanager

import httpx2

from app.providers.errors import (
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)

# Identifies the app to third-party services without any personal or contact details.
USER_AGENT = "ArchintX-Learning-Assistant/0.1"


@contextmanager
def translate_http_errors(provider: str) -> Iterator[None]:
    """Re-raise httpx2 transport failures as `app.providers.errors` types."""
    try:
        yield
    except httpx2.TimeoutException as exc:
        raise ProviderTimeoutError(f"{provider} request timed out") from exc
    except httpx2.TransportError as exc:
        raise ProviderUnavailableError(f"{provider} connection failed") from exc


def check_status(response: httpx2.Response, provider: str) -> None:
    """Raise the matching provider error for a non-2xx response."""
    status = response.status_code
    if status == 429:
        raise RateLimitedError(f"{provider} rate limit reached", _retry_after(response))
    if status >= 500:
        raise ProviderUnavailableError(f"{provider} server error {status}")
    if status >= 400:
        raise ProviderRequestError(f"{provider} request failed with status {status}")


def _retry_after(response: httpx2.Response) -> float | None:
    try:
        return float(response.headers["retry-after"])
    except (KeyError, ValueError):
        return None
