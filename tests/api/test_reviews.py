"""Step 23b: GET /me/reviews, the per-course spaced-review switch, owner-only data."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.api.progress import current_time
from app.db.models import ExerciseAttempt, User
from app.db.session import Database

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
DAY = timedelta(days=1)


async def attempt(database: Database, world, username: str, at: datetime, passed: bool) -> None:
    async with database.session() as session:
        user_id = await session.scalar(select(User.id).where(User.username == username))
        session.add(
            ExerciseAttempt(
                user_id=user_id,
                exercise_id=world.exercise_id,
                passed=passed,
                feedback="-",
                created_at=at,
            )
        )


async def switch(world, on: bool) -> None:
    response = await world.client.patch(
        f"/admin/courses/{world.course_id}",
        headers=world.headers["boss"],
        json={"spaced_review_enabled": on},
    )
    assert response.status_code == 200


async def reviews(world, username: str = "asha", now: datetime = T0) -> dict:
    world.app.dependency_overrides[current_time] = lambda: now
    response = await world.client.get(
        f"/me/reviews?course_id={world.course_id}", headers=world.headers[username]
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_switched_off_course_has_no_reviews(world, database: Database) -> None:
    await attempt(database, world, "asha", T0, False)

    body = await reviews(world, now=T0 + 2 * DAY)

    assert (body["enabled"], body["reviews"]) == (False, [])


async def test_a_failed_attempt_is_due_a_day_later(world, database: Database) -> None:
    await switch(world, True)
    await attempt(database, world, "asha", T0, False)

    early = await reviews(world, now=T0 + DAY - timedelta(minutes=1))
    (review,) = (await reviews(world, now=T0 + DAY))["reviews"]

    assert early["reviews"][0]["due"] is False
    assert review["due"] is True and review["interval_days"] == 1
    assert (review["lesson_title"], review["module_title"]) == ("Let", "Basics")


async def test_a_pass_when_due_moves_up_and_an_early_pass_does_not(
    world, database: Database
) -> None:
    await switch(world, True)
    for at in (T0, T0 + DAY, T0 + DAY + timedelta(minutes=5)):  # the last one is early
        await attempt(database, world, "asha", at, True)

    (review,) = (await reviews(world, now=T0 + 2 * DAY))["reviews"]

    assert review["interval_days"] == 3 and review["due"] is False
    assert datetime.fromisoformat(review["due_at"]) == T0 + 4 * DAY


async def test_students_only_see_their_own_reviews(world, database: Database) -> None:
    await switch(world, True)
    await attempt(database, world, "asha", T0, False)

    assert (await reviews(world, "ravi", now=T0 + 2 * DAY))["reviews"] == []


async def test_unknown_or_missing_course(world) -> None:
    headers = world.headers["asha"]

    unknown = await world.client.get("/me/reviews?course_id=nope", headers=headers)
    missing = await world.client.get("/me/reviews", headers=headers)

    assert (unknown.status_code, missing.status_code) == (404, 422)


async def test_students_cannot_switch_it(world) -> None:
    response = await world.client.patch(
        f"/admin/courses/{world.course_id}",
        headers=world.headers["asha"],
        json={"spaced_review_enabled": True},
    )

    assert response.status_code == 403
