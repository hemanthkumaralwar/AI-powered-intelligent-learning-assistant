"""POST /chat/ask end to end on the Neon test schema, with a fake search and fake LLM."""

from collections.abc import AsyncIterator
from datetime import timedelta

import argon2
import httpx2
import pytest

from app.auth.passwords import PasswordHasher
from app.auth.service import AuthService
from app.auth.tokens import TokenService
from app.core.config import Settings
from app.core.quota import MINUTE, Quota, QuotaRule
from app.db.models import Course
from app.db.session import Database
from app.llm.client import LLMClient
from app.llm.fake import FakeChatModel
from app.main import create_app
from app.providers.errors import ProviderCallError, RateLimitedError
from app.providers.retry import RetryPolicy
from app.rag.answer import REFUSAL, AnswerService
from app.rag.condense import Condenser
from app.rag.retriever import Retriever
from app.runner.fake import FakeRunner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService
from app.vectorstore.index import SearchHit

pytestmark = pytest.mark.anyio

PASSWORD = "Str0ng-Passphrase!"  # noqa: S105 - test fixture value
COURSE = "javascript-beginner-v1"
LESSON = "javascript-beginner-mod-1-lesson-1"
REPLY = "`let` is block-scoped [1]."
QUESTIONS_PER_MINUTE = 4


class Chat:
    """The test client plus knobs for what the fake search returns."""

    def __init__(self) -> None:
        self.model = FakeChatModel(default_reply=REPLY)
        self.score = 0.9
        self.search_error: ProviderCallError | None = None
        self.client: httpx2.AsyncClient
        self.headers: dict[str, str] = {}
        self.queries: list[str] = []

    async def login(self, username: str) -> dict[str, str]:
        credentials = {"username": username, "password": PASSWORD}
        await self.client.post("/auth/register", json=credentials)
        token = (await self.client.post("/auth/login", json=credentials)).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def search(self, query: str, k: int, course_id: str | None) -> list[SearchHit]:
        self.queries.append(query)
        if self.search_error is not None:
            raise self.search_error
        return [
            SearchHit(
                chunk_id="c1",
                score=self.score,
                course_id=COURSE,
                lesson_id=LESSON,
                section="Explanation",
                text="let declares a block-scoped variable.",
                metadata={
                    "type": "content",
                    "course_title": "JavaScript for Beginners",
                    "module_title": "Basics",
                    "lesson_title": "Variables",
                },
            )
        ]

    async def ask(self, **body) -> httpx2.Response:
        return await self.client.post("/chat/ask", headers=self.headers, json=body)


@pytest.fixture
async def chat(database: Database, null_indexing) -> AsyncIterator[Chat]:
    chat = Chat()
    llm = LLMClient(chat.model, timeout_seconds=5, retry_policy=RetryPolicy(max_attempts=1))
    answers = AnswerService(
        Retriever(chat.search, 5, 0.63),
        llm,
        Quota([QuotaRule("too quickly", QUESTIONS_PER_MINUTE, MINUTE)]),
        Condenser(llm),
    )
    hasher = PasswordHasher(argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    app = create_app(
        Settings(_env_file=None, environment="test", log_level="WARNING", llm_provider="fake"),
        database=database,
        auth=AuthService(hasher, TokenService("j" * 64, timedelta(minutes=30))),
        code_runner=CodeRunnerService([FakeRunner()], None, RunQuota(QuotaLimits(9, 9, 9))),
        indexing=null_indexing,
        answers=answers,
    )
    async with database.session() as session:
        session.add(Course(id=COURSE, title="JavaScript for Beginners", language="javascript"))
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            chat.client = client
            chat.headers = await chat.login("asha")
            yield chat
    assert chat.model.closed is False  # injected services belong to the caller


async def test_grounded_answer_with_citation(chat: Chat) -> None:
    response = await chat.ask(question="  What is let?  ", course_id=COURSE)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["answer"], body["grounded"]) == (REPLY, True)
    assert body["citations"] == [
        {
            "number": 1,
            "course_title": "JavaScript for Beginners",
            "module_title": "Basics",
            "lesson_id": LESSON,
            "lesson_title": "Variables",
            "section": "Explanation",
            "link": f"/lessons/{LESSON}",
        }
    ]
    assert "<question>\nWhat is let?\n</question>" in chat.model.requests[0].messages[1].content


async def test_out_of_course_question_is_refused_without_an_llm_call(chat: Chat) -> None:
    chat.score = 0.4

    response = await chat.ask(question="How do Docker volumes work?")

    assert response.status_code == 200
    body = response.json()
    assert (body["answer"], body["grounded"], body["citations"]) == (REFUSAL, False, [])
    assert chat.model.requests == []


async def test_unknown_course_is_404(chat: Chat) -> None:
    response = await chat.ask(question="What is let?", course_id="no-such-course")

    assert (response.status_code, response.json()["detail"]) == (404, "Course not found")


async def test_requires_login(chat: Chat) -> None:
    chat.headers = {}

    assert (await chat.ask(question="What is let?")).status_code == 401


@pytest.mark.parametrize(
    "body",
    [{"question": "   "}, {"question": "x" * 1001}, {"question": "q", "course_id": ""}, {}],
    ids=["blank", "too-long", "empty-course", "missing"],
)
async def test_invalid_requests_are_422(chat: Chat, body: dict) -> None:
    assert (await chat.ask(**body)).status_code == 422


async def test_quota_gives_429_with_retry_after(chat: Chat) -> None:
    for _ in range(QUESTIONS_PER_MINUTE):
        await chat.ask(question="What is let?")

    response = await chat.ask(question="What is let?")

    assert response.status_code == 429
    assert response.json()["detail"] == "too quickly"
    assert 1 <= int(response.headers["Retry-After"]) <= 60


async def test_provider_failure_gives_a_safe_503(chat: Chat) -> None:
    chat.search_error = RateLimitedError("gemini quota: project 123 exhausted")

    response = await chat.ask(question="What is let?")

    assert response.status_code == 503
    assert "123" not in response.text
    assert response.json()["detail"] == (
        "The assistant is unavailable right now. Please try again shortly."
    )


# ---- Step 13: sessions and follow-ups -------------------------------------------------


async def test_follow_up_in_a_session_is_rewritten_with_its_history(chat: Chat) -> None:
    first = await chat.ask(question="What is an array?", course_id=COURSE)
    session_id = first.json()["session_id"]
    chat.queries.clear()

    second = await chat.ask(question="How do I loop over it?", session_id=session_id)

    assert second.status_code == 200, second.text
    assert second.json()["session_id"] == session_id
    rewrite_request = chat.model.requests[-2]
    assert "Student: What is an array?" in rewrite_request.messages[1].content
    assert f"Tutor: {REPLY}" in rewrite_request.messages[1].content
    # The fake model's rewrite is its default reply; retrieval used it, not the raw text.
    assert chat.queries == [REPLY]


async def test_history_lists_and_returns_the_conversation(chat: Chat) -> None:
    first = (await chat.ask(question="What is let?")).json()
    await chat.ask(question="And const?", session_id=first["session_id"])
    other = (await chat.ask(question="What is a loop?")).json()

    listed = await chat.client.get("/chat/sessions", headers=chat.headers)
    detail = await chat.client.get(f"/chat/sessions/{first['session_id']}", headers=chat.headers)

    assert [s["id"] for s in listed.json()] == [other["session_id"], first["session_id"]]
    assert listed.json()[1]["title"] == "What is let?"
    messages = detail.json()["messages"]
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "What is let?"),
        ("assistant", REPLY),
        ("user", "And const?"),
        ("assistant", REPLY),
    ]
    assert messages[1]["grounded"] is True
    assert messages[1]["citations"][0]["link"] == f"/lessons/{LESSON}"
    assert messages[0]["citations"] is None
    paged = await chat.client.get("/chat/sessions?limit=1&offset=1", headers=chat.headers)
    assert [s["id"] for s in paged.json()] == [first["session_id"]]


async def test_another_student_cannot_read_ask_in_or_delete_a_session(chat: Chat) -> None:
    session_id = (await chat.ask(question="What is let?")).json()["session_id"]
    ravi = await chat.login("ravi")

    read = await chat.client.get(f"/chat/sessions/{session_id}", headers=ravi)
    ask = await chat.client.post(
        "/chat/ask", headers=ravi, json={"question": "And const?", "session_id": session_id}
    )
    delete = await chat.client.delete(f"/chat/sessions/{session_id}", headers=ravi)
    listed = await chat.client.get("/chat/sessions", headers=ravi)

    assert (read.status_code, ask.status_code, delete.status_code) == (403, 403, 403)
    assert read.json()["detail"] == "This chat belongs to another user"
    assert listed.json() == []
    still_there = await chat.client.get(f"/chat/sessions/{session_id}", headers=chat.headers)
    assert len(still_there.json()["messages"]) == 2


async def test_unknown_session_is_404(chat: Chat) -> None:
    missing = "00000000-0000-4000-8000-000000000000"

    read = await chat.client.get(f"/chat/sessions/{missing}", headers=chat.headers)
    ask = await chat.ask(question="And const?", session_id=missing)

    assert (read.status_code, ask.status_code) == (404, 404)
    assert chat.queries == []  # nothing searched for a session that does not exist


async def test_owner_can_delete_a_session(chat: Chat) -> None:
    session_id = (await chat.ask(question="What is let?")).json()["session_id"]

    deleted = await chat.client.delete(f"/chat/sessions/{session_id}", headers=chat.headers)
    read = await chat.client.get(f"/chat/sessions/{session_id}", headers=chat.headers)

    assert (deleted.status_code, read.status_code) == (204, 404)


async def test_full_session_asks_for_a_new_chat(
    chat: Chat, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.chat.service.MAX_MESSAGES_PER_SESSION", 2)
    session_id = (await chat.ask(question="What is let?")).json()["session_id"]

    response = await chat.ask(question="And const?", session_id=session_id)

    assert response.status_code == 409
    assert "start a new chat" in response.json()["detail"]


async def test_a_failed_answer_saves_nothing(chat: Chat) -> None:
    chat.search_error = RateLimitedError("quota")

    assert (await chat.ask(question="What is let?")).status_code == 503
    listed = await chat.client.get("/chat/sessions", headers=chat.headers)
    assert listed.json() == []


async def test_sessions_need_login(chat: Chat) -> None:
    assert (await chat.client.get("/chat/sessions")).status_code == 401


# ---- explanation level (Step 16) --------------------------------------------------------


async def test_answers_use_the_profile_level_unless_the_request_overrides_it(chat: Chat) -> None:
    await chat.client.patch("/auth/me", headers=chat.headers, json={"level": "advanced"})

    await chat.ask(question="What is let?")
    await chat.ask(question="What is let?", level="beginner")

    profile, override = (r.messages[0].content for r in chat.model.requests)
    assert "Explanation level: advanced." in profile
    assert "Explanation level: beginner." in override


async def test_unknown_level_is_422(chat: Chat) -> None:
    assert (await chat.ask(question="What is let?", level="expert")).status_code == 422
