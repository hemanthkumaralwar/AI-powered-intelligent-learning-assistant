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


BUG_HUNT = "const total = 0;\ntotal = total + 1;\nconsole.log(total);"
DOM_CODE = "const out = document.querySelector('.output');\nout.textContent = 'hi';"
COURSE = {
    "id": "js",
    "title": "JavaScript",
    "description": None,
    "level": None,
    "language": "javascript",
}
GET_ROUTES = {
    "/auth/me": {"id": "1", "username": "asha", "role": "student"},
    "/courses": [COURSE],
    "/courses/js": COURSE
    | {
        "modules": [
            {
                "id": "m1",
                "position": 1,
                "title": "Basics",
                "description": None,
                "content": {},
                "lessons": [
                    {"id": "l1", "position": 1, "title": "Variables"},
                    {"id": "l2", "position": 2, "title": "The DOM"},
                ],
            }
        ]
    },
    "/lessons/l1": {
        "id": "l1",
        "module_id": "m1",
        "position": 1,
        "title": "Variables",
        "objective": None,
        "content": {},
        "exercises": [
            {
                "id": "e1",
                "kind": "bug_hunt",
                "title": "Fix the counter",
                "instructions": "Find the bug.",
                "starter_code": BUG_HUNT,
                "expected_output": None,
                "hints": ["Can a const change?"],
                "difficulty": None,
            }
        ],
    },
    "/lessons/l2": {
        "id": "l2",
        "module_id": "m1",
        "position": 2,
        "title": "The DOM",
        "objective": None,
        "content": {},
        "exercises": [
            {
                "id": "e2",
                "kind": "interactive",
                "title": "Write text",
                "instructions": "Write into .output.",
                "starter_code": DOM_CODE,
                "expected_output": None,
                "hints": [],
                "difficulty": None,
            }
        ],
    },
}
RUN_RESULT = {
    "outcome": "runtime_error",
    "stdout": "",
    "compile_output": "",
    "stderr": "TypeError: Assignment to constant variable.",
    "exit_code": 1,
    "time_ms": 12,
    "provider": "fake",
    "truncated": False,
}
DEBUG_ANSWER = {
    "summary": "total is a const.",
    "exercise": True,
    "corrected_code": None,
    "issues": [
        {"line": 2, "problem": "Reassigns a const.", "fix_hint": "Should it be able to change?"}
    ],
    "related_lessons": [
        {
            "lesson_id": "l1",
            "lesson_title": "Variables",
            "module_title": "Basics",
            "course_title": "JavaScript",
            "link": "/lessons/l1",
        }
    ],
}
POST_ROUTES = {
    "/code/run": RUN_RESULT,
    "/coding/debug": DEBUG_ANSWER,
    "/code/share": {"url": "https://godbolt.org/z/abc"},
}


class FakeApi(BaseHTTPRequestHandler):
    """Accepts asha/right-password; token "good" works, "expired" is 401, "broken" is 500.
    POST bodies are recorded in `received` so tests can check what the UI sent."""

    received: dict[str, dict] = {}

    def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/auth/login":
            if body == {"username": "asha", "password": "right-password"}:
                token = {"access_token": GOOD_TOKEN, "token_type": "bearer", "expires_in": 60}
                self._reply(200, token)
            else:
                self._reply(401, {"detail": "Invalid username or password"})
        elif self._authorised():
            FakeApi.received[self.path] = body
            self._reply(200, POST_ROUTES[self.path])

    def do_GET(self) -> None:  # noqa: N802
        if self._authorised():
            self._reply(200, GET_ROUTES[self.path])

    def _authorised(self) -> bool:
        authorization = self.headers.get("Authorization")
        if authorization == f"Bearer {GOOD_TOKEN}":
            return True
        if authorization == f"Bearer {BROKEN_TOKEN}":
            self._reply(500, {"detail": "Internal server error"})
        else:
            self._reply(401, {"detail": "Invalid or expired token"})
        return False

    def _reply(self, status: int, body: object) -> None:
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


# ---- practice and the compiler panel (Step 15) ------------------------------------------


def signed_in(fake_api_url: str) -> AppTest:
    FakeApi.received.clear()
    app = AppTest.from_file(APP, default_timeout=30)
    app.secrets["API_BASE_URL"] = fake_api_url
    app.session_state["access_token"] = GOOD_TOKEN
    return app.run()


def button(app: AppTest, label: str):
    return next(b for b in app.button if b.label == label)


def test_exercise_opens_with_its_starter_code(fake_api_url: str) -> None:
    app = signed_in(fake_api_url)

    assert not app.exception
    assert app.header[0].value == "Practice"
    assert app.text_area(key="exercise-e1:code").value == BUG_HUNT
    assert app.selectbox(key="exercise-e1:language").value == "javascript"
    # Compiler Explorer cannot run JavaScript, so there is no share button for it.
    assert "Open in Compiler Explorer" not in [b.label for b in app.button]


def test_run_shows_output_then_ai_explains_it(fake_api_url: str) -> None:
    app = button(signed_in(fake_api_url), "Run").click().run()

    assert "**Runtime error**" in [m.value for m in app.markdown]
    assert any("TypeError: Assignment" in c.value for c in app.code)
    assert FakeApi.received["/code/run"]["code"] == BUG_HUNT

    app = button(app, "Ask AI about this output").click().run()

    sent = FakeApi.received["/coding/debug"]
    assert sent["run"]["outcome"] == "runtime_error"
    assert "TypeError" in sent["run"]["stderr"]
    assert "course exercise" in app.info[0].value
    markdown = [m.value for m in app.markdown]
    assert "total is a const." in markdown
    assert "**Line 2:** Reassigns a const." in markdown
    assert not app.exception


def test_pasted_output_is_sent_without_an_outcome(fake_api_url: str) -> None:
    app = signed_in(fake_api_url)
    app.text_area(key="exercise-e1:pasted").input("TypeError on my laptop")
    app = button(app.run(), "Ask AI about this output").click().run()

    assert FakeApi.received["/coding/debug"]["run"] == {"stdout": "TypeError on my laptop"}


def test_share_appears_for_compiler_explorer_languages(fake_api_url: str) -> None:
    app = signed_in(fake_api_url)
    app = app.selectbox(key="exercise-e1:language").set_value("python").run()

    app = button(app, "Open in Compiler Explorer").click().run()

    assert "https://godbolt.org/z/abc" in app.success[-1].value
    assert FakeApi.received["/code/share"]["language"] == "python"


def test_dom_exercise_offers_the_page_sandbox(fake_api_url: str) -> None:
    app = signed_in(fake_api_url)
    app = app.selectbox[1].select_index(1).run()  # the DOM lesson

    assert app.text_area(key="exercise-e2:code").value == DOM_CODE
    app = button(app, "Run in page sandbox").click().run()

    assert not app.exception
    assert app.session_state["exercise-e2:sandboxed"] == (DOM_CODE, "")
