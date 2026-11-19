"""Google Gemini SDK plumbing shared by the LLM and embedding adapters."""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx2
from google import genai
from google.genai import errors, types

from app.providers.errors import (
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)

_RETRY_INFO_TYPE = "type.googleapis.com/google.rpc.RetryInfo"
_DURATION = re.compile(r"^(\d+(?:\.\d+)?)s$")


def make_gemini_client(api_key: str, timeout_seconds: float) -> genai.Client:
    # The SDK does not retry by default; our retry policy handles it.
    return genai.Client(
        api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000))
    )


@contextmanager
def translate_gemini_errors() -> Iterator[None]:
    """Re-raise Gemini SDK and transport errors as `app.providers.errors` types."""
    try:
        yield
    except errors.APIError as exc:
        raise map_api_error(exc) from exc
    except httpx2.TimeoutException as exc:
        raise ProviderTimeoutError("gemini request timed out") from exc
    except httpx2.TransportError as exc:
        raise ProviderUnavailableError("gemini connection failed") from exc


def map_api_error(exc: errors.APIError) -> Exception:
    if exc.code == 429:
        return RateLimitedError(
            "gemini rate limit reached",
            parse_retry_delay(exc.details),
            daily=is_daily_quota(exc.details),
        )
    if exc.code is not None and exc.code >= 500:
        return ProviderUnavailableError(f"gemini server error {exc.code}")
    return ProviderRequestError(f"gemini request failed with status {exc.code}")


def is_daily_quota(details: Any) -> bool:
    """True when a QuotaFailure names a per-day quota (e.g. "...RequestsPerDay...")."""
    return any("PerDay" in str(v.get("quotaId", "")) for v in _quota_violations(details))


def _quota_violations(details: Any) -> list[dict[str, Any]]:
    error = details.get("error") if isinstance(details, dict) else None
    entries = error.get("details") if isinstance(error, dict) else None
    return [
        violation
        for entry in (entries if isinstance(entries, list) else [])
        if isinstance(entry, dict) and entry.get("@type", "").endswith("QuotaFailure")
        for violation in entry.get("violations") or []
        if isinstance(violation, dict)
    ]


def parse_retry_delay(details: Any) -> float | None:
    """Read the RetryInfo delay (e.g. "37s") from a Gemini error body, if present."""
    error = details.get("error") if isinstance(details, dict) else None
    entries = error.get("details") if isinstance(error, dict) else None
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("@type") == _RETRY_INFO_TYPE:
            match = _DURATION.match(str(entry.get("retryDelay", "")))
            if match:
                return float(match.group(1))
    return None
