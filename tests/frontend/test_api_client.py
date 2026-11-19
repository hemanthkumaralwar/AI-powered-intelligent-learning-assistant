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
        (respond(503, text="<html>bad gateway</html>"), "busy or still starting up"),
        (respond(418, {"detail": "I'm a teapot"}), "I'm a teapot"),
        (respond(418, text="teapot"), r"Unexpected response from the server \(418\)"),
        (respond(200, text="not json"), "Unexpected response"),
        (raising(httpx2.ReadTimeout), "waking up"),
        (raising(httpx2.ConnectError), "Cannot reach the server"),
    ],
    ids=[
        "401",
        "422",
        "500",
        "503-html",
        "418-detail",
        "418-no-detail",
        "bad-json",
        "timeout",
        "offline",
    ],
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


# ---- content, code runs and the coding assistant -----------------------------------------


def recording(status: int = 200, body: object = None):
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(status, json=body if body is not None else {})

    return handler, seen


def test_course_and_lesson_ids_are_path_encoded() -> None:
    handler, seen = recording(body={"id": "x"})
    client = client_returning(handler)

    client.course("tok", "js/../admin")
    client.lesson("tok", "a b")

    assert seen[0].url.raw_path == b"/courses/js%2F..%2Fadmin"
    assert seen[1].url.raw_path == b"/lessons/a%20b"
    assert seen[0].headers["authorization"] == "Bearer tok"


def test_courses_returns_the_list() -> None:
    handler, _ = recording(body=[{"id": "js"}])

    assert client_returning(handler).courses("tok") == [{"id": "js"}]


def test_run_share_and_debug_send_the_right_bodies() -> None:
    handler, seen = recording(body={"url": "https://godbolt.org/z/1", "outcome": "ok"})
    client = client_returning(handler)

    client.run_code("tok", "python", "print(1)", "in")
    url = client.share_code("tok", "c", "int main(){}")
    client.debug_code("tok", "python", "x", {"stdout": "pasted"})
    client.debug_code("tok", "python", "x")

    assert url == "https://godbolt.org/z/1"
    bodies = [json.loads(r.content) for r in seen]
    assert [r.url.path for r in seen] == [
        "/code/run",
        "/code/share",
        "/coding/debug",
        "/coding/debug",
    ]
    assert bodies[0] == {"language": "python", "code": "print(1)", "stdin": "in"}
    assert bodies[2]["run"] == {"stdout": "pasted"}
    assert "run" not in bodies[3]


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        (429, {"detail": "You are running code too often; wait a moment."}, "too often"),
        (502, {"detail": "The assistant couldn't produce a valid answer."}, "valid answer"),
        (502, None, "couldn't answer"),
        (503, {"detail": "secret internals"}, "busy or still starting up"),
        (504, None, "took too long"),
        (422, {"detail": [{"msg": "Code must be at most 8 KB"}]}, "Check your input: Code must"),
        (422, {"detail": [{}]}, r"Unexpected response from the server \(422\)"),
    ],
    ids=["429", "502", "502-plain", "503-hides-detail", "504", "422-message", "422-no-message"],
)
def test_api_messages_reach_the_student_except_server_errors(status, body, message) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if body is None:
            return httpx2.Response(status, text="bad gateway")
        return httpx2.Response(status, json=body)

    with pytest.raises(ApiError, match=message) as excinfo:
        client_returning(handler).run_code("tok", "python", "x")
    assert "secret" not in str(excinfo.value)


def test_expired_token_on_any_call_means_session_expired() -> None:
    with pytest.raises(SessionExpiredError):
        client_returning(respond(401, {"detail": "x"})).courses("old")


def test_set_level_patches_the_profile() -> None:
    handler, seen = recording(body={"level": "advanced"})

    assert client_returning(handler).set_level("tok", "advanced") == {"level": "advanced"}
    assert (seen[0].method, seen[0].url.path) == ("PATCH", "/auth/me")
    assert json.loads(seen[0].content) == {"level": "advanced"}


def test_submit_attempt_posts_the_code() -> None:
    handler, seen = recording(body={"passed": True, "feedback": "ok"})

    result = client_returning(handler).submit_attempt("tok", "e/1", "x = 1")

    assert result["passed"] is True
    assert seen[0].url.raw_path == b"/exercises/e%2F1/attempts"
    assert json.loads(seen[0].content) == {"code": "x = 1"}


def test_rate_limit_message_says_when_to_retry() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        detail = {"detail": "You are sending requests to the assistant too quickly; wait a moment."}
        return httpx2.Response(429, json=detail, headers={"Retry-After": "12"})

    with pytest.raises(ApiError, match=r"too quickly; wait a moment\. Try again in 12 seconds\."):
        client_returning(handler).ask("tok", "q")


def test_chat_progress_coding_and_admin_calls() -> None:
    handler, seen = recording(body={"ok": True})
    client = client_returning(handler)

    client.ask("tok", "What is let?", session_id="s1")
    client.chat_sessions("tok")
    client.chat_session("tok", "s1")
    client.coding("tok", "explain", "python", code="x = 1")
    client.progress("tok", course_id="js")
    client.recommendations("tok")
    client.documents("tok")
    client.upload_course("tok", "c.json", b"{}", "javascript")
    client.reindex("tok")

    calls = [(r.method, r.url.path) for r in seen]
    assert calls == [
        ("POST", "/chat/ask"),
        ("GET", "/chat/sessions"),
        ("GET", "/chat/sessions/s1"),
        ("POST", "/coding/explain"),
        ("GET", "/me/progress"),
        ("GET", "/me/recommendations"),
        ("GET", "/admin/documents"),
        ("POST", "/admin/documents"),
        ("POST", "/admin/reindex"),
    ]
    assert json.loads(seen[0].content) == {"question": "What is let?", "session_id": "s1"}
    assert seen[4].url.params["course_id"] == "js" and "course_id" not in seen[5].url.params
    assert b'name="language"' in seen[7].content and b'filename="c.json"' in seen[7].content


def test_deletes_return_nothing_and_unknown_coding_task_is_refused() -> None:
    client = client_returning(lambda request: httpx2.Response(204))

    assert client.delete_chat("tok", "s1") is None
    assert client.delete_course("tok", "js") is None
    with pytest.raises(ValueError, match="unknown coding task"):
        client.coding("tok", "hack", "python", code="x")
