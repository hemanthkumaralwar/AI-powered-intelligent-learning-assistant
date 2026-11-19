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
        if self._authorised():
            FakeApi.received[self.path] = body
            self._reply(200, GET_ROUTES["/auth/me"] | body)

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorised():
            return
        path = self.path.split("?")[0]
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
    app = log_in(run_app(fake_api_url), "asha", "wrong")

    assert app.error[0].value == "Invalid username or password."
    assert len(app.text_input) == 2


def test_login_shows_the_account_in_the_sidebar(fake_api_url: str) -> None:
    app = log_in(run_app(fake_api_url), "asha", "right-password")

    assert app.sidebar.success[0].value == "Signed in as **asha** (student)"
    assert app.session_state["access_token"] == GOOD_TOKEN


def account_sidebar() -> None:
    """The signed-in sidebar on its own: AppTest re-runs only the current page after the
    first run, so widgets drawn by the entry point are tested here instead."""
    import streamlit as st

    from api_client import ApiClient
    from components.account import show_account

    if st.session_state.get("access_token"):
        user = {"username": "asha", "role": "student", "level": "beginner"}
        show_account(ApiClient(st.secrets["API_BASE_URL"]), st.session_state["access_token"], user)


def sidebar_app(fake_api_url: str) -> AppTest:
    FakeApi.received.clear()
    app = AppTest.from_function(account_sidebar, default_timeout=30)
    app.secrets["API_BASE_URL"] = fake_api_url
    app.session_state["access_token"] = GOOD_TOKEN
    app.session_state["user"] = {"username": "asha"}
    return app.run()


def test_log_out_forgets_the_session(fake_api_url: str) -> None:
    app = sidebar_app(fake_api_url)

    app = app.sidebar.button(key="account:logout").click().run()

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


# ---- practice and the compiler panel (Step 15) ------------------------------------------


def signed_in(
    fake_api_url: str, page: str | None = "views/practice.py", token: str = GOOD_TOKEN
) -> AppTest:
    """Signed in, then on `page` (None: the entry point's run, where the sidebar lives;
    AppTest's switch_page runs only the page script)."""
    FakeApi.received.clear()
    app = AppTest.from_file(APP, default_timeout=60)
    app.secrets["API_BASE_URL"] = fake_api_url
    app.session_state["access_token"] = token
    app.run()
    return app if page is None else app.switch_page(page).run()


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
    assert any("course exercise" in box.value for box in app.info)
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

    assert any("https://godbolt.org/z/abc" in s.value for s in app.success)
    assert FakeApi.received["/code/share"]["language"] == "python"


def test_dom_exercise_offers_the_page_sandbox(fake_api_url: str) -> None:
    app = signed_in(fake_api_url)
    lesson = next(s for s in app.selectbox if s.label == "Lesson")
    app = lesson.select_index(1).run()  # the DOM lesson

    assert app.text_area(key="exercise-e2:code").value == DOM_CODE
    app = button(app, "Run in page sandbox").click().run()

    assert not app.exception
    assert app.session_state["exercise-e2:sandboxed"] == (DOM_CODE, "")


def test_level_selector_saves_to_the_profile(fake_api_url: str) -> None:
    app = sidebar_app(fake_api_url)
    level = app.sidebar.selectbox(key="account:level")
    assert level.value == "beginner"

    app = level.set_value("advanced").run()

    assert FakeApi.received["/auth/me"] == {"level": "advanced"}
    assert app.session_state["user"]["level"] == "advanced"
    assert not app.exception


def test_lesson_lists_its_platform_activities(fake_api_url: str) -> None:
    app = signed_in(fake_api_url)

    (box,) = [i.value for i in app.info if "learning platform" in i.value]
    assert "- Quiz: Quiz (10 questions)" in box
    assert "- Card matching: Match the terms (6 pairs)" in box


def test_submit_for_grading_shows_hint_feedback(fake_api_url: str) -> None:
    app = button(signed_in(fake_api_url), "Submit for grading").click().run()

    assert FakeApi.received["/exercises/e1/attempts"] == {"code": BUG_HUNT}
    assert app.warning[0].value == "Not yet. Can a const be reassigned?"
    assert not app.exception


# ---- full frontend (Step 19) ------------------------------------------------------------


def test_admin_pages_are_only_in_the_admin_menu() -> None:
    from menu import ADMIN_PAGES, pages_for

    student = [path for pages in pages_for("student").values() for path, _, _ in pages]
    admin = [path for pages in pages_for("admin").values() for path, _, _ in pages]

    assert ADMIN_PAGES[0][0] not in student
    assert ADMIN_PAGES[0][0] in admin and set(student) < set(admin)


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


def test_courses_page_shows_the_lesson_and_its_activities(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/courses.py")

    assert app.header[0].value == "Variables"
    assert any("learning platform" in box.value for box in app.info)
    assert not app.exception


def test_chat_asks_then_shows_history_sources_and_practice(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/chat.py")

    app = app.chat_input[0].set_value("What is let?").run()

    assert FakeApi.received["/chat/ask"] == {"question": "What is let?"}
    assert app.session_state["chat:active"] == "s1"
    markdown = [m.value for m in app.markdown]
    assert "`let` is block-scoped [1]." in markdown
    assert any("Sources: [1] Basics › Variables — Explanation" in c.value for c in app.caption)
    assert any("Practise Variables on the learning platform" in box.value for box in app.info)


def test_follow_up_goes_to_the_same_chat(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/chat.py")
    app = app.chat_input[0].set_value("What is let?").run()

    app.chat_input[0].set_value("And const?").run()

    assert FakeApi.received["/chat/ask"] == {"question": "And const?", "session_id": "s1"}


def test_coding_helper_explains_code(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/coding.py")
    app.text_area(key="helper:code").input("x = 1")

    app = button(app.run(), "Explain").click().run()

    assert FakeApi.received["/coding/explain"]["code"] == "x = 1"
    assert "- **Line 1:** Sets x." in [m.value for m in app.markdown]


def test_progress_page_shows_what_to_do_next(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/progress.py")

    markdown = [m.value for m in app.markdown]
    assert "🔁 **Variables** · Basics" in markdown
    assert "- Bug hunt: Fix the counter (0%)" in markdown
    assert any("Needs review: Variables" in c.value for c in app.caption)
    assert not app.exception


def test_admin_sees_documents_and_can_reindex(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/admin_courses.py", token=ADMIN_TOKEN)

    assert app.title[0].value == "Manage courses"
    assert app.dataframe[0].value["Course"][0] == "js"

    app = button(app, "Re-index").click().run()

    assert "/admin/reindex" in FakeApi.received
    assert any("Queued 1 document" in s.value for s in app.success)


def test_the_login_screen_lists_no_pages(fake_api_url: str) -> None:
    app = run_app(fake_api_url)

    # No auto-discovered page menu before sign-in (page scripts live in views/, not pages/).
    assert not (Path(APP).parent / "pages").exists()
    assert not app.sidebar.children or not any(
        "admin" in str(child).lower() for child in app.sidebar.children.values()
    )


def test_admin_deletes_a_course_and_sees_confirmation(fake_api_url: str) -> None:
    app = signed_in(fake_api_url, page="views/admin_courses.py", token=ADMIN_TOKEN)
    app.checkbox[0].check()

    app = button(app.run(), "Delete course").click().run()

    assert "DELETE /admin/courses/js" in FakeApi.received
    assert any("Deleted `js`." in s.value for s in app.success)
