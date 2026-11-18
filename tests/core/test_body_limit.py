import json

import pytest

from app.core.body_limit import BodySizeLimitMiddleware

pytestmark = pytest.mark.anyio


class EchoApp:
    """Returns the size of the body it received."""

    def __init__(self) -> None:
        self.called = False

    async def __call__(self, scope, receive, send) -> None:
        self.called = True
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": json.dumps({"size": len(body)}).encode()})


async def call(app, path: str, chunks: list[bytes], content_length: int | None = None):
    headers = [] if content_length is None else [(b"content-length", str(content_length).encode())]
    scope = {"type": "http", "path": path, "headers": headers}
    queue = [
        {"type": "http.request", "body": chunk, "more_body": i < len(chunks) - 1}
        for i, chunk in enumerate(chunks)
    ]
    sent: list[dict] = []

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    status = sent[0]["status"]
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, json.loads(body)


def limited(inner) -> BodySizeLimitMiddleware:
    return BodySizeLimitMiddleware(inner, default_limit=10, path_limits={"/upload": 100})


async def test_small_body_is_replayed_unchanged() -> None:
    status, body = await call(limited(EchoApp()), "/x", [b"12345", b"678"], content_length=8)

    assert (status, body) == (200, {"size": 8})


async def test_declared_length_over_limit_is_refused_before_reading() -> None:
    inner = EchoApp()

    status, body = await call(limited(inner), "/x", [b"tiny"], content_length=11)

    assert (status, body) == (413, {"detail": "Request body is too large."})
    assert inner.called is False


async def test_undeclared_streamed_body_over_limit_is_refused() -> None:
    inner = EchoApp()

    status, _ = await call(limited(inner), "/x", [b"123456", b"789012"])

    assert status == 413
    assert inner.called is False


async def test_path_specific_limit() -> None:
    status, body = await call(limited(EchoApp()), "/upload", [b"x" * 100])

    assert (status, body) == (200, {"size": 100})
    assert (await call(limited(EchoApp()), "/upload", [b"x" * 101]))[0] == 413


async def test_bad_content_length_header_falls_back_to_counting() -> None:
    app = limited(EchoApp())
    scope = {"type": "http", "path": "/x", "headers": [(b"content-length", b"abc")]}
    messages = [{"type": "http.request", "body": b"1234567890123", "more_body": False}]
    sent: list[dict] = []

    async def receive():
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    assert sent[0]["status"] == 413


async def test_disconnect_before_body_gives_empty_body() -> None:
    status, body = await call(limited(EchoApp()), "/x", [])

    assert (status, body) == (200, {"size": 0})


async def test_non_http_scopes_pass_through() -> None:
    seen: list[str] = []

    async def inner(scope, receive, send) -> None:
        seen.append(scope["type"])

    await limited(inner)({"type": "lifespan"}, None, None)

    assert seen == ["lifespan"]
