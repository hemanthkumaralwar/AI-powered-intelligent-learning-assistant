"""Streamlit UI tests with AppTest; screens that call the API use a fake API on localhost."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from streamlit.proto.TextInput_pb2 import TextInput
from streamlit.testing.v1 import AppTest

# Fake tokens understood by FakeApi below (not secrets).
GOOD_TOKEN = "good"  # noqa: S105
EXPIRED_TOKEN = "expired"  # noqa: S105
BROKEN_TOKEN = "broken"  # noqa: S105

APP = str(Path(__file__).resolve().parents[2] / "frontend" / "streamlit_app.py")


@pytest.fixture(autouse=True)
def no_env_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_BASE_URL", raising=False)


def run_app(api_base_url: str | None = None) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=30)
    if api_base_url is not None:
        app.secrets["API_BASE_URL"] = api_base_url
    return app.run()


def test_shows_login_form_when_configured() -> None:
    app = run_app("http://localhost:8000")

    assert not app.exception
    assert [field.label for field in app.text_input] == ["Username", "Password"]
    assert app.text_input[0].proto.type == TextInput.DEFAULT
    assert app.text_input[1].proto.type == TextInput.PASSWORD
    assert app.button[0].label == "Log in"


def test_explains_missing_configuration() -> None:
    app = run_app()

    assert not app.exception
    assert "API_BASE_URL is not configured" in app.error[0].value
    assert not app.text_input


def test_reads_url_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_BASE_URL", "http://127.0.0.1:8000")

    app = run_app()

    assert not app.exception
    assert len(app.text_input) == 2


def test_rejects_insecure_api_url() -> None:
    app = run_app("http://api.example.com")

    assert not app.exception
    assert "https" in app.error[0].value


# ---- screens that call the API, against a tiny fake API on localhost -------------------


class FakeApi(BaseHTTPRequestHandler):
    """Accepts asha/right-password; tokens "good" and "expired" for /auth/me."""

    def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if body == {"username": "asha", "password": "right-password"}:
            self._reply(200, {"access_token": GOOD_TOKEN, "token_type": "bearer", "expires_in": 60})
        else:
            self._reply(401, {"detail": "Invalid username or password"})

    def do_GET(self) -> None:  # noqa: N802
        if self.headers.get("Authorization") == f"Bearer {GOOD_TOKEN}":
            self._reply(200, {"id": "1", "username": "asha", "role": "student"})
        elif self.headers.get("Authorization") == f"Bearer {BROKEN_TOKEN}":
            self._reply(500, {"detail": "Internal server error"})
        else:
            self._reply(401, {"detail": "Invalid or expired token"})

    def _reply(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def fake_api_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeApi)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def log_in(app: AppTest, username: str, password: str) -> AppTest:
    app.text_input[0].input(username)
    app.text_input[1].input(password)
    return app.button[0].click().run()


def test_wrong_password_shows_friendly_error(fake_api_url: str) -> None:
    app = log_in(run_app(fake_api_url), "asha", "wrong")

    assert app.error[0].value == "Invalid username or password."
    assert len(app.text_input) == 2


def test_login_shows_account_then_logout_returns_to_form(fake_api_url: str) -> None:
    app = log_in(run_app(fake_api_url), "asha", "right-password")

    assert app.success[0].value == "Signed in as **asha** (student)"
    assert app.session_state["access_token"] == GOOD_TOKEN

    app = app.button[0].click().run()
    assert "access_token" not in app.session_state
    assert [field.label for field in app.text_input] == ["Username", "Password"]


def test_expired_session_returns_to_login(fake_api_url: str) -> None:
    app = AppTest.from_file(APP, default_timeout=30)
    app.secrets["API_BASE_URL"] = fake_api_url
    app.session_state["access_token"] = EXPIRED_TOKEN
    app.run()

    assert "expired" in app.warning[0].value
    assert "access_token" not in app.session_state


def test_server_error_on_account_page_is_shown_plainly(fake_api_url: str) -> None:
    app = AppTest.from_file(APP, default_timeout=30)
    app.secrets["API_BASE_URL"] = fake_api_url
    app.session_state["access_token"] = BROKEN_TOKEN
    app.run()

    assert app.error[0].value == "The server had a problem. Please try again shortly."
    assert not app.exception
