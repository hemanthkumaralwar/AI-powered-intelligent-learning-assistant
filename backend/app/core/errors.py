"""Global error handling: full details go to the server log, never to the client."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

INTERNAL_ERROR_DETAIL = "Internal server error"


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log the stack trace server-side and return a generic 500 body."""
    # Method and path only: query strings and bodies may carry personal data.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": INTERNAL_ERROR_DETAIL})


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the catch-all handler; HTTPException keeps FastAPI's default handling."""
    app.add_exception_handler(Exception, handle_unexpected_error)
