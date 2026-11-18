"""File-level checks: size, type, filename and text decoding (pure functions)."""

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from app.ingestion.errors import FileTooLargeError, InvalidUploadError, UnsupportedFileTypeError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
FileKind = Literal["json", "txt"]

_SUPPORTED = {".json": "json", ".txt": "txt"}
_NOT_YET = {".pdf", ".docx"}
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


def file_kind(filename: str) -> FileKind:
    """Decide the type from the extension; the content is checked separately."""
    suffix = PurePosixPath(filename.lower()).suffix
    if suffix in _SUPPORTED:
        return _SUPPORTED[suffix]
    if suffix in _NOT_YET:
        raise UnsupportedFileTypeError("PDF and DOCX uploads are not supported yet.")
    raise UnsupportedFileTypeError("Only .json course files and .txt notes are accepted.")


def decode_text(content: bytes) -> str:
    """UTF-8 text without NUL bytes, so a renamed binary file is rejected."""
    if b"\x00" in content:
        raise InvalidUploadError("The file is not a text file.")
    try:
        text = content.decode("utf-8-sig")  # tolerate a BOM from Windows editors
    except UnicodeDecodeError as exc:
        raise InvalidUploadError("The file is not valid UTF-8 text.") from exc
    if not text.strip():
        raise InvalidUploadError("The file contains no text.")
    return text
