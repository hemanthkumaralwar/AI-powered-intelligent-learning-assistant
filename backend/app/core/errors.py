"""Global error handling: full details go to the server log, never to the client."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

INTERNAL_ERROR_DETAIL = "Internal server error"
SECRET_FIELDS = frozenset({"password"})


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log the stack trace server-side and return a generic 500 body."""
    # Method and path only: query strings and bodies may carry personal data.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": INTERNAL_ERROR_DETAIL})


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 with where and why, but never the submitted value.

    FastAPI's default echoes each bad field's `input`, which would send a rejected
    password straight back in the response body.
    """
    errors = [
        {"loc": list(error["loc"]), "msg": _safe_message(error), "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": errors})


def _safe_message(error: dict) -> str:
    # Pydantic's length messages quote the actual length ("... not 5"), which would
    # reveal how long a rejected password was.
    if any(part in SECRET_FIELDS for part in error["loc"]):
        return "Invalid value"
    return error["msg"]


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the catch-all and validation handlers; HTTPException keeps FastAPI's default."""
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
