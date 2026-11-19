import pytest

from app.ingestion.errors import FileTooLargeError, InvalidUploadError, UnsupportedFileTypeError
from app.ingestion.files import MAX_UPLOAD_BYTES, check_size, require_course_json, safe_filename


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("course.json", "course.json"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\x\\course.json", "course.json"),
        ("evil\r\nX-Header: 1.json", "evilX-Header: 1.json"),
        ("..", "upload"),
        ("", "upload"),
        (None, "upload"),
        ("a" * 300 + ".json", "a" * 255),
    ],
)
def test_safe_filename(raw: str | None, expected: str) -> None:
    assert safe_filename(raw) == expected


@pytest.mark.parametrize("name", ["course.json", "COURSE.JSON", "x.y.json"])
def test_course_json_is_accepted(name: str) -> None:
    require_course_json(name)


@pytest.mark.parametrize(
    "name", ["notes.txt", "slides.pdf", "notes.docx", "virus.exe", "noextension", "json"]
)
def test_everything_else_must_be_converted_first(name: str) -> None:
    with pytest.raises(UnsupportedFileTypeError, match="Convert other material to course JSON"):
        require_course_json(name)


def test_size_limits() -> None:
    check_size(b"x" * MAX_UPLOAD_BYTES)
    with pytest.raises(FileTooLargeError):
        check_size(b"x" * (MAX_UPLOAD_BYTES + 1))
    with pytest.raises(InvalidUploadError, match="empty"):
        check_size(b"")
