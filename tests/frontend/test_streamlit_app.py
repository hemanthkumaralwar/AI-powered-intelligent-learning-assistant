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
ADMIN_TOKEN = "admin-token"  # noqa: S105

APP = str(Path(__file__).resolve().parents[2] / "frontend" / "streamlit_app.py")


@pytest.fixture(autouse=True)
def no_env_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_BASE_URL", raising=False)


def run_app(api_base_url: str | None = None) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=30)
    if api_base_url is not None:
        app.secrets["API_BASE_URL"] = api_base_url
    return app.run()


def sign_in_page(api_base_url: str | None = None) -> AppTest:
    """Guests land on LearnX (Step 24); the login form is on the Sign in page."""
    return run_app(api_base_url).switch_page("views/sign_in.py").run()


def test_shows_login_form_when_configured() -> None:
    app = sign_in_page("http://localhost:8000")

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

    app = sign_in_page()

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
    "/auth/me": {"id": "1", "username": "asha", "role": "student", "level": "beginner"},
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
        "content": {
            "practice": [
                {"kind": "quiz", "title": "Quiz", "count": 10},
                {"kind": "card_matching", "title": "Match the terms", "count": 6},
            ]
        },
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
CHAT_REPLY = {
    "session_id": "s1",
    "answer": "`let` is block-scoped [1].",
    "grounded": True,
    "citations": [
        {
            "number": 1,
            "course_title": "JavaScript",
            "module_title": "Basics",
            "lesson_id": "l1",
            "lesson_title": "Variables",
            "section": "Explanation",
            "link": "/lessons/l1",
            "course_id": "js",
        }
    ],
    "practice": [
        {
            "lesson_id": "l1",
            "lesson_title": "Variables",
            "url": None,
            "activities": [{"kind": "quiz", "title": "Quiz", "count": 10}],
        }
    ],
}
GET_ROUTES |= {
    "/chat/sessions": [
        {
            "id": "s1",
            "title": "What is let?",
            "created_at": "2026-11-19T10:00:00Z",
            "updated_at": "2026-11-19T10:00:00Z",
        }
    ],
    "/chat/sessions/s1": {
        "id": "s1",
        "title": "What is let?",
        "created_at": "2026-11-19T10:00:00Z",
        "updated_at": "2026-11-19T10:00:00Z",
        "messages": [
            {
                "role": "user",
                "content": "What is let?",
                "grounded": None,
                "citations": None,
                "created_at": "2026-11-19T10:00:00Z",
            },
            {
                "role": "assistant",
                "content": "`let` is block-scoped [1].",
                "grounded": True,
                "citations": CHAT_REPLY["citations"],
                "created_at": "2026-11-19T10:00:01Z",
            },
        ],
    },
    "/me/recommendations": {
        "course_id": "js",
        "course_title": "JavaScript",
        "recommendations": [
            {
                "kind": "review",
                "lesson_id": "l1",
                "lesson_title": "Variables",
                "module_title": "Basics",
                "reason": "Review: 0% on this lesson's exercises",
                "mastery": 0.0,
                "exercises": [
                    {
                        "exercise_id": "e1",
                        "title": "Fix the counter",
                        "kind": "bug_hunt",
                        "score": 0.0,
                    }
                ],
                "practice": [{"kind": "quiz", "title": "Quiz", "count": 10}],
                "practice_url": None,
            },
        ],
    },
    "/me/progress": {
        "course_id": "js",
        "course_title": "JavaScript",
        "weak_threshold": 0.6,
        "modules": [
            {
                "module_id": "m1",
                "title": "Basics",
                "mastery": 0.0,
                "coverage": 0.5,
                "lessons": [
                    {"lesson_id": "l1", "title": "Variables", "mastery": 0.0, "weak": True},
                    {"lesson_id": "l2", "title": "The DOM", "mastery": None, "weak": False},
                ],
            }
        ],
    },
    "/admin/documents": [
        {
            "id": "d1",
            "course_id": "js",
            "filename": "javascript-beginner.json",
            "content_type": "application/json",
            "size_bytes": 2048000,
            "status": "ready",
            "error_message": None,
            "created_at": "2026-11-19T10:00:00Z",
        }
    ],
}
POST_ROUTES = {
    "/chat/ask": CHAT_REPLY,
    "/coding/explain": {
        "summary": "Declares x.",
        "lines": [{"line": 1, "explanation": "Sets x."}],
        "related_lessons": [],
        "practice": [],
    },
    "/admin/documents": GET_ROUTES["/admin/documents"][0] | {"status": "pending"},
    "/admin/reindex": {"queued": 1},
    "/code/run": RUN_RESULT,
    "/coding/debug": DEBUG_ANSWER,
    "/code/share": {"url": "https://godbolt.org/z/abc"},
    "/exercises/e1/attempts": {
        "id": "a1",
        "passed": False,
        "feedback": "Can a const be reassigned?",
        "created_at": "2026-11-19T10:00:00Z",
    },
}


class FakeApi(BaseHTTPRequestHandler):
    """Accepts asha/right-password; token "good" works, "expired" is 401, "broken" is 500.
    POST bodies are recorded in `received` so tests can check what the UI sent."""

    received: dict[str, dict] = {}

    def do_POST(self) -> None:  # noqa: N802 - name required by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) or b"{}"
        multipart = "multipart" in self.headers.get("Content-Type", "")
        body = {"multipart": raw.decode("latin-1")} if multipart else json.loads(raw)
        if self.path == "/auth/login":
            if body == {"username": "asha", "password": "right-password"}:
                token = {"access_token": GOOD_TOKEN, "token_type": "bearer", "expires_in": 60}
                self._reply(200, token)
            else:
                self._reply(401, {"detail": "Invalid username or password"})
        elif self._authorised():
            FakeApi.received[self.path] = body
            self._reply(200, POST_ROUTES[self.path])

    def do_PATCH(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not self._authorised():
            return
        FakeApi.received[self.path] = body
        self._reply(200, GET_ROUTES["/auth/me"] | body)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        public = path == "/courses" or path.startswith(("/courses/", "/lessons/"))
        if public and "Authorization" not in self.headers:
            FakeApi.received[f"GUEST {path}"] = {}
            self._reply(200, GET_ROUTES[path])
            return
        if not self._authorised():
            return
        if path == "/auth/me" and self._is_admin():
            self._reply(200, GET_ROUTES[path] | {"username": "boss", "role": "admin"})
        else:
            self._reply(200, GET_ROUTES[path])

    def do_DELETE(self) -> None:  # noqa: N802
        if self._authorised():
            FakeApi.received[f"DELETE {self.path}"] = {}
            self.send_response(204)
            self.end_headers()

    def _is_admin(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {ADMIN_TOKEN}"

    def _authorised(self) -> bool:
        authorization = self.headers.get("Authorization")
        if authorization in (f"Bearer {GOOD_TOKEN}", f"Bearer {ADMIN_TOKEN}"):
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
    app = log_in(sign_in_page(fake_api_url), "asha", "wrong")

    assert app.error[0].value == "Invalid username or password."
    assert len(app.text_input) == 2


def test_login_shows_the_account_in_the_profile_menu(fake_api_url: str) -> None:
    app = log_in(sign_in_page(fake_api_url), "asha", "right-password")

    assert "Signed in as **asha** (student)" in [m.value for m in app.markdown]
    assert app.session_state["access_token"] == GOOD_TOKEN


def profile_menu() -> None:
    """The profile menu on its own: AppTest re-runs only the current page after the first
    run, so widgets drawn by the entry point are tested here instead."""
    import streamlit as st

    from api_client import ApiClient
    from components.account import show_profile

    if st.session_state.get("access_token"):
        user = {"username": "asha", "role": "student", "level": "beginner"}
        show_profile(ApiClient(st.secrets["API_BASE_URL"]), st.session_state["access_token"], user)


def profile_app(fake_api_url: str) -> AppTest:
    FakeApi.received.clear()
    app = AppTest.from_function(profile_menu, default_timeout=30)
    app.secrets["API_BASE_URL"] = fake_api_url
    app.session_state["access_token"] = GOOD_TOKEN
    app.session_state["user"] = {"username": "asha"}
    return app.run()


def test_log_out_forgets_the_session(fake_api_url: str) -> None:
    app = profile_app(fake_api_url)

    app = app.button(key="account:logout").click().run()

    assert "access_token" not in app.session_state and "user" not in app.session_state


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


def test_level_selector_saves_to_the_profile(fake_api_url: str) -> None:
    app = profile_app(fake_api_url)
    level = app.selectbox(key="account:level")
    assert level.value == "beginner"

    app = level.set_value("advanced").run()

    assert FakeApi.received["/auth/me"] == {"level": "advanced"}
    assert app.session_state["user"]["level"] == "advanced"
    assert not app.exception


# ---- LearnX: courses, course page, lesson tabs -----------------------------------------

# The first lesson gets reading content, to check the staged Reading tab.
GET_ROUTES["/lessons/l1"]["objective"] = "Declare variables with let and const."
GET_ROUTES["/lessons/l1"]["content"] |= {
    "duration": "25 minutes",
    "concepts": ["let", "const"],
    "analogy": {
        "subject": "Labelled boxes",
        "comparison": "A variable is a labelled box.",
        "mapping": [{"from": "Glued | label", "to": "const"}],
    },
    "keyTakeaways": ["Prefer const."],
    "hooklineimage": {"html": "<script>alert(1)</script>"},
    "hooklines": [{"text": "A variable is a label.", "image": {"html": "<b>x</b>"}}],
    "lessonExplanation": [{"topic": "Declaring", "points": ["let can change."]}],
    "syntax": {"title": "Syntax", "highlight": {"code": "let x = 1;"}},
    "parts": [{"label": "Step 1", "name": "let", "description": "Can be reassigned."}],
    "example": [{"title": "Example 1", "code": "const a = 1;", "explanation": "Fixed."}],
    "flowchart": {"title": "Choosing", "code": "flowchart LR\n A --> B"},
    "realWorldStory": {
        "storyTitle": "Config",
        "storyText": "Keys stay const.",
        "storyCompany": "Acme",
    },
    "useCaseCards": [{"industry": "Web", "jobRole": "Developer", "useCase": "Form state"}],
}


def signed_in(
    fake_api_url: str,
    page: str | None = "views/learnx.py",
    token: str = GOOD_TOKEN,
    state: dict[str, object] | None = None,
) -> AppTest:
    """Signed in, with `state` in session_state, then on `page` (None: the entry point's
    run; AppTest's switch_page runs only the page script)."""
    FakeApi.received.clear()
    app = AppTest.from_file(APP, default_timeout=60)
    app.secrets["API_BASE_URL"] = fake_api_url
    app.session_state["access_token"] = token
    for key, value in (state or {}).items():
        app.session_state[key] = value
    app.run()
    return app if page is None else app.switch_page(page).run()


def in_course(fake_api_url: str) -> AppTest:
    return signed_in(fake_api_url, state={"learnx:course": "js"})


def in_lesson(fake_api_url: str, lesson: str = "l1") -> AppTest:
    return signed_in(fake_api_url, state={"learnx:course": "js", "learnx:lesson": lesson})


def button(app: AppTest, label: str):
    return next(b for b in app.button if b.label == label)


def test_learnx_lists_courses_and_opens_one(fake_api_url: str) -> None:
    app = signed_in(fake_api_url)

    assert "**JavaScript**" in [m.value for m in app.markdown]
    assert any(c.value == "JavaScript" for c in app.caption)

    app = app.button(key="course:js").click().run()

    assert app.session_state["learnx:course"] == "js"
    assert "## JavaScript" in [m.value for m in app.markdown]
    assert not app.exception


def test_course_page_shows_modules_progress_and_what_to_do_next(fake_api_url: str) -> None:
    app = in_course(fake_api_url)

    assert app.expander[0].label == "1. Basics · 0%"
    captions = [c.value for c in app.caption]
    assert "0% · review" in captions and "not started" in captions
    markdown = [m.value for m in app.markdown]
    assert "🔁 **Variables** · Basics" in markdown
    assert "- Bug hunt: Fix the counter (0%)" in markdown

    app = app.button(key="next:l1").click().run()

    assert app.session_state["learnx:lesson"] == "l1"
    assert not app.exception


def test_course_page_opens_a_lesson_and_goes_back(fake_api_url: str) -> None:
    app = in_course(fake_api_url)

    app = app.button(key="lesson:l2").click().run()
    assert "## The DOM" in [m.value for m in app.markdown]

    previous = app.button(key="lesson:previous")
    assert previous.help == "Previous: Variables"
    assert not [b for b in app.button if b.key == "lesson:next"]  # The DOM is the last one
    app = previous.click().run()
    assert "## Variables" in [m.value for m in app.markdown]

    app = app.button(key="outline:course").click().run()  # the course name in the outline
    assert app.session_state["learnx:lesson"] is None


def test_lesson_has_reading_practice_code_and_activity_tabs(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)

    labels = [t.label for t in app.tabs]  # the Code tab's own tabs are listed inside it
    assert labels[:4] == ["Reading", "Ask Nexus", "Practice", "Code"]
    assert labels[-1] == "Quiz & activities"
    assert not app.exception


def test_lesson_outline_lists_the_module_with_progress_marks(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url, lesson="l2")

    outline = {b.key: b for b in app.sidebar.button}
    assert outline["outline:course"].label == "JavaScript"
    assert app.sidebar.caption[0].value == "1. Basics"
    variables, dom = outline["outline:l1"], outline["outline:l2"]
    assert (variables.label, variables.icon) == ("Variables", ":material/timelapse:")  # weak
    assert dom.icon == ":material/radio_button_checked:"  # the open lesson

    app = variables.click().run()

    assert app.session_state["learnx:lesson"] == "l1"
    assert "## Variables" in [m.value for m in app.markdown]


def test_outline_marks_follow_progress() -> None:
    from components.outline import DONE, NOT_STARTED, STARTED, lesson_icon

    assert lesson_icon(None, current=False) == NOT_STARTED
    assert lesson_icon({"mastery": None, "weak": False}, current=False) == NOT_STARTED
    assert lesson_icon({"mastery": 0.4, "weak": True}, current=False) == STARTED
    assert lesson_icon({"mastery": 1.0, "weak": False}, current=False) == DONE


def test_guest_outline_has_no_progress_marks(fake_api_url: str) -> None:
    app = guest(fake_api_url, {"learnx:course": "js", "learnx:lesson": "l2"})

    assert app.sidebar.button(key="outline:l1").icon == ":material/radio_button_unchecked:"
    assert not app.exception


def test_reading_tab_shows_numbered_stages_safely(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)
    markdown = [m.value for m in app.markdown]
    captions = [c.value for c in app.caption]

    stages = [
        m.removeprefix("#### ")
        for m in markdown
        if m.startswith("#### ")
        and m not in ("#### Ask Nexus about this course", "#### Lesson quiz")
    ]
    assert stages == [
        "Your mission",
        "Brief",
        "Core concepts",
        "Mental model",
        "Syntax anatomy",
        "Examples",
        "Flow",
        "In the real world",
        "Recap",
    ]
    assert "Stage 1 of 9" in captions and "Stage 9 of 9" in captions
    assert "**Objective:** Declare variables with let and const." in markdown
    assert "- A variable is a label." in markdown and "1. **let:** Can be reassigned." in markdown
    assert "**Config** (Acme)" in markdown and "- **Web · Developer:** Form state" in markdown
    codes = [c.value for c in app.code]
    assert "let x = 1;" in codes and "flowchart LR\n A --> B" in codes
    assert "| Glued \\| label | const |" in "\n".join(markdown)  # a | cannot split a cell
    assert not any("<script>" in value for value in markdown)  # stored HTML is skipped


def test_exercise_opens_with_its_starter_code(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)

    assert app.text_area(key="exercise-e1:code").value == BUG_HUNT
    assert app.selectbox(key="exercise-e1:language").value == "javascript"
    # Compiler Explorer cannot run JavaScript, so there is no share button for it.
    assert "Open in Compiler Explorer" not in [b.label for b in app.button]


def test_run_shows_output_then_ai_explains_it(fake_api_url: str) -> None:
    app = button(in_lesson(fake_api_url), "Run").click().run()

    assert "**Runtime error**" in [m.value for m in app.markdown]
    assert any("TypeError: Assignment" in c.value for c in app.code)
    assert FakeApi.received["/code/run"]["code"] == BUG_HUNT

    app = button(app, "Ask AI about this output").click().run()

    sent = FakeApi.received["/coding/debug"]
    assert sent["run"]["outcome"] == "runtime_error"
    assert "TypeError" in sent["run"]["stderr"]
    assert any("course exercise" in box.value for box in app.info)
    markdown = [m.value for m in app.markdown]
    assert "total is a const." in markdown
    assert "**Line 2:** Reassigns a const." in markdown
    assert not app.exception


def test_pasted_output_is_sent_without_an_outcome(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)
    app.text_area(key="exercise-e1:pasted").input("TypeError on my laptop")
    app = button(app.run(), "Ask AI about this output").click().run()

    assert FakeApi.received["/coding/debug"]["run"] == {"stdout": "TypeError on my laptop"}


def test_share_appears_for_compiler_explorer_languages(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)
    app = app.selectbox(key="exercise-e1:language").set_value("python").run()

    app = button(app, "Open in Compiler Explorer").click().run()

    assert any("https://godbolt.org/z/abc" in s.value for s in app.success)
    assert FakeApi.received["/code/share"]["language"] == "python"


def test_dom_exercise_offers_the_page_sandbox(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url, lesson="l2")

    assert app.text_area(key="exercise-e2:code").value == DOM_CODE
    app = button(app, "Run in page sandbox").click().run()

    assert not app.exception
    assert app.session_state["exercise-e2:sandboxed"] == (DOM_CODE, "")


def test_activities_tab_lists_the_platform_activities_but_not_the_quiz(
    fake_api_url: str,
) -> None:
    app = in_lesson(fake_api_url)

    (box,) = [i.value for i in app.info if "learning platform" in i.value]
    assert "- Card matching: Match the terms (6 pairs)" in box
    assert "Quiz" not in box  # the quiz is taken in the app instead


def test_lesson_without_activities_says_so(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url, lesson="l2")

    assert any("no quiz or activities" in i.value for i in app.info)
    assert "/lessons/l2/quiz" not in FakeApi.received


# ---- Lesson quiz, taken in the app -------------------------------------------------

Q1, Q2 = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
GET_ROUTES["/lessons/l1/quiz"] = {
    "lesson_id": "l1",
    "questions": [
        {
            "id": Q1,
            "position": 1,
            "question": "Which keyword declares a constant?",
            "options": [{"id": 2, "text": "const"}, {"id": 0, "text": "var"}],
        },
        {
            "id": Q2,
            "position": 2,
            "question": "Can let be reassigned?",
            "options": [{"id": 1, "text": "No"}, {"id": 0, "text": "Yes"}],
        },
    ],
}
GET_ROUTES["/lessons/l1/quiz/attempts"] = [
    {"id": "a2", "correct": 1, "total": 2, "created_at": "2026-11-24T10:00:00Z"},
    {"id": "a1", "correct": 2, "total": 2, "created_at": "2026-11-23T10:00:00Z"},
]
POST_ROUTES["/lessons/l1/quiz/attempts"] = {
    "id": "a3",
    "correct": 1,
    "total": 2,
    "created_at": "2026-11-24T11:00:00Z",
    "results": [
        {
            "question_id": Q1,
            "chosen": 2,
            "correct_option": 2,
            "correct": True,
            "explanation": "const cannot be reassigned.",
        },
        {
            "question_id": Q2,
            "chosen": 1,
            "correct_option": 0,
            "correct": False,
            "explanation": "let can be reassigned; const cannot.",
        },
    ],
}


def answer_quiz(app: AppTest, first: int | None, second: int | None) -> AppTest:
    if first is not None:
        app.radio(key=f"quiz:l1:q0:{Q1}").set_value(first)
    if second is not None:
        app.radio(key=f"quiz:l1:q0:{Q2}").set_value(second)
    return button(app, "Submit answers").click().run()


def test_quiz_shows_questions_and_past_scores(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)

    assert "#### Lesson quiz" in [m.value for m in app.markdown]
    first = app.radio(key=f"quiz:l1:q0:{Q1}")
    assert first.options == ["const", "var"] and first.value is None
    assert any("Last score 1/2 · best 2/2 · 2 attempts" in c.value for c in app.caption)
    assert not app.exception


def test_quiz_is_marked_and_shows_the_right_answers(fake_api_url: str) -> None:
    app = answer_quiz(in_lesson(fake_api_url), 2, 1)

    assert FakeApi.received["/lessons/l1/quiz/attempts"] == {"answers": {Q1: 2, Q2: 1}}
    markdown = [m.value for m in app.markdown]
    assert "**Score: 1/2 (50%)**" in markdown
    assert "Your answer: No  \nCorrect answer: Yes" in markdown
    assert any("let can be reassigned" in c.value for c in app.caption)
    assert not app.exception


def test_quiz_needs_every_answer_before_marking(fake_api_url: str) -> None:
    app = answer_quiz(in_lesson(fake_api_url), 2, None)

    assert any("Answer every question first (1 left)." in w.value for w in app.warning)
    assert "/lessons/l1/quiz/attempts" not in FakeApi.received


def test_retake_starts_a_fresh_quiz(fake_api_url: str) -> None:
    app = answer_quiz(in_lesson(fake_api_url), 2, 1)

    app = button(app, "Retake the quiz").click().run()

    assert app.radio(key=f"quiz:l1:q1:{Q1}").value is None
    assert "**Score: 1/2 (50%)**" not in [m.value for m in app.markdown]


def test_submit_for_grading_shows_hint_feedback(fake_api_url: str) -> None:
    app = button(in_lesson(fake_api_url), "Submit for grading").click().run()

    assert FakeApi.received["/exercises/e1/attempts"] == {"code": BUG_HUNT}
    assert app.warning[0].value == "Not yet. Can a const be reassigned?"
    assert not app.exception


def test_code_tab_explains_code_in_the_course_language(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)
    assert app.selectbox(key="helper:language").value == "javascript"
    app.text_area(key="helper:code").input("x = 1")

    app = button(app.run(), "Explain").click().run()

    assert FakeApi.received["/coding/explain"]["code"] == "x = 1"
    assert "- **Line 1:** Sets x." in [m.value for m in app.markdown]


POST_ROUTES |= {
    "/coding/example": {
        "title": "A closure",
        "code": "const add = (a) => (b) => a + b;",
        "explanation": "add remembers a.",
        "related_lessons": [],
        "practice": [],
    },
    "/coding/practice": {
        "questions": [
            {"question": "Sum 1 to 3", "expected_output": "6", "hints": ["Use a loop."]},
        ],
        "related_lessons": [],
        "practice": [],
    },
}


@pytest.mark.parametrize(
    ("topic_key", "label", "path", "shown"),
    [
        ("helper:example-topic", "Show example", "/coding/example", "add remembers a."),
        ("helper:practice-topic", "Get questions", "/coding/practice", "**1. Sum 1 to 3**"),
    ],
)
def test_code_tab_examples_and_practice_questions(
    fake_api_url: str, topic_key: str, label: str, path: str, shown: str
) -> None:
    app = in_lesson(fake_api_url)
    app.text_input(key=topic_key).input("closures")

    app = button(app.run(), label).click().run()

    assert FakeApi.received[path]["topic"] == "closures"
    assert shown in [m.value for m in app.markdown]
    assert not app.exception


# ---- Arc: the course assistant ----------------------------------------------------------


def test_chat_asks_then_shows_history_sources_and_practice(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)

    app = app.chat_input[0].set_value("What is let?").run()

    assert FakeApi.received["/chat/ask"] == {"question": "What is let?", "course_id": "js"}
    assert app.session_state["chat:active"] == "s1"
    markdown = [m.value for m in app.markdown]
    assert "`let` is block-scoped [1]." in markdown
    assert any("Sources: [1] Basics › Variables — Explanation" in c.value for c in app.caption)
    # Platform activities live only in the lesson's Quiz & activities tab, not under answers.
    assert not any("Practise Variables on the learning platform" in box.value for box in app.info)


def test_follow_up_goes_to_the_same_chat(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)
    app = app.chat_input[0].set_value("What is let?").run()

    app.chat_input[0].set_value("And const?").run()

    assert FakeApi.received["/chat/ask"] == {
        "question": "And const?",
        "course_id": "js",
        "session_id": "s1",
    }


def test_past_chats_open_and_new_chat_starts_fresh(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)

    app = app.button(key="chat-s1").click().run()
    assert app.session_state["chat:active"] == "s1"
    assert "What is let?" in [m.value for m in app.markdown]

    app = button(app, "New chat").click().run()
    assert app.session_state["chat:active"] is None
    assert "#### Ask Nexus about this course" in [m.value for m in app.markdown]


def test_past_chats_panel_hides_and_comes_back(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)
    assert "**Past chats**" in [m.value for m in app.markdown]

    app = app.button(key="chat:hide-panel").click().run()

    assert "**Past chats**" not in [m.value for m in app.markdown]
    assert not [b for b in app.button if b.key == "chat-s1"]
    assert app.chat_input  # still possible to ask

    app = app.button(key="chat:show-panel").click().run()

    assert app.button(key="chat-s1").label == "What is let?"


def test_an_answer_the_course_does_not_cover_is_a_notice(
    fake_api_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = GET_ROUTES["/chat/sessions/s1"]
    off_topic = {**session["messages"][1], "grounded": False, "citations": []}
    off_topic["content"] = "I couldn't find this in your course materials."
    monkeypatch.setitem(session, "messages", [session["messages"][0], off_topic])

    app = in_lesson(fake_api_url)
    app = app.button(key="chat-s1").click().run()

    assert [w.value for w in app.warning] == ["I couldn't find this in your course materials."]
    assert "I couldn't find this in your course materials." not in [m.value for m in app.markdown]


# ---- the rail and admin pages ----------------------------------------------------------


def test_rail_per_visitor_has_no_arc_and_admin_lives_at_slash_admin() -> None:
    from menu import pages_for

    def titles(user: dict | None) -> list[str]:
        return [page.title for page in pages_for(user)]

    assert titles(None) == ["LearnX", "Sign in"]
    assert titles({"role": "student"}) == ["LearnX"]
    assert titles({"role": "admin"}) == ["LearnX", "Settings"]
    assert pages_for({"role": "admin"})[-1].url_path == "admin"


def test_a_student_cannot_open_the_admin_page(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page=None)

    # Not registered in a student's navigation at all, so it cannot be reached.
    with pytest.raises(ValueError, match="Could not find a navigation page"):
        app.switch_page("views/admin_courses.py")
    assert "/admin/documents" not in FakeApi.received


def admin_page_as(user: dict) -> None:
    """The admin page's own role check, run directly (second guard behind the menu)."""
    import streamlit as st

    st.session_state["user"] = user
    st.session_state["access_token"] = "t"  # noqa: S105 - placeholder, never sent
    import runpy

    runpy.run_path(st.secrets["PAGE"])


def test_the_admin_page_itself_refuses_students(fake_api_url: str) -> None:
    app = AppTest.from_function(admin_page_as, args=({"role": "student"},), default_timeout=60)
    app.secrets["API_BASE_URL"] = fake_api_url
    app.secrets["PAGE"] = str(Path(APP).parent / "views" / "admin_courses.py")

    app.run()

    assert app.error[0].value == "This page is for admins."


def test_admin_sees_documents_and_can_reindex(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/admin_courses.py", token=ADMIN_TOKEN)

    assert app.title[0].value == "Manage courses"
    assert app.dataframe[0].value["Course"][0] == "js"

    app = button(app, "Re-index").click().run()

    assert "/admin/reindex" in FakeApi.received
    assert any("Queued 1 document" in s.value for s in app.success)


def test_guests_never_get_the_admin_page(fake_api_url: str) -> None:
    app = run_app(fake_api_url)

    # No auto-discovered page menu (page scripts live in views/, not pages/), and the
    # admin page is not in a guest's navigation.
    assert not (Path(APP).parent / "pages").exists()
    with pytest.raises(ValueError, match="Could not find a navigation page"):
        app.switch_page("views/admin_courses.py")
    assert not app.sidebar.children or not any(
        "admin" in str(child).lower() for child in app.sidebar.children.values()
    )


def test_admin_deletes_a_course_and_sees_confirmation(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/admin_courses.py", token=ADMIN_TOKEN)
    app.checkbox[0].check()

    app = button(app.run(), "Delete course").click().run()

    assert "DELETE /admin/courses/js" in FakeApi.received
    assert any("Deleted `js`." in s.value for s in app.success)


# ---- Removed features stay removed (Open in Practice, spaced review) ----------------


def test_answers_have_no_open_in_practice_button(fake_api_url: str) -> None:
    app = in_lesson(fake_api_url)

    app = app.chat_input[0].set_value("What is let?").run()

    assert not [b for b in app.button if b.label.startswith("Open in Practice")]
    assert not app.exception


def test_course_page_has_no_review_schedule(fake_api_url: str) -> None:
    app = in_course(fake_api_url)

    assert "#### Due for review" not in [m.value for m in app.markdown]
    assert "/me/reviews" not in FakeApi.received


def test_settings_have_no_course_feature_switches(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/admin_courses.py", token=ADMIN_TOKEN)

    assert not app.toggle
    assert not app.exception


# ---- Step 24: guests browse and read; sign in for the rest ---------------------------


def guest(fake_api_url: str, state: dict[str, object] | None = None) -> AppTest:
    FakeApi.received.clear()
    app = AppTest.from_file(APP, default_timeout=60)
    app.secrets["API_BASE_URL"] = fake_api_url
    for key, value in (state or {}).items():
        app.session_state[key] = value
    return app.run()


def test_guests_see_the_courses_without_signing_in(fake_api_url: str) -> None:
    app = guest(fake_api_url)

    assert "**JavaScript**" in [m.value for m in app.markdown]
    assert "GUEST /courses" in FakeApi.received  # sent without a token
    assert not app.exception


def test_guests_read_lessons_and_are_asked_to_sign_in_for_the_rest(fake_api_url: str) -> None:
    app = guest(fake_api_url, {"learnx:course": "js", "learnx:lesson": "l1"})

    markdown = [m.value for m in app.markdown]
    assert "#### Your mission" in markdown  # the Reading tab
    prompts = [i.value for i in app.info]
    assert "Sign in to ask Nexus, the course assistant." in prompts
    assert "Sign in to run and submit this lesson's exercises." in prompts
    assert "Sign in to use the coding helper." in prompts
    assert "Sign in to take this lesson's quiz and count it in your progress." in prompts
    assert "GUEST /lessons/l1/quiz" not in FakeApi.received
    assert not app.text_area  # no code editor for guests
    assert not app.chat_input
    assert not app.exception


def test_guests_see_no_progress_on_the_course_page(fake_api_url: str) -> None:
    app = guest(fake_api_url, {"learnx:course": "js"})

    assert app.expander[0].label == "1. Basics"  # no mastery for guests
    assert "Sign in to track your progress and see what to do next." in [i.value for i in app.info]
    assert "#### What to do next" not in [m.value for m in app.markdown]
