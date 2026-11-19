"""HTTP error responses shared by several routers."""

from fastapi import HTTPException, status

from app.core.quota import QuotaExceededError


def too_many_requests(exc: QuotaExceededError) -> HTTPException:
    """429 with the quota's own message and a whole-second Retry-After (at least 1)."""
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        str(exc),
        headers={"Retry-After": str(max(1, round(exc.retry_after)))},
    )
