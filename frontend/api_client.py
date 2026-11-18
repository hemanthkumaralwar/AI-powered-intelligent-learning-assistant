"""Small HTTP client for the ArchintX API, kept free of Streamlit so it can be unit tested.

Every failure becomes an `ApiError` whose message is safe to show to a student: no
stack traces, URLs, or server internals.
"""

from typing import Any
from urllib.parse import urlsplit

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
        """Return the signed-in account (`id`, `username`, `role`)."""
        response = self._send("GET", "/auth/me", headers={"Authorization": f"Bearer {token}"})
        if response.status_code == 401:
            raise SessionExpiredError("Your session has expired. Please log in again.")
        return self._json(response)

    def close(self) -> None:
        self._http.close()

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
    def _json(response: httpx2.Response) -> dict[str, Any]:
        if response.status_code >= 500:
            raise ApiError("The server had a problem. Please try again shortly.")
        if not response.is_success:
            raise ApiError(f"Unexpected response from the server ({response.status_code}).")
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError("Unexpected response from the server.") from exc
