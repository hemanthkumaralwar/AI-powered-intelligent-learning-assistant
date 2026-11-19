"""Turn AI-provider failures into safe HTTP errors (shared by /chat and /coding)."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, status

from app.core.quota import QuotaExceededError
from app.providers.errors import InvalidResponseError, ProviderCallError

logger = logging.getLogger(__name__)


@contextmanager
def ai_errors() -> Iterator[None]:
    """429 over quota (with Retry-After), 502 when the model's reply stayed unusable,
    503 when the provider is unavailable. Provider details never reach the client."""
    try:
        yield
    except QuotaExceededError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            str(exc),
            headers={"Retry-After": str(max(1, round(exc.retry_after)))},
        ) from exc
    except InvalidResponseError as exc:
        logger.warning("AI reply unusable: %s", type(exc).__name__)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The assistant couldn't produce a valid answer. Please try again.",
        ) from exc
    except ProviderCallError as exc:
        logger.warning("AI provider failure: %s", type(exc).__name__)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The assistant is unavailable right now. Please try again shortly.",
        ) from exc
