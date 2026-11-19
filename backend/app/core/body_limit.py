"""Reject oversized request bodies before any parsing happens.

Starlette parses multipart bodies before endpoint code runs, so a size check inside an
upload handler comes too late: a huge body would already be spooled to disk. This ASGI
middleware counts bytes as they arrive and answers 413 as soon as the limit is passed.
Bodies within the limit are buffered and replayed to the app unchanged.

Paths with a large limit (uploads) can also require a bearer token header: a request
without one is refused before its body is read, so anonymous clients cannot make the
server buffer megabytes. The token itself is still checked by the endpoint.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from starlette.responses import JSONResponse

Scope = dict[str, Any]
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

_TOO_LARGE = JSONResponse({"detail": "Request body is too large."}, status_code=413)
_NOT_AUTHENTICATED = JSONResponse(
    {"detail": "Not authenticated"}, status_code=401, headers={"WWW-Authenticate": "Bearer"}
)


class BodySizeLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        default_limit: int,
        path_limits: Mapping[str, int],
        bearer_required: frozenset[str] = frozenset(),
    ) -> None:
        self._app = app
        self._default_limit = default_limit
        self._path_limits = dict(path_limits)
        self._bearer_required = bearer_required

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        if scope["path"] in self._bearer_required and not _has_bearer(scope):
            await _NOT_AUTHENTICATED(scope, receive, send)
            return
        limit = self._path_limits.get(scope["path"], self._default_limit)
        if _declared_length(scope) > limit:
            await _TOO_LARGE(scope, receive, send)
            return
        body = await _read_body(receive, limit)
        if body is None:
            await _TOO_LARGE(scope, receive, send)
            return
        await self._app(scope, _replay(body, receive), send)


def _has_bearer(scope: Scope) -> bool:
    for name, value in scope.get("headers", []):
        if name == b"authorization":
            return value[:7].lower() == b"bearer " and len(value.strip()) > 7
    return False


def _declared_length(scope: Scope) -> int:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return 0
    return 0


async def _read_body(receive: Receive, limit: int) -> bytes | None:
    """The whole body, or None as soon as it exceeds `limit` (never trusting headers)."""
    chunks: list[bytes] = []
    size = 0
    while True:
        message = await receive()
        if message["type"] != "http.request":
            break  # client disconnected; the app will see an empty body
        chunk = message.get("body", b"")
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _replay(body: bytes, receive: Receive) -> Receive:
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()  # later calls wait for the client's disconnect

    return replay
