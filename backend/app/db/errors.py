"""Errors the database layer raises to its callers.

Anything not translated here propagates and becomes the generic 500 from `app.core.errors`.
"""


class DatabaseConfigurationError(Exception):
    """DATABASE_URL is missing or not a PostgreSQL URL."""


class DuplicateError(Exception):
    """A unique constraint rejected the write (e.g. the username is taken)."""
