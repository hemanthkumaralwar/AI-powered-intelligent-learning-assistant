"""File-level checks for uploads: size, type and filename (pure functions).

Only course JSON is accepted. Other material (DOCX, PDF, TXT) is converted to course JSON
outside this app, so every course follows the same schema.
"""

import re
from pathlib import PurePosixPath, PureWindowsPath

from app.ingestion.errors import FileTooLargeError, InvalidUploadError, UnsupportedFileTypeError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Control characters (incl. CR/LF) are stripped so a filename can never break a header.
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def check_size(content: bytes) -> None:
    if not content:
        raise InvalidUploadError("The file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise FileTooLargeError("The file is larger than 10 MB.")


def safe_filename(raw: str | None) -> str:
    """Base name only, no control characters, at most 255 characters."""
    name = PureWindowsPath(PurePosixPath(raw or "").name).name
    name = _CONTROL.sub("", name).strip().strip(".")
    return name[:255] or "upload"


def require_course_json(filename: str) -> None:
    """Accept .json only; the content itself is validated by `parse_course`."""
    if PurePosixPath(filename.lower()).suffix != ".json":
        raise UnsupportedFileTypeError(
            "Only course JSON files are accepted. Convert other material to course JSON first."
        )
