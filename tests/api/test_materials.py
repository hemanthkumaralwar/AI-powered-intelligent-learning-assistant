"""Course JSON upload (admin) and course content (students) end to end on the Neon test schema."""

import copy
import json
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import argon2
import httpx2
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select

from app.auth.passwords import PasswordHasher
from app.auth.seed import seed_admin
from app.auth.service import AuthService
from app.auth.tokens import TokenService
from app.core.config import Settings
from app.db.models import Chunk, Course, Document, Exercise, Lesson, Module, QuizQuestion
from app.db.session import Database
from app.main import create_app
from app.providers.errors import ProviderUnavailableError
from app.runner.fake import FakeRunner
from app.runner.quota import QuotaLimits, RunQuota
from app.runner.service import CodeRunnerService

pytestmark = pytest.mark.anyio

PASSWORD = "Str0ng-Passphrase!"  # noqa: S105 - test fixture value
REAL_COURSE = (
    Path(__file__).resolve().parents[2] / "eval" / "materials" / "javascript-beginner.json"
)
ANSWER_MARKERS = ("correct_index", "correctAnswer", "solution", "fixedCode", "bug_explanation")


def small_course() -> dict:
    course = copy.deepcopy(json.loads(REAL_COURSE.read_bytes()))
    course["course"]["courseId"] = "small-js"
    modules = course["course"]["modules"][:2]
    for m, module in enumerate(modules, 1):
        module["moduleId"] = f"small-js-mod-{m}"
        module["lessons"] = module["lessons"][:2]
        for n, lesson in enumerate(module["lessons"], 1):
            lesson["lessonId"] = f"small-js-mod-{m}-lesson-{n}"
    course["course"]["modules"] = modules
    return course


@pytest.fixture
async def api(database: Database) -> AsyncIterator[httpx2.AsyncClient]:
    hasher = PasswordHasher(argon2.PasswordHasher(time_cost=1, memory_cost=8, parallelism=1))
    auth = AuthService(hasher, TokenService("j" * 64, timedelta(minutes=30)))
    runner = CodeRunnerService([FakeRunner()], None, RunQuota(QuotaLimits(9, 9, 9)))
    app = create_app(
        Settings(
            _env_file=None,
            environment="test",
            log_level="WARNING",
            llm_provider="fake",
            embedding_provider="fake",
            embedding_document_texts_per_minute=100_000,
            embedding_query_texts_per_minute=100_000,
        ),
        database=database,
        auth=auth,
        code_runner=runner,
    )
    await seed_admin(database, auth, "admin", SecretStr(PASSWORD))
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/auth/register", json={"username": "student", "password": PASSWORD})
            # Tests reach the app's services (e.g. to wait for background indexing).
            client.app_state = app.state  # type: ignore[attr-defined]
            yield client


async def token(api: httpx2.AsyncClient, username: str) -> dict[str, str]:
    response = await api.post("/auth/login", json={"username": username, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def upload(api, headers, name: str, content: bytes, **form) -> httpx2.Response:
    return await api.post(
        "/admin/documents", headers=headers, files={"file": (name, content)}, data=form
    )


async def count(database: Database, model: type) -> int:
    async with database.session() as session:
        return await session.scalar(select(func.count()).select_from(model))


# ---- Done-when: the real course --------------------------------------------------------


async def test_real_course_loads_as_8_modules_64_lessons_640_questions(
    api: httpx2.AsyncClient, database: Database
) -> None:
    admin = await token(api, "admin")

    response = await upload(
        api, admin, "javascript-beginner.json", REAL_COURSE.read_bytes(), language="javascript"
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["course_id"], body["status"]) == ("javascript-beginner-v1", "pending")
    assert await count(database, Course) == 1
    assert await count(database, Module) == 8
    assert await count(database, Lesson) == 64
    assert await count(database, QuizQuestion) == 640
    assert await count(database, Exercise) == 192


# ---- admin upload rules ----------------------------------------------------------------


async def test_reupload_is_409_until_the_course_is_deleted(
    api: httpx2.AsyncClient, database: Database
) -> None:
    admin = await token(api, "admin")
    raw = json.dumps(small_course()).encode()
    assert (await upload(api, admin, "c.json", raw, language="javascript")).status_code == 201

    again = await upload(api, admin, "c.json", raw, language="javascript")
    assert again.status_code == 409
    assert "Delete it first" in again.json()["detail"]

    assert (await api.delete("/admin/courses/small-js", headers=admin)).status_code == 204
    assert await count(database, Document) == 0
    assert (await upload(api, admin, "c.json", raw, language="javascript")).status_code == 201
    assert (await api.delete("/admin/courses/nope", headers=admin)).status_code == 404


async def test_module_ids_used_by_another_course_are_409(api: httpx2.AsyncClient) -> None:
    admin = await token(api, "admin")
    await upload(api, admin, "a.json", json.dumps(small_course()).encode(), language="javascript")
    other = small_course()
    other["course"]["courseId"] = "other-course"

    response = await upload(api, admin, "b.json", json.dumps(other).encode(), language="javascript")

    assert response.status_code == 409
    assert "already used by another course" in response.json()["detail"]


@pytest.mark.parametrize(
    ("name", "content", "form", "status", "message"),
    [
        ("c.json", b"{oops", {"language": "javascript"}, 422, "Invalid JSON"),
        ("c.json", b'{"course": {"courseId": "x"}}', {"language": "javascript"}, 422, "schema"),
        ("c.json", b"MZ\x90\x00renamed-exe", {"language": "javascript"}, 422, "UTF-8|JSON"),
        ("c.json", b"{}", {}, 422, ""),
        ("c.json", b"{}", {"language": "cobol"}, 422, ""),
        ("notes.txt", b"hello", {"language": "javascript"}, 415, "Convert other material"),
        ("deck.pdf", b"%PDF-1.7", {"language": "javascript"}, 415, "Convert other material"),
        ("run.exe", b"MZ", {"language": "javascript"}, 415, "Convert other material"),
    ],
    ids=[
        "broken-json",
        "schema-mismatch",
        "renamed-binary",
        "no-language",
        "bad-language",
        "txt",
        "pdf",
        "exe",
    ],
)
async def test_bad_uploads_are_rejected(
    api: httpx2.AsyncClient, name: str, content: bytes, form: dict, status: int, message: str
) -> None:
    admin = await token(api, "admin")

    response = await upload(api, admin, name, content, **form)

    assert response.status_code == status, response.text
    if message:
        assert any(part in str(response.json()["detail"]) for part in message.split("|"))


async def test_oversized_upload_is_413_before_parsing(api: httpx2.AsyncClient) -> None:
    admin = await token(api, "admin")

    big = b"x" * (10 * 1024 * 1024 + 1)
    response = await upload(api, admin, "big.json", big, language="javascript")

    assert response.status_code == 413


async def test_other_endpoints_have_a_small_body_limit(api: httpx2.AsyncClient) -> None:
    response = await api.post(
        "/auth/login",
        content=b"{" + b" " * 70_000 + b"}",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


async def test_students_cannot_use_admin_endpoints(api: httpx2.AsyncClient) -> None:
    student = await token(api, "student")

    assert (await upload(api, student, "c.json", b"{}", language="javascript")).status_code == 403
    assert (await api.get("/admin/documents", headers=student)).status_code == 403
    assert (await api.delete("/admin/courses/x", headers=student)).status_code == 403
    assert (await api.get("/admin/documents", headers={})).status_code == 401


# ---- students see content, never answers ------------------------------------------------


async def test_student_views_contain_no_answers(api: httpx2.AsyncClient) -> None:
    admin, student = await token(api, "admin"), await token(api, "student")
    await upload(api, admin, "c.json", json.dumps(small_course()).encode(), language="javascript")

    courses = await api.get("/courses", headers=student)
    outline = await api.get("/courses/small-js", headers=student)
    lesson = await api.get("/lessons/small-js-mod-1-lesson-1", headers=student)

    assert [c["id"] for c in courses.json()] == ["small-js"]
    assert courses.json()[0]["language"] == "javascript"
    assert [len(m["lessons"]) for m in outline.json()["modules"]] == [2, 2]
    body = lesson.json()
    assert {e["kind"] for e in body["exercises"]} == {"interactive", "mini_challenge", "bug_hunt"}
    assert "lessonExplanation" in body["content"]
    for response in (courses, outline, lesson):
        assert not [marker for marker in ANSWER_MARKERS if marker in response.text]
    fixed_code = small_course()["course"]["modules"][0]["lessons"][0]["bugHunt"]["fixedCode"]
    assert fixed_code not in lesson.text


async def test_missing_course_or_lesson_is_404(api: httpx2.AsyncClient) -> None:
    student = await token(api, "student")

    assert (await api.get("/courses/nope", headers=student)).status_code == 404
    assert (await api.get("/lessons/nope", headers=student)).status_code == 404
    # Anonymous access to course content is allowed since Step 24: test_public_access.py


async def test_only_admins_download_the_original_course_json(api: httpx2.AsyncClient) -> None:
    admin, student = await token(api, "admin"), await token(api, "student")
    raw = json.dumps(small_course()).encode()
    document = (await upload(api, admin, 'my "course"\r\n.json', raw, language="javascript")).json()

    download = await api.get(f"/admin/documents/{document['id']}/download", headers=admin)
    assert download.status_code == 200
    assert b"correctAnswer" in download.content
    disposition = download.headers["content-disposition"]
    assert disposition.startswith("attachment; filename*=UTF-8''")
    encoded_name = disposition.removeprefix("attachment; filename*=UTF-8''")
    assert not {'"', "\r", "\n", " "} & set(encoded_name)
    assert download.headers["x-content-type-options"] == "nosniff"

    as_student = f"/admin/documents/{document['id']}/download"
    assert (await api.get(as_student, headers=student)).status_code == 403
    # The old notes endpoints are gone.
    assert (await api.get("/materials", headers=student)).status_code == 404


async def test_admin_lists_and_deletes_documents(api: httpx2.AsyncClient) -> None:
    admin = await token(api, "admin")
    first = small_course()
    second = small_course()
    second["course"]["courseId"] = "second"
    for module in second["course"]["modules"]:
        module["moduleId"] = "second-" + module["moduleId"]
        for lesson in module["lessons"]:
            lesson["lessonId"] = "second-" + lesson["lessonId"]
    a = (await upload(api, admin, "a.json", json.dumps(first).encode(), language="python")).json()
    await upload(api, admin, "b.json", json.dumps(second).encode(), language="python")

    assert len((await api.get("/admin/documents", headers=admin)).json()) == 2
    assert len((await api.get("/admin/documents?course_id=second", headers=admin)).json()) == 1
    assert (await api.delete(f"/admin/documents/{a['id']}", headers=admin)).status_code == 204
    assert (await api.delete(f"/admin/documents/{a['id']}", headers=admin)).status_code == 404
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await api.get(f"/admin/documents/{missing}/download", headers=admin)).status_code == 404


# ---- indexing, search and re-index (fake embeddings) ------------------------------------


async def upload_and_index(api: httpx2.AsyncClient, admin: dict) -> dict:
    response = await upload(
        api, admin, "c.json", json.dumps(small_course()).encode(), language="javascript"
    )
    await api.app_state.indexing.wait_until_idle()
    return response.json()


async def test_upload_is_indexed_in_the_background(api: httpx2.AsyncClient) -> None:
    admin = await token(api, "admin")

    document = await upload_and_index(api, admin)

    listed = (await api.get("/admin/documents", headers=admin)).json()
    assert [(d["id"], d["status"], d["error_message"]) for d in listed] == [
        (document["id"], "ready", None)
    ]
    assert api.app_state.indexing.index.course_size("small-js") > 20


async def test_admin_search_finds_the_chunk(api: httpx2.AsyncClient, database: Database) -> None:
    admin = await token(api, "admin")
    await upload_and_index(api, admin)
    async with database.session() as session:
        chunk = (await session.scalars(select(Chunk).order_by(Chunk.position).offset(5))).first()

    response = await api.post(
        "/admin/search", headers=admin, json={"query": chunk.text, "course_id": "small-js", "k": 3}
    )

    hits = response.json()
    assert response.status_code == 200
    assert hits[0]["chunk_id"] == chunk.id
    assert set(hits[0]) == {"chunk_id", "score", "course_id", "lesson_id", "section", "text"}
    assert len(hits) == 3


@pytest.mark.parametrize("body", [{"query": ""}, {"query": "x", "k": 0}, {"query": "x", "k": 21}])
async def test_search_validates_input(api: httpx2.AsyncClient, body: dict) -> None:
    response = await api.post("/admin/search", headers=await token(api, "admin"), json=body)

    assert response.status_code == 422


async def test_deleting_a_course_or_document_removes_its_vectors(api: httpx2.AsyncClient) -> None:
    admin = await token(api, "admin")
    document = await upload_and_index(api, admin)
    index = api.app_state.indexing.index

    await api.delete(f"/admin/documents/{document['id']}", headers=admin)
    assert index.size == 0

    await upload_and_index(api, admin)  # the course still exists, so re-upload is refused
    await api.delete("/admin/courses/small-js", headers=admin)
    assert index.course_size("small-js") == 0


async def test_reindex_requeues_every_document(api: httpx2.AsyncClient) -> None:
    admin = await token(api, "admin")
    await upload_and_index(api, admin)

    response = await api.post("/admin/reindex", headers=admin)
    await api.app_state.indexing.wait_until_idle()

    assert (response.status_code, response.json()) == (202, {"queued": 1})
    assert (await api.get("/admin/documents", headers=admin)).json()[0]["status"] == "ready"


async def test_students_cannot_search_or_reindex(api: httpx2.AsyncClient) -> None:
    student = await token(api, "student")

    assert (
        await api.post("/admin/search", headers=student, json={"query": "x"})
    ).status_code == 403
    assert (await api.post("/admin/reindex", headers=student)).status_code == 403


async def test_search_is_503_when_embedding_is_down(api: httpx2.AsyncClient, monkeypatch) -> None:
    async def down(*args, **kwargs):
        raise ProviderUnavailableError("gemini server error 503")

    monkeypatch.setattr(api.app_state.indexing._embedder, "embed_query", down)

    response = await api.post(
        "/admin/search", headers=await token(api, "admin"), json={"query": "x"}
    )

    assert response.status_code == 503
    assert "gemini" not in response.text
