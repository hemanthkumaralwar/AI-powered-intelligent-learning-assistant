"""Small HTTP client for the ArchintX API, kept free of Streamlit so it can be unit tested.

Every failure becomes an `ApiError` whose message is safe to show to a student: no
stack traces, URLs, or server internals. The API's own `detail` messages are shown for
4xx answers, because the API writes them for students; 5xx details never are.
"""

from typing import Any
from urllib.parse import quote, urlsplit

import httpx2

# Render's free tier sleeps when idle; waking takes ~30-60 s, so be patient.
DEFAULT_TIMEOUT_SECONDS = 60.0
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ApiError(Exception):
    """A problem talking to the API, with a message fit for the UI."""


class SessionExpiredError(ApiError):
    """The token is no longer accepted; the user must log in again."""


def validate_base_url(base_url: str) -> str:
    """Require https, except for a backend running on this machine."""
    url = base_url.strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname:
        return url
    if parts.scheme == "http" and parts.hostname in _LOCAL_HOSTS:
        return url
    raise ValueError("API_BASE_URL must be an https:// URL (http:// only for localhost)")


class ApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._http = httpx2.Client(
            base_url=validate_base_url(base_url), timeout=timeout_seconds, transport=transport
        )

    def login(self, username: str, password: str) -> str:
        """Return an access token for valid credentials."""
        response = self._send(
            "POST", "/auth/login", json={"username": username, "password": password}
        )
        if response.status_code == 401:
            raise ApiError("Invalid username or password.")
        if response.status_code == 422:
            raise ApiError("Enter both a username and a password.")
        return self._json(response)["access_token"]

    def me(self, token: str) -> dict[str, Any]:
        """Return the signed-in account (`id`, `username`, `role`, `level`)."""
        return self._authed("GET", "/auth/me", token)

    def set_level(self, token: str, level: str) -> dict[str, Any]:
        """Save the explanation level (beginner, intermediate, advanced) to the profile."""
        return self._authed("PATCH", "/auth/me", token, json={"level": level})

    # ---- course content -------------------------------------------------------------

    def courses(self, token: str) -> list[dict[str, Any]]:
        return self._authed("GET", "/courses", token)

    def course(self, token: str, course_id: str) -> dict[str, Any]:
        """The course outline: modules with their lessons."""
        return self._authed("GET", f"/courses/{quote(course_id, safe='')}", token)

    def lesson(self, token: str, lesson_id: str) -> dict[str, Any]:
        """Lesson content and exercises (starter code and hints, never solutions)."""
        return self._authed("GET", f"/lessons/{quote(lesson_id, safe='')}", token)

    # ---- running code and the coding assistant -------------------------------------

    def run_code(self, token: str, language: str, code: str, stdin: str = "") -> dict[str, Any]:
        """Run on the remote sandbox: `outcome`, `stdout`, `stderr`, `compile_output`..."""
        body = {"language": language, "code": code, "stdin": stdin}
        return self._authed("POST", "/code/run", token, json=body)

    def share_code(self, token: str, language: str, code: str) -> str:
        """A public, permanent Compiler Explorer link (C, C++, Java, Python)."""
        body = {"language": language, "code": code}
        return self._authed("POST", "/code/share", token, json=body)["url"]

    def debug_code(
        self, token: str, language: str, code: str, run: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Issues with line numbers, a summary, and (unless it is a course exercise) a fix.
        `run` is the run result, or {"stdout": pasted} for output from elsewhere."""
        body: dict[str, Any] = {"language": language, "code": code}
        if run is not None:
            body["run"] = run
        return self._authed("POST", "/coding/debug", token, json=body)

    def submit_attempt(self, token: str, exercise_id: str, code: str) -> dict[str, Any]:
        """Grade an exercise attempt: `passed` and hint-style `feedback` (never the answer)."""
        path = f"/exercises/{quote(exercise_id, safe='')}/attempts"
        return self._authed("POST", path, token, json={"code": code})

    def close(self) -> None:
        self._http.close()

    # ---- plumbing --------------------------------------------------------------------

    def _authed(self, method: str, path: str, token: str, **kwargs: Any) -> Any:
        response = self._send(method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
        if response.status_code == 401:
            raise SessionExpiredError("Your session has expired. Please log in again.")
        return self._json(response)

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx2.Response:
        try:
            return self._http.request(method, path, **kwargs)
        except httpx2.TimeoutException as exc:
            raise ApiError(
                "The server is waking up (free hosting sleeps when idle). "
                "Please try again in a minute."
            ) from exc
        except httpx2.TransportError as exc:
            raise ApiError("Cannot reach the server. Check your connection and try again.") from exc

    @staticmethod
    def _json(response: httpx2.Response) -> Any:
        if response.status_code == 502:
            raise ApiError(_detail(response) or "The assistant couldn't answer. Please try again.")
        if response.status_code >= 500:
            raise ApiError("The server had a problem. Please try again shortly.")
        if not response.is_success:
            fallback = f"Unexpected response from the server ({response.status_code})."
            raise ApiError(_detail(response) or fallback)
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError("Unexpected response from the server.") from exc


def _detail(response: httpx2.Response) -> str | None:
    """The API's student-facing message: a string `detail`, or the first validation
    message for a 422 (whose `detail` is a list)."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        return None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        message = detail[0].get("msg")
        return f"Check your input: {message}" if message else None
    return None
