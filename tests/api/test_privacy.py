"""A student only ever sees their own data, students cannot use admin actions, logs carry
no personal data, and old chats are deleted."""

import logging
from datetime import timedelta

import pytest
from sqlalchemy import update

from app.db.models import ChatSession
from app.db.session import Database

pytestmark = pytest.mark.anyio

PRIVATE_QUESTION = "my private question about let and my cat Mittens"
PRIVATE_CODE = "secret_variable_mittens = 42"


async def test_another_students_chat_is_403_for_read_continue_and_delete(world) -> None:
    asha, ravi = world.headers["asha"], world.headers["ravi"]
    chat = await world.client.post("/chat/ask", headers=asha, json={"question": "What is let?"})
    session_id = chat.json()["session_id"]

    read = await world.client.get(f"/chat/sessions/{session_id}", headers=ravi)
    follow_up = await world.client.post(
        "/chat/ask", headers=ravi, json={"question": "And const?", "session_id": session_id}
    )
    delete = await world.client.delete(f"/chat/sessions/{session_id}", headers=ravi)
    listed = await world.client.get("/chat/sessions", headers=ravi)

    assert (read.status_code, follow_up.status_code, delete.status_code) == (403, 403, 403)
    assert listed.json() == []


async def test_attempts_and_progress_are_per_student(world) -> None:
    asha, ravi = world.headers["asha"], world.headers["ravi"]
    world.model.push('{"passed": false, "feedback": "Think about let."}')
    path = f"/exercises/{world.exercise_id}/attempts"
    await world.client.post(path, headers=asha, json={"code": "const x = 0;\nx = 1;"})

    ravis_attempts = await world.client.get(path, headers=ravi)
    ravis_progress = await world.client.get(
        f"/me/progress?course_id={world.course_id}", headers=ravi
    )
    ashas_progress = await world.client.get(
        f"/me/progress?course_id={world.course_id}", headers=asha
    )

    assert ravis_attempts.json() == []
    assert ravis_progress.json()["modules"][0]["mastery"] is None
    assert ashas_progress.json()["modules"][0]["mastery"] == 0.0


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/admin/documents"),
        ("POST", "/admin/reindex"),
        ("POST", "/admin/search"),
        ("DELETE", "/admin/courses/js"),
    ],
)
async def test_students_cannot_use_admin_actions(world, method: str, path: str) -> None:
    body = {"query": "let"} if path == "/admin/search" else None

    response = await world.client.request(method, path, headers=world.headers["asha"], json=body)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


async def test_a_student_cannot_make_themselves_admin(world) -> None:
    headers = world.headers["asha"]

    response = await world.client.patch("/auth/me", headers=headers, json={"role": "admin"})
    me = await world.client.get("/auth/me", headers=headers)

    assert response.status_code == 422 and me.json()["role"] == "student"


async def test_logs_hold_no_questions_code_passwords_or_tokens(
    world, caplog: pytest.LogCaptureFixture
) -> None:
    headers = world.headers["asha"]
    token = headers["Authorization"].removeprefix("Bearer ")
    world.model.push('{"summary": "s", "lines": [], "concepts": []}')

    with caplog.at_level(logging.DEBUG):
        await world.client.post("/chat/ask", headers=headers, json={"question": PRIVATE_QUESTION})
        await world.client.post(
            "/coding/explain", headers=headers, json={"language": "python", "code": PRIVATE_CODE}
        )
        await world.client.post(
            "/auth/login", json={"username": "asha", "password": world.password}
        )

    logged = caplog.text
    assert "chat answer outcome=" in logged  # the flows did log, as metadata
    for private in ("Mittens", PRIVATE_CODE, world.password, token):
        assert private not in logged


async def test_old_chats_are_deleted_when_their_owner_lists_chats(
    world, database: Database
) -> None:
    headers = world.headers["asha"]
    old = await world.client.post("/chat/ask", headers=headers, json={"question": "Old?"})
    new = await world.client.post("/chat/ask", headers=headers, json={"question": "New?"})
    async with database.session() as session:
        await session.execute(
            update(ChatSession)
            .where(ChatSession.id == old.json()["session_id"])
            .values(updated_at=ChatSession.updated_at - timedelta(days=91))
        )

    listed = await world.client.get("/chat/sessions", headers=headers)

    assert [chat["id"] for chat in listed.json()] == [new.json()["session_id"]]
    gone = await world.client.get(f"/chat/sessions/{old.json()['session_id']}", headers=headers)
    assert gone.status_code == 404


async def test_course_content_cache_is_cleared_when_an_admin_deletes_a_course(world) -> None:
    student, admin = world.headers["asha"], world.headers["boss"]
    before = await world.client.get("/courses", headers=student)

    deleted = await world.client.delete(f"/admin/courses/{world.course_id}", headers=admin)
    after = await world.client.get("/courses", headers=student)

    assert [c["id"] for c in before.json()] == [world.course_id]
    assert deleted.status_code == 204
    assert after.json() == []
