import json

import httpx2
import pytest

from api_client import ApiClient, ApiError, SessionExpiredError, validate_base_url

BASE = "https://api.example.com"


def client_returning(handler) -> ApiClient:
    return ApiClient(BASE, transport=httpx2.MockTransport(handler))


def respond(status: int, body: object | None = None, text: str | None = None):
    def handler(request: httpx2.Request) -> httpx2.Response:
        if text is not None:
            return httpx2.Response(status, text=text)
        return httpx2.Response(status, json=body)

    return handler


def raising(exc_type: type[Exception]):
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise exc_type("boom", request=request)

    return handler


# ---- base URL --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://api.example.com/", "https://api.example.com"),
        ("  https://x.onrender.com  ", "https://x.onrender.com"),
        ("http://localhost:8000", "http://localhost:8000"),
        ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
    ],
)
def test_accepts_https_and_local_http(raw: str, expected: str) -> None:
    assert validate_base_url(raw) == expected


@pytest.mark.parametrize(
    "raw", ["http://api.example.com", "ftp://x", "api.example.com", "", "https://"]
)
def test_rejects_insecure_or_malformed_urls(raw: str) -> None:
    with pytest.raises(ValueError, match="https"):
        validate_base_url(raw)


# ---- login -----------------------------------------------------------------------------


def test_login_sends_credentials_and_returns_token() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"access_token": "tok", "token_type": "bearer"})

    assert client_returning(handler).login("asha", "pw") == "tok"
    assert seen[0].url.path == "/auth/login"
    assert json.loads(seen[0].content) == {"username": "asha", "password": "pw"}


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (respond(401, {"detail": "Invalid username or password"}), "Invalid username or password"),
        (respond(422, {"detail": []}), "Enter both a username and a password"),
        (respond(500, {"detail": "Internal server error"}), "server had a problem"),
        (respond(503, text="<html>bad gateway</html>"), "server had a problem"),
        (respond(418, {"detail": "teapot"}), r"Unexpected response from the server \(418\)"),
        (respond(200, text="not json"), "Unexpected response"),
        (raising(httpx2.ReadTimeout), "waking up"),
        (raising(httpx2.ConnectError), "Cannot reach the server"),
    ],
    ids=["401", "422", "500", "503-html", "418", "bad-json", "timeout", "offline"],
)
def test_login_failures_become_friendly_messages(handler, message: str) -> None:
    with pytest.raises(ApiError, match=message) as excinfo:
        client_returning(handler).login("asha", "pw")
    assert "Traceback" not in str(excinfo.value)
    assert "api.example.com" not in str(excinfo.value)


# ---- me --------------------------------------------------------------------------------


def test_me_sends_bearer_token() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"id": "1", "username": "asha", "role": "student"})

    user = client_returning(handler).me("tok")

    assert user["username"] == "asha"
    assert seen[0].headers["authorization"] == "Bearer tok"


def test_me_with_rejected_token_means_session_expired() -> None:
    with pytest.raises(SessionExpiredError, match="expired"):
        client_returning(respond(401, {"detail": "Invalid or expired token"})).me("old")


def test_close_releases_connections() -> None:
    client = client_returning(respond(200, {}))
    client.close()

    with pytest.raises(RuntimeError):
        client.me("tok")
