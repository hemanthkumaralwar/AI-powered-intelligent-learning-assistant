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


class Chat:
    """The test client plus knobs for what the fake search returns."""

    def __init__(self) -> None:
        self.model = FakeChatModel(default_reply=REPLY)
        self.score = 0.9
        self.search_error: ProviderCallError | None = None
        self.client: httpx2.AsyncClient
        self.headers: dict[str, str] = {}

    async def search(self, query: str, k: int, course_id: str | None) -> list[SearchHit]:
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
        Retriever(chat.search, 5, 0.63), llm, Quota([QuotaRule("too quickly", 2, MINUTE)])
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
            credentials = {"username": "asha", "password": PASSWORD}
            await client.post("/auth/register", json=credentials)
            token = (await client.post("/auth/login", json=credentials)).json()["access_token"]
            chat.headers = {"Authorization": f"Bearer {token}"}
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
    assert response.json() == {"answer": REFUSAL, "grounded": False, "citations": []}
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
    for _ in range(2):
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
