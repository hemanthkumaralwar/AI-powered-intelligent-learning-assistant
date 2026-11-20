"""A student's session on the live API, for the production evaluation.

The access token stays inside this object: it is never returned, printed or written.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx2

from app.evaluation.live import Reply
from app.providers.rate_limit import RateLimiter

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# A sleeping Render instance can take about a minute to answer its first request.
REQUEST_TIMEOUT_SECONDS = 120.0
DEFAULT_RETRY_SECONDS = 60.0


class LiveApiError(RuntimeError):
    """The API refused the evaluation's setup (sign-in, course); the message says why."""


def check_api_url(url: str) -> str:
    """https only (credentials are sent), except for a local API."""
    parts = urlsplit(url)
    if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
        return url.rstrip("/")
    raise ValueError("The API URL must start with https:// (http:// only for localhost)")


class LiveApi:
    def __init__(
        self,
        client: httpx2.AsyncClient,
        limiter: RateLimiter,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._limiter = limiter
        self._clock = clock
        self._sleep = sleep
        self._headers: dict[str, str] = {}
        self._course_id: str | None = None

    async def health_seconds(self) -> float:
        """Time the first /health call (the cold start when the API was asleep)."""
        start = self._clock()
        response = await self._client.get("/health")
        if response.status_code != 200:
            raise LiveApiError(f"/health returned HTTP {response.status_code}")
        return self._clock() - start

    async def login(self, username: str, password: str) -> None:
        response = await self._client.post(
            "/auth/login", json={"username": username, "password": password}
        )
        if response.status_code != 200:
            raise LiveApiError(f"Sign-in failed (HTTP {response.status_code})")
        self._headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    async def require_course(self, course_id: str) -> None:
        response = await self._client.get("/courses", headers=self._headers)
        if response.status_code != 200:
            raise LiveApiError(f"/courses returned HTTP {response.status_code}")
        if course_id not in {course["id"] for course in response.json()}:
            raise LiveApiError(f"Course {course_id!r} is not loaded; upload it first")
        self._course_id = course_id  # questions are then searched in this course only

    async def ask(self, question: str, session_id: str | None) -> Reply:
        """One paced question; a 429 waits for Retry-After and tries once more."""
        body = {"question": question}
        if self._course_id is not None:
            body["course_id"] = self._course_id
        if session_id is not None:
            body["session_id"] = session_id
        reply, retry_after = await self._post_question(body)
        if reply.status == 429:
            await self._sleep(retry_after)
            reply, _ = await self._post_question(body)
        return reply

    async def _post_question(self, body: dict[str, str]) -> tuple[Reply, float]:
        await self._limiter.acquire()
        start = self._clock()
        response = await self._client.post("/chat/ask", headers=self._headers, json=body)
        seconds = self._clock() - start
        if response.status_code == 200:
            return Reply(200, seconds, response.json()), 0.0
        return Reply(response.status_code, seconds), _retry_after(response)


def _retry_after(response: httpx2.Response) -> float:
    try:
        return max(1.0, float(response.headers.get("Retry-After", DEFAULT_RETRY_SECONDS)))
    except ValueError:
        return DEFAULT_RETRY_SECONDS
