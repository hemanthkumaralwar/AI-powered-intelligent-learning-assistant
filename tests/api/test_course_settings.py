"""Step 23a: the admin-only per-course switch for "Open in Practice", and the course id
that lets Arc open a cited lesson."""

import logging

import pytest

from app.api.schemas.chat import CitationResponse

pytestmark = pytest.mark.anyio


def path(world) -> str:
    return f"/admin/courses/{world.course_id}"


async def course_flag(world, headers) -> bool:
    courses = (await world.client.get("/courses", headers=headers)).json()
    return next(c for c in courses if c["id"] == world.course_id)["arc_practice_enabled"]


async def test_courses_start_switched_off(world) -> None:
    assert await course_flag(world, world.headers["asha"]) is False


async def test_admin_turns_it_on_and_students_see_it_at_once(
    world, caplog: pytest.LogCaptureFixture
) -> None:
    student = world.headers["asha"]
    assert await course_flag(world, student) is False  # now cached for 10 minutes

    with caplog.at_level(logging.INFO):
        response = await world.client.patch(
            path(world), headers=world.headers["boss"], json={"arc_practice_enabled": True}
        )

    assert response.status_code == 200 and response.json()["arc_practice_enabled"] is True
    assert await course_flag(world, student) is True  # the cache was cleared
    assert "course settings changed" in caplog.text and world.course_id in caplog.text

    off = {"arc_practice_enabled": False}
    await world.client.patch(path(world), headers=world.headers["boss"], json=off)
    assert await course_flag(world, student) is False


async def test_students_cannot_change_it(world) -> None:
    response = await world.client.patch(
        path(world), headers=world.headers["asha"], json={"arc_practice_enabled": True}
    )

    assert response.status_code == 403
    assert await course_flag(world, world.headers["asha"]) is False


@pytest.mark.parametrize(
    "body",
    [{}, {"arc_practice_enabled": None}, {"tutor": True}, {"arc_practice_enabled": "maybe"}],
    ids=["empty", "null-only", "unknown-field", "not-a-boolean"],
)
async def test_bad_bodies_are_422(world, body: dict) -> None:
    response = await world.client.patch(path(world), headers=world.headers["boss"], json=body)

    assert response.status_code == 422


async def test_unknown_course_is_404(world) -> None:
    response = await world.client.patch(
        "/admin/courses/nope", headers=world.headers["boss"], json={"arc_practice_enabled": True}
    )

    assert response.status_code == 404


async def test_citations_carry_the_course_id_in_answers_and_history(world) -> None:
    headers = world.headers["asha"]
    reply = (
        await world.client.post("/chat/ask", headers=headers, json={"question": "What is let?"})
    ).json()
    history = (
        await world.client.get(f"/chat/sessions/{reply['session_id']}", headers=headers)
    ).json()

    assert reply["citations"][0]["course_id"] == world.course_id
    assert history["messages"][1]["citations"][0]["course_id"] == world.course_id


def test_citations_saved_before_course_ids_still_load() -> None:
    saved = {
        "number": 1,
        "course_title": "JS",
        "module_title": "Basics",
        "lesson_id": "l1",
        "lesson_title": "Let",
        "section": "Explanation",
        "link": "/lessons/l1",
    }

    assert CitationResponse.model_validate(saved).course_id is None
