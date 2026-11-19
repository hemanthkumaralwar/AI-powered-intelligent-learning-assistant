"""Turn AI-provider failures into safe HTTP errors (shared by /chat and /coding)."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import HTTPException, status

from app.api.http_errors import too_many_requests
from app.core.quota import QuotaExceededError
from app.providers.errors import InvalidResponseError, ProviderCallError, ProviderTimeoutError

logger = logging.getLogger(__name__)


@contextmanager
def ai_errors() -> Iterator[None]:
    """429 over quota (with Retry-After), 502 when the model's reply stayed unusable,
    504 when the provider took too long, 503 when it is unavailable. Provider details
    never reach the client."""
    try:
        yield
    except QuotaExceededError as exc:
        raise too_many_requests(exc) from exc
    except ProviderTimeoutError as exc:
        logger.warning("AI provider timed out")
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT,
            "The assistant took too long to answer. Please try again.",
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
