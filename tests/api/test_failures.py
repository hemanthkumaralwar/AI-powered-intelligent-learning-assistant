"""Simulated failures return clean, documented errors (README "Errors" table), never
provider or server internals. (A generic 500 for unexpected bugs is covered by
tests/core/test_errors.py.)"""

import pytest

from app.providers.errors import (
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitedError,
)

pytestmark = pytest.mark.anyio

INTERNAL = "internal detail project-123"


async def ask(world, headers=None):
    return await world.client.post(
        "/chat/ask", headers=headers or world.headers["asha"], json={"question": "What is let?"}
    )


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (ProviderTimeoutError(INTERNAL), 504, "The assistant took too long to answer."),
        (ProviderUnavailableError(INTERNAL), 503, "The assistant is unavailable right now."),
        (RateLimitedError(INTERNAL, daily=True), 503, "The assistant is unavailable right now."),
    ],
    ids=["timeout-504", "down-503", "provider-quota-503"],
)
async def test_ai_provider_failures_in_chat(world, error, status: int, detail: str) -> None:
    world.model.push(error)

    response = await ask(world)

    assert response.status_code == status
    assert response.json()["detail"].startswith(detail)
    assert INTERNAL not in response.text


async def test_embedding_provider_failure_is_a_clean_503(world) -> None:
    world.search_error = ProviderUnavailableError(INTERNAL)

    response = await ask(world)

    assert response.status_code == 503 and INTERNAL not in response.text


async def test_unusable_model_reply_is_502(world) -> None:
    world.model.push("not json", "still not json")

    response = await world.client.post(
        "/coding/explain", headers=world.headers["asha"], json={"language": "python", "code": "x"}
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "The assistant couldn't produce a valid answer. Please try again."
    )


async def test_our_own_ai_quota_is_429_with_retry_after(world) -> None:
    for _ in range(world.ai_questions_per_minute):
        await ask(world)

    response = await ask(world)

    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60


async def test_code_runner_down_is_503(world) -> None:
    response = await world.client.post(
        "/code/run",
        headers=world.headers["asha"],
        json={"language": "python", "code": "print(1)"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "The code runner is unavailable. Please try again shortly."
    assert "runner down" not in response.text


async def test_oversized_body_is_413(world) -> None:
    response = await world.client.post(
        "/chat/ask", headers=world.headers["asha"], content=b"x" * (64 * 1024 + 1)
    )

    assert response.status_code == 413


async def test_upload_without_a_token_is_refused_before_the_body_is_read(world) -> None:
    files = {"file": ("c.json", b"{" + b" " * 2_000_000 + b"}", "application/json")}

    anonymous = await world.client.post("/admin/documents", files=files)
    student = await world.client.post(
        "/admin/documents", headers=world.headers["asha"], files=files, data={"language": "python"}
    )

    assert anonymous.status_code == 401 and anonymous.headers["WWW-Authenticate"] == "Bearer"
    assert student.status_code == 403


async def test_repeated_wrong_passwords_lock_the_account_for_a_while(world) -> None:
    for _ in range(2):
        wrong = {"username": "asha", "password": "wrong-password!"}
        assert (await world.client.post("/auth/login", json=wrong)).status_code == 401

    right = await world.client.post(
        "/auth/login", json={"username": "asha", "password": world.password}
    )
    unknown = await world.client.post(
        "/auth/login", json={"username": "nobody", "password": world.password}
    )

    assert right.status_code == 429 and int(right.headers["Retry-After"]) > 0
    assert "failed sign-ins" in right.json()["detail"]
    assert unknown.status_code == 401  # other usernames are unaffected
