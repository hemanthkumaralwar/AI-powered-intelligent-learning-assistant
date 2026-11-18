import pytest

from app.ingestion.errors import FileTooLargeError, InvalidUploadError, UnsupportedFileTypeError
from app.ingestion.files import MAX_UPLOAD_BYTES, check_size, decode_text, file_kind, safe_filename


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("notes.txt", "notes.txt"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\x\\course.json", "course.json"),
        ("evil\r\nX-Header: 1.txt", "evilX-Header: 1.txt"),
        ("..", "upload"),
        ("", "upload"),
        (None, "upload"),
        ("a" * 300 + ".txt", "a" * 255),
    ],
)
def test_safe_filename(raw: str | None, expected: str) -> None:
    assert safe_filename(raw) == expected


@pytest.mark.parametrize(
    ("name", "kind"), [("c.json", "json"), ("N.TXT", "txt"), ("x.y.json", "json")]
)
def test_supported_kinds(name: str, kind: str) -> None:
    assert file_kind(name) == kind


@pytest.mark.parametrize("name", ["slides.pdf", "notes.docx"])
def test_pdf_and_docx_are_not_supported_yet(name: str) -> None:
    with pytest.raises(UnsupportedFileTypeError, match="not supported yet"):
        file_kind(name)


@pytest.mark.parametrize("name", ["virus.exe", "archive.zip", "noextension", "page.html"])
def test_other_types_are_refused(name: str) -> None:
    with pytest.raises(UnsupportedFileTypeError, match="Only .json"):
        file_kind(name)


def test_size_limits() -> None:
    check_size(b"x" * MAX_UPLOAD_BYTES)
    with pytest.raises(FileTooLargeError):
        check_size(b"x" * (MAX_UPLOAD_BYTES + 1))
    with pytest.raises(InvalidUploadError, match="empty"):
        check_size(b"")


def test_decode_text_accepts_utf8_and_bom() -> None:
    assert decode_text("héllo".encode()) == "héllo"
    assert decode_text(b"\xef\xbb\xbfhi") == "hi"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"MZ\x90\x00\x03\x00binary", "not a text file"),
        (b"\xff\xfe\xfa", "not valid UTF-8"),
        (b"   \n\t ", "contains no text"),
    ],
)
def test_decode_text_rejects_binary_and_empty(content: bytes, message: str) -> None:
    with pytest.raises(InvalidUploadError, match=message):
        decode_text(content)
