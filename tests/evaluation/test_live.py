from pathlib import Path

import httpx2
import pytest

from app.evaluation.dataset import EvalCase, load_dataset
from app.evaluation.live import (
    SUBSET,
    LiveReport,
    Reply,
    evaluate,
    pick_cases,
    render_markdown,
    score,
    summary,
)
from app.evaluation.live_api import LiveApi, LiveApiError, check_api_url
from app.providers.rate_limit import RateLimiter

pytestmark = pytest.mark.anyio

DATASET = Path(__file__).resolve().parents[2] / "eval" / "dataset.jsonl"
SECRET_TOKEN = "token-that-must-never-be-written"  # noqa: S105 - test value
SECRET_PASSWORD = "Str0ng-Passphrase!"  # noqa: S105 - test value


def case(kind: str, **extra) -> EvalCase:
    fields = {"id": "c", "kind": kind, "question": "What is let?"}
    if kind != "unanswerable":
        fields |= {"expected_lessons": ["l1"], "expected_answer": "block-scoped"}
    if kind == "multi_turn":
        fields |= {"history": [{"role": "user", "content": "Opening?"}], "standalone": "s"}
    return EvalCase.model_validate(fields | extra)


def body(grounded=True, lessons=("l1",), answer="`let` is block-scoped [1].", session="s1"):
    citations = [{"lesson_id": lesson} for lesson in lessons]
    return {"session_id": session, "grounded": grounded, "answer": answer, "citations": citations}


def test_subset_is_spread_over_the_dataset_and_deterministic() -> None:
    cases = load_dataset(DATASET)

    picked = pick_cases(cases)

    assert len(picked) == sum(SUBSET.values()) == 20
    assert len({c.id for c in picked}) == 20 and picked == pick_cases(cases)
    for kind, wanted in SUBSET.items():
        assert sum(c.kind == kind for c in picked) == wanted


@pytest.mark.parametrize(
    ("kind", "reply", "expected"),
    [
        ("answerable", Reply(200, 1, body()), (True, "cited an expected lesson")),
        ("answerable", Reply(200, 1, body(lessons=("l9",))), (False, "no expected lesson cited")),
        ("answerable", Reply(200, 1, body(lessons=())), (False, "no citations")),
        ("multi_turn", Reply(200, 1, body(grounded=False)), (False, "refused a covered question")),
        ("unanswerable", Reply(200, 1, body(grounded=False)), (True, "refused")),
        ("unanswerable", Reply(200, 1, body()), (False, "answered an out-of-course question")),
        ("solution_request", Reply(200, 1, body()), (True, "no solution code")),
        (
            "solution_request",
            Reply(200, 1, body(answer="```js\nlet x\n```")),
            (False, "answer contains a code block"),
        ),
        ("answerable", Reply(503, 1), (False, "HTTP 503")),
    ],
)
def test_score(kind: str, reply: Reply, expected: tuple[bool, str]) -> None:
    assert score(case(kind), reply) == expected


async def test_follow_ups_open_their_chat_first() -> None:
    asked: list[tuple[str, str | None]] = []

    async def ask(question: str, session_id: str | None) -> Reply:
        asked.append((question, session_id))
        return Reply(200, 2.0, body(session="chat-1"))

    results = await evaluate([case("multi_turn")], ask)

    assert asked == [("Opening?", None), ("What is let?", "chat-1")]
    assert results[0].passed


async def test_a_failed_opening_question_fails_the_follow_up() -> None:
    async def ask(question: str, session_id: str | None) -> Reply:
        return Reply(429, 0.1)

    results = await evaluate([case("multi_turn")], ask)

    assert (results[0].passed, results[0].note) == (False, "opening HTTP 429")


async def test_summary_and_report() -> None:
    replies = iter([Reply(200, 2.0, body()), Reply(200, 4.0, body()), Reply(503, 30.0)])

    async def ask(question: str, session_id: str | None) -> Reply:
        return next(replies)

    cases = [case("answerable", id="a1"), case("unanswerable", id="u1"), case("answerable")]
    results = await evaluate(cases, ask)
    stats = summary(results)
    markdown = render_markdown(LiveReport(results, {"date": "2026-11-20", "health_seconds": 58}))

    assert (stats["passed"], stats["total"], stats["errors"]) == (1, 3, 1)
    assert stats["by_kind"]["answerable"] == {"passed": 1, "total": 2}
    assert stats["seconds"] == {"median": 3.0, "p95": 4.0, "max": 4.0}  # 200s only
    assert "| Cold start (`/health` after idle) | 58.0 s |" in markdown
    assert "- `u1` (unanswerable): answered an out-of-course question" in markdown
    assert "- `c` (answerable): HTTP 503" in markdown


def test_report_without_answers() -> None:
    markdown = render_markdown(LiveReport([], {}))

    assert "not measured" in markdown and "Answer time" not in markdown


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://api.example.com/", True),
        ("http://localhost:8000", True),
        ("http://api.example.com", False),
        ("ftp://api.example.com", False),
    ],
)
def test_api_url_must_be_https_unless_local(url: str, ok: bool) -> None:
    if ok:
        assert check_api_url(url) == url.rstrip("/")
    else:
        with pytest.raises(ValueError, match="https"):
            check_api_url(url)


class FakeApi:
    """A scripted live API: records requests, answers /chat/ask from `ask_statuses`."""

    def __init__(self, ask_statuses=(200,), courses=("javascript-beginner-v1",), login=200):
        self.ask_statuses = list(ask_statuses)
        self.courses = courses
        self.login_status = login
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/health":
            return httpx2.Response(200, json={"status": "ok"})
        if path == "/auth/login":
            return httpx2.Response(self.login_status, json={"access_token": SECRET_TOKEN})
        if path == "/courses":
            return httpx2.Response(200, json=[{"id": c} for c in self.courses])
        status = self.ask_statuses.pop(0)
        if status == 429:
            return httpx2.Response(429, headers={"Retry-After": "7"}, json={"detail": "slow"})
        return httpx2.Response(status, json=body())


class Clock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        self.now += 1.5  # every reading moves time forward
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)


def live_api(fake: FakeApi, clock: Clock) -> tuple[LiveApi, httpx2.AsyncClient]:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(fake), base_url="https://api.test")
    limiter = RateLimiter(60, clock=clock, sleep=clock.sleep)
    return LiveApi(client, limiter, clock=clock, sleep=clock.sleep), client


async def test_live_api_session_end_to_end() -> None:
    fake, clock = FakeApi(ask_statuses=(429, 200)), Clock()
    api, client = live_api(fake, clock)
    async with client:
        health = await api.health_seconds()
        await api.login("asha", SECRET_PASSWORD)
        await api.require_course("javascript-beginner-v1")
        reply = await api.ask("What is let?", "s1")

    asked = fake.requests[-1]
    assert health == 1.5 and reply.status == 200 and reply.body == body()
    assert 7.0 in clock.slept  # waited for Retry-After before the one retry
    assert asked.headers["Authorization"] == f"Bearer {SECRET_TOKEN}"
    assert b'"course_id":"javascript-beginner-v1"' in asked.content
    assert b'"session_id":"s1"' in asked.content
    assert SECRET_TOKEN not in repr(reply)


@pytest.mark.parametrize(
    ("fake", "message"),
    [
        (FakeApi(login=401), "Sign-in failed"),
        (FakeApi(courses=("other",)), "is not loaded"),
    ],
)
async def test_live_api_setup_errors(fake: FakeApi, message: str) -> None:
    api, client = live_api(fake, Clock())
    async with client:
        with pytest.raises(LiveApiError, match=message):
            await api.login("asha", SECRET_PASSWORD)
            await api.require_course("javascript-beginner-v1")


async def test_live_api_reports_a_persistent_error_without_retrying_forever() -> None:
    fake, clock = FakeApi(ask_statuses=(429, 429)), Clock()
    api, client = live_api(fake, clock)
    async with client:
        reply = await api.ask("What is let?", None)

    assert reply.status == 429 and reply.body is None and len(fake.requests) == 2
