"""Safe file-download responses."""

from urllib.parse import quote

from fastapi import Response

from app.db.models import Document


def file_response(document: Document, content: bytes) -> Response:
    """Send stored bytes as an attachment.

    The filename goes out RFC 5987-encoded, so no character in it can alter the header;
    `nosniff` stops browsers from treating a text file as HTML.
    """
    return Response(
        content=content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.filename)}",
            "X-Content-Type-Options": "nosniff",
        },
    )
