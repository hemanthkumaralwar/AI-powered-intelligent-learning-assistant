"""Repository behaviour against a real (Neon test branch) PostgreSQL schema."""

import hashlib
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.errors import DuplicateError
from app.db.models import Chunk, Course, Document, DocumentFile, Lesson, Module, User
from app.db.repositories.chats import ChatRepository, NewMessage
from app.db.repositories.chunks import ChunkRepository, NewChunk
from app.db.repositories.courses import CourseRepository
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.users import UserRepository
from app.db.session import Database

pytestmark = pytest.mark.anyio


def make_course(course_id: str = "js-v1", title: str = "JavaScript") -> Course:
    return Course(
        id=course_id,
        title=title,
        language="javascript",
        level="Beginner",
        modules=[
            Module(
                id=f"{course_id}-mod-2",
                position=2,
                title="Functions",
                lessons=[Lesson(id=f"{course_id}-mod-2-lesson-1", position=1, title="Declaring")],
            ),
            Module(
                id=f"{course_id}-mod-1",
                position=1,
                title="Variables",
                lessons=[
                    Lesson(id=f"{course_id}-mod-1-lesson-2", position=2, title="const"),
                    Lesson(id=f"{course_id}-mod-1-lesson-1", position=1, title="let"),
                ],
            ),
        ],
    )


async def add_document(db: Database, content: bytes = b"lesson text", **kwargs) -> uuid.UUID:
    async with db.session() as session:
        if await CourseRepository(session).get("js-v1") is None:
            await CourseRepository(session).add(make_course())
        document = await DocumentRepository(session).add(
            course_id=kwargs.get("course_id", "js-v1"),
            filename="notes.txt",
            content_type="text/plain",
            content=content,
            uploaded_by=kwargs.get("uploaded_by"),
        )
        return document.id


async def count(db: Database, model: type) -> int:
    async with db.session() as session:
        return await session.scalar(select(func.count()).select_from(model))


# ---- users -------------------------------------------------------------------------


async def test_user_round_trip_is_case_insensitive(database: Database) -> None:
    async with database.session() as session:
        created = await UserRepository(session).add("Asha", "hash", "student")

    async with database.session() as session:
        users = UserRepository(session)
        by_name = await users.get_by_username("ASHA")
        by_id = await users.get(created.id)

    assert by_name is not None and by_id is not None
    assert by_name.id == by_id.id == created.id
    assert (by_name.username, by_name.role) == ("asha", "student")
    assert by_name.created_at is not None


async def test_unknown_user_is_none(database: Database) -> None:
    async with database.session() as session:
        users = UserRepository(session)
        assert await users.get(uuid.uuid4()) is None
        assert await users.get_by_username("nobody") is None


async def test_duplicate_username_differing_only_in_case(database: Database) -> None:
    async with database.session() as session:
        await UserRepository(session).add("ravi", "hash", "student")

    with pytest.raises(DuplicateError, match="username already exists"):
        async with database.session() as session:
            await UserRepository(session).add("Ravi", "hash", "admin")


async def test_invalid_role_is_rejected_by_the_database(database: Database) -> None:
    with pytest.raises(IntegrityError):
        async with database.session() as session:
            await UserRepository(session).add("mallory", "hash", "superuser")  # type: ignore[arg-type]


# ---- courses -----------------------------------------------------------------------


async def test_course_tree_round_trips_in_position_order(database: Database) -> None:
    async with database.session() as session:
        await CourseRepository(session).add(make_course())

    async with database.session() as session:
        course = await CourseRepository(session).get("js-v1")

    assert course is not None
    assert [m.title for m in course.modules] == ["Variables", "Functions"]
    assert [lesson.title for lesson in course.modules[0].lessons] == ["let", "const"]


async def test_course_listing_is_sorted_and_starts_empty(database: Database) -> None:
    async with database.session() as session:
        repo = CourseRepository(session)
        assert await repo.list_courses() == []
        await repo.add(make_course("py-v1", "Python"))
        await repo.add(make_course("c-v1", "C"))

    async with database.session() as session:
        assert [c.title for c in await CourseRepository(session).list_courses()] == ["C", "Python"]


async def test_unknown_course_is_none(database: Database) -> None:
    async with database.session() as session:
        assert await CourseRepository(session).get("missing") is None


async def test_duplicate_course_is_rejected(database: Database) -> None:
    async with database.session() as session:
        await CourseRepository(session).add(make_course())

    with pytest.raises(DuplicateError):
        async with database.session() as session:
            await CourseRepository(session).add(make_course())


async def test_deleting_a_course_removes_its_tree(database: Database) -> None:
    await add_document(database)
    async with database.session() as session:
        await session.delete(await CourseRepository(session).get("js-v1"))

    assert await count(database, Module) == 0
    assert await count(database, Lesson) == 0
    assert await count(database, DocumentFile) == 0


# ---- documents ---------------------------------------------------------------------


async def test_document_stores_size_hash_and_content(database: Database) -> None:
    document_id = await add_document(database, content=b"const x = 1;")

    async with database.session() as session:
        documents = DocumentRepository(session)
        document = await documents.get(document_id)
        content = await documents.get_content(document_id)

    assert document is not None
    assert (document.size_bytes, document.status) == (12, "pending")
    assert document.sha256 == hashlib.sha256(b"const x = 1;").hexdigest()
    assert content == b"const x = 1;"


async def test_empty_document_is_rejected(database: Database) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        await add_document(database, content=b"")


async def test_document_listing_filters_by_course(database: Database) -> None:
    first = await add_document(database, content=b"a")
    second = await add_document(database, content=b"b")

    async with database.session() as session:
        documents = DocumentRepository(session)
        all_ids = {d.id for d in await documents.list_documents()}
        in_course = await documents.list_documents("js-v1")
        elsewhere = await documents.list_documents("other-course")

    assert all_ids == {first, second}
    assert len(in_course) == 2
    assert elsewhere == []


async def test_set_status_reports_whether_the_document_exists(database: Database) -> None:
    document_id = await add_document(database)

    async with database.session() as session:
        documents = DocumentRepository(session)
        assert await documents.set_status(document_id, "failed", "no text found") is True
        assert await documents.set_status(uuid.uuid4(), "ready") is False

    async with database.session() as session:
        document = await DocumentRepository(session).get(document_id)
    assert (document.status, document.error_message) == ("failed", "no text found")


async def test_deleting_a_document_removes_file_and_chunks(database: Database) -> None:
    document_id = await add_document(database)
    async with database.session() as session:
        await ChunkRepository(session).replace_for_document(
            document_id, [NewChunk(id="c1", position=0, section="intro", text="hello")]
        )

    async with database.session() as session:
        documents = DocumentRepository(session)
        assert await documents.delete(document_id) is True
        assert await documents.delete(document_id) is False

    assert await count(database, DocumentFile) == 0
    assert await count(database, Chunk) == 0


async def test_deleting_the_uploader_keeps_the_document(database: Database) -> None:
    async with database.session() as session:
        admin = await UserRepository(session).add("admin", "hash", "admin")
    document_id = await add_document(database, uploaded_by=admin.id)

    async with database.session() as session:
        await session.delete(await session.get(User, admin.id))

    async with database.session() as session:
        document = await DocumentRepository(session).get(document_id)
    assert document is not None and document.uploaded_by is None


# ---- chunks ------------------------------------------------------------------------


async def test_replacing_chunks_swaps_the_whole_set(database: Database) -> None:
    document_id = await add_document(database)
    async with database.session() as session:
        chunks = ChunkRepository(session)
        await chunks.replace_for_document(
            document_id,
            [
                NewChunk(id="old-1", position=0, section="a", text="old one"),
                NewChunk(id="old-2", position=1, section="b", text="old two"),
            ],
        )
        await chunks.replace_for_document(
            document_id,
            [
                NewChunk(
                    id="new-1",
                    position=0,
                    section="explanation",
                    text="new",
                    lesson_id="js-v1-mod-1-lesson-1",
                    metadata={"lesson_title": "let"},
                )
            ],
        )

    async with database.session() as session:
        stored = await ChunkRepository(session).list_for_document(document_id)

    assert [c.id for c in stored] == ["new-1"]
    assert stored[0].lesson_id == "js-v1-mod-1-lesson-1"
    assert stored[0].extra == {"lesson_title": "let"}
    assert stored[0].embedding is None


async def test_embeddings_are_stored_and_filtered_by_vector_space(database: Database) -> None:
    document_id = await add_document(database)
    async with database.session() as session:
        chunks = ChunkRepository(session)
        await chunks.replace_for_document(
            document_id,
            [
                NewChunk(id="c0", position=0, section="s", text="zero"),
                NewChunk(id="c1", position=1, section="s", text="one"),
                NewChunk(id="c2", position=2, section="s", text="two"),
            ],
        )
        await chunks.set_embeddings("gemini:m:3", {"c1": [0.1, 0.2, 0.3], "c0": [1.0, 0.0, 0.0]})
        await chunks.set_embeddings("huggingface:m:2", {"c2": [0.5, 0.5]})
        await chunks.set_embeddings("gemini:m:3", {})

    async with database.session() as session:
        not_ready_yet = await ChunkRepository(session).list_searchable("gemini:m:3")
        await DocumentRepository(session).set_status(document_id, "ready")

    async with database.session() as session:
        chunks = ChunkRepository(session)
        gemini = await chunks.list_searchable("gemini:m:3")
        other = await chunks.list_searchable("openai:m:3")
        stale = await chunks.count_other_spaces("gemini:m:3")

    assert not_ready_yet == []  # a document still being indexed is never searchable
    assert [c.id for c in gemini] == ["c0", "c1"]
    assert gemini[1].embedding == pytest.approx([0.1, 0.2, 0.3])
    assert other == []
    assert stale == 1  # c2 lives in the huggingface space


# ---- Step 8 additions -----------------------------------------------------------------


async def test_course_exists_and_delete(database: Database) -> None:
    await add_document(database)
    async with database.session() as session:
        courses = CourseRepository(session)
        assert await courses.exists("js-v1") is True
        assert await courses.exists("missing") is False
        assert await courses.delete("js-v1") is True
        assert await courses.delete("js-v1") is False

    assert await count(database, Document) == 0


async def test_lesson_and_module_lookup(database: Database) -> None:
    async with database.session() as session:
        await CourseRepository(session).add(make_course())

    async with database.session() as session:
        courses = CourseRepository(session)
        lesson = await courses.get_lesson("js-v1-mod-1-lesson-2")
        module = await courses.get_module("js-v1-mod-2")
        assert await courses.get_lesson("missing") is None
        assert await courses.get_module("missing") is None

    assert lesson is not None and lesson.module.course_id == "js-v1"
    assert lesson.exercises == []
    assert module is not None and module.title == "Functions"


async def test_chat_messages_keep_order_and_a_concurrent_append_conflicts(
    database: Database,
) -> None:
    async with database.session() as session:
        user = await UserRepository(session).add("asha", "hash", "student")
        chat = await ChatRepository(session).create_session(user.id, "What is let?")
        await ChatRepository(session).add_messages(
            chat.id,
            0,
            [
                NewMessage("user", "What is let?"),
                NewMessage("assistant", "Block-scoped.", None, True),
            ],
        )

    async with database.session() as session:
        repo = ChatRepository(session)
        assert await repo.count_messages(chat.id) == 2
        assert [m.content for m in await repo.recent_messages(chat.id, 1)] == ["Block-scoped."]
        assert [m.position for m in await repo.messages(chat.id)] == [0, 1]

    # A second writer that read the same message count tries the same positions.
    with pytest.raises(DuplicateError):
        async with database.session() as session:
            await ChatRepository(session).add_messages(chat.id, 1, [NewMessage("user", "Again?")])

    async with database.session() as session:
        await ChatRepository(session).delete_session(chat.id)
    async with database.session() as session:
        assert await ChatRepository(session).count_messages(chat.id) == 0
