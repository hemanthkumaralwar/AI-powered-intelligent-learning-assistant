"""Step 24: course content is public within an app-wide guest quota; everything else
still needs a token."""

import re
import uuid

import pytest

from app.core.quota import MINUTE, Quota, QuotaRule

pytestmark = pytest.mark.anyio

PUBLIC = {"GET /courses", "GET /courses/{course_id}", "GET /lessons/{lesson_id}"}
# Open by design: health check, sign-up and sign-in.
ANONYMOUS = {"GET /health", "POST /auth/register", "POST /auth/login"}


def guest_limit(world, limit: int) -> None:
    world.app.state.guest_quota = Quota(
        [QuotaRule("Lots of visitors", limit, MINUTE, per_user=False)]
    )


async def test_guests_can_browse_and_read(world) -> None:
    courses = await world.client.get("/courses")
    outline = await world.client.get(f"/courses/{world.course_id}")
    lesson = await world.client.get("/lessons/js-m1-l1")

    assert [c["id"] for c in courses.json()] == [world.course_id]
    assert outline.status_code == 200 and lesson.status_code == 200
    # The exercise's reference solution ("let x = 0; ...") is never sent; its starter
    # code ("const x = 0; ...") is.
    assert "const x = 0;" in lesson.text and "let x = 0;" not in lesson.text


async def test_guests_share_one_quota_and_a_real_token_skips_it(world) -> None:
    guest_limit(world, 2)
    for _ in range(2):
        assert (await world.client.get("/courses")).status_code == 200

    guest = await world.client.get("/courses")
    fake_token = await world.client.get("/courses", headers={"Authorization": "Bearer nope"})
    student = await world.client.get("/courses", headers=world.headers["asha"])

    assert guest.status_code == 429 and int(guest.headers["Retry-After"]) >= 1
    assert fake_token.status_code == 429  # a bad token is still a guest
    assert student.status_code == 200


async def test_everything_else_still_needs_a_token(world) -> None:
    paths = world.app.openapi()["paths"]
    protected = [
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
        if f"{method.upper()} {path}" not in PUBLIC | ANONYMOUS
    ]
    assert len(protected) >= 20

    for method, path in protected:
        concrete = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
        response = await world.client.request(method, concrete)
        assert response.status_code == 401, f"{method} {path}: {response.status_code}"
