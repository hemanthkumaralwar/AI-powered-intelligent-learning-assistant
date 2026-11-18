"""Translate Postgres unique violations into `DuplicateError` (internal helper)."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError

from app.db.errors import DuplicateError

_UNIQUE_VIOLATION = "23505"


@contextmanager
def unique_violation_as(message: str) -> Iterator[None]:
    """Raise `DuplicateError(message)` for unique violations; other errors pass through."""
    try:
        yield
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
            # Only our own message: the driver's text echoes the conflicting value.
            raise DuplicateError(message) from exc
        raise
