"""ORM models: users, the course tree, uploaded documents, their chunks, and chats.

Fixed-value columns are TEXT plus a CHECK constraint rather than Postgres ENUM types,
which are awkward to change in migrations. Vectors are plain REAL[]: FAISS does the
similarity search in memory; Postgres only keeps vectors so the index can be rebuilt
after a restart.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import (
    REAL,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

Role = Literal["admin", "student"]
DocumentStatus = Literal["pending", "processing", "ready", "failed"]
# Only course JSON is stored; kind is kept as an explicit, checked marker for future types.
DocumentKind = Literal["course"]
ExerciseKind = Literal["interactive", "mini_challenge", "bug_hunt"]
ChatRole = Literal["user", "assistant"]

# Stable constraint names keep Alembic migrations deterministic across databases.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    """An account. Deliberately no email or real name: less personal data to protect."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'student')", name="role_valid"),
        CheckConstraint("username = lower(username)", name="username_lowercase"),
        CheckConstraint("level IN ('beginner', 'intermediate', 'advanced')", name="level_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    # Explanation depth for chat and coding answers (app/llm/prompt_levels.py).
    # The Python default sets it on new objects (a server default alone would leave the
    # attribute unloaded after insert); the server default covers rows from before 0005.
    level: Mapped[str] = mapped_column(
        String(20), default="beginner", server_default=text("'beginner'")
    )


class Course(TimestampMixin, Base):
    """Keyed by the `courseId` from the course JSON (e.g. "javascript-beginner-v1")."""

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "language IN ('c', 'cpp', 'java', 'python', 'javascript', 'sql')",
            name="language_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str | None] = mapped_column(String(50))
    # Programming language of the course's exercises (the course JSON does not say).
    # The check constraint above also makes every course a coding course, which the
    # per-course Nexus switch below relies on: if non-coding courses are ever allowed, the
    # switch must refuse them (Step 23a).
    language: Mapped[str] = mapped_column(String(20))
    # Admin switch (Step 23a): Nexus answers citing this course offer "Open in Practice"
    # (the field keeps its first name, arc_practice_enabled: it is part of the API).
    # A Python default for new objects; the server default for rows from before 0007.
    arc_practice_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    # Admin switch (Step 23b): students see which attempted lessons are due for review.
    spaced_review_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )

    modules: Mapped[list["Module"]] = relationship(
        back_populates="course",
        order_by="Module.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Module(Base):
    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("course_id", "position", name="uq_modules_course_position"),)

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    # Teaching text only (e.g. moduleExplanation); never anything that reveals answers.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="module",
        order_by="Lesson.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("module_id", "position", name="uq_lessons_module_position"),)

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    module_id: Mapped[str] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    objective: Mapped[str | None] = mapped_column(Text)
    # Teaching sections only (explanation, concepts, examples...). Quizzes, solutions and
    # answer-bearing widgets are never stored here: this is what students are shown.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    module: Mapped[Module] = relationship(back_populates="lessons")
    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        order_by="QuizQuestion.position", cascade="all, delete-orphan", passive_deletes=True
    )
    exercises: Mapped[list["Exercise"]] = relationship(
        order_by="Exercise.kind", cascade="all, delete-orphan", passive_deletes=True
    )


class Document(TimestampMixin, Base):
    """An uploaded file. Its bytes live in `document_files` so listings never load them."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')", name="status_valid"
        ),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        CheckConstraint("kind IN ('course')", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    # Lets Step 8 spot re-uploads of an identical file.
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class DocumentFile(Base):
    __tablename__ = "document_files"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    content: Mapped[bytes] = mapped_column(LargeBinary)


class Chunk(Base):
    """A searchable piece of a document, with its vector once embedded."""

    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "position", name="uq_chunks_document_position"),
        # A vector is meaningless without knowing which model space it belongs to.
        CheckConstraint("(embedding IS NULL) = (embedding_id IS NULL)", name="embedding_has_space"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[str | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(100))
    text: Mapped[str] = mapped_column(Text)
    # "metadata" is reserved on declarative classes, so the attribute is `extra`.
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(REAL))
    embedding_id: Mapped[str | None] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QuizQuestion(Base):
    """A multiple-choice question from a lesson. `correct_index` is never sent to students
    before they answer (Step 17)."""

    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("lesson_id", "position", name="uq_quiz_questions_lesson_position"),
        CheckConstraint(
            "correct_index >= 0 AND correct_index < jsonb_array_length(options)",
            name="correct_index_in_options",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str]] = mapped_column(JSONB)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text)


class Exercise(Base):
    """A coding exercise from a lesson. `solution` and `bug_explanation` are for admins
    and scoring only, never shown to students."""

    __tablename__ = "exercises"
    __table_args__ = (
        UniqueConstraint("lesson_id", "kind", name="uq_exercises_lesson_kind"),
        CheckConstraint("kind IN ('interactive', 'mini_challenge', 'bug_hunt')", name="kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255))
    instructions: Mapped[str] = mapped_column(Text)
    starter_code: Mapped[str] = mapped_column(Text)
    expected_output: Mapped[str | None] = mapped_column(Text)
    hints: Mapped[list[str]] = mapped_column(JSONB, default=list)
    difficulty: Mapped[str | None] = mapped_column(String(20))
    solution: Mapped[str | None] = mapped_column(Text)
    bug_explanation: Mapped[str | None] = mapped_column(Text)


class ChatSession(TimestampMixin, Base):
    """One conversation. Only its owner may read or delete it (checked in ChatService).

    `updated_at` is bumped whenever messages are added, so lists sort by last activity.
    """

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(80))


class ChatMessage(Base):
    """A question or an answer. `position` orders a session's messages exactly (timestamps
    can tie), and its uniqueness turns two simultaneous writes into a clean conflict."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "position", name="uq_chat_messages_session_position"),
        CheckConstraint("role IN ('user', 'assistant')", name="role_valid"),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    # User messages: the standalone question actually searched, when it was rewritten.
    standalone: Mapped[str | None] = mapped_column(Text)
    # Assistant messages: whether the answer came from the course, and its citations.
    grounded: Mapped[bool | None] = mapped_column(Boolean)
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExerciseAttempt(Base):
    """A graded try at a course exercise. Only the result is kept, not the student's code:
    progress analysis (Step 18) needs pass/fail, and less personal data is stored."""

    __tablename__ = "exercise_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True
    )
    passed: Mapped[bool] = mapped_column(Boolean)
    feedback: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
