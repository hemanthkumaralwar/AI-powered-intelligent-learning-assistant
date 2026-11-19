"""Reasons shown on a failed document (admins see them in GET /admin/documents).

Short and fixed: never exception text, which can carry provider responses or internals.
"""

from app.ingestion.chunking import ChunkTooLargeError
from app.providers.errors import (
    InvalidResponseError,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

DEFAULT_FAILURE_REASON = "Indexing failed unexpectedly; see server logs, then re-index."

# Not failures: the document stays `pending` and resumes on its own.
WAITING_FOR_DAILY_QUOTA = (
    "Waiting for the daily embedding quota (resets at midnight Pacific time); "
    "indexing resumes automatically."
)
WAITING_FOR_RATE_LIMIT = "Waiting for the embedding rate limit; indexing resumes automatically."

FAILURE_REASONS: tuple[tuple[type[Exception], str], ...] = (
    (ProviderTimeoutError, "Embedding service timed out; re-index later."),
    (ProviderUnavailableError, "Embedding service unavailable; re-index later."),
    (ProviderConfigurationError, "Embedding service is not configured (missing API key)."),
    (ProviderRequestError, "Embedding service rejected the request; check its settings."),
    (InvalidResponseError, "Embedding service returned an unexpected reply; re-index later."),
    (ChunkTooLargeError, "A section of this course is too large to index."),
)
