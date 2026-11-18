"""Initial schema: users, course tree, documents, document files, chunks.

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ["users", "courses", "modules", "lessons", "documents", "document_files", "chunks"]


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.CheckConstraint("role IN ('admin', 'student')", name="ck_users_role_valid"),
        sa.CheckConstraint("username = lower(username)", name="ck_users_username_lowercase"),
    )
    op.create_table(
        "courses",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level", sa.String(50), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_courses"),
    )
    op.create_table(
        "modules",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("course_id", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_modules"),
        sa.UniqueConstraint("course_id", "position", name="uq_modules_course_position"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name="fk_modules_course_id_courses", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_modules_course_id", "modules", ["course_id"])
    op.create_table(
        "lessons",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("module_id", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_lessons"),
        sa.UniqueConstraint("module_id", "position", name="uq_lessons_module_position"),
        sa.ForeignKeyConstraint(
            ["module_id"], ["modules.id"], name="fk_lessons_module_id_modules", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_lessons_module_id", "lessons", ["module_id"])
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_documents_status_valid",
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_documents_size_positive"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name="fk_documents_course_id_courses", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
            name="fk_documents_uploaded_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_documents_course_id", "documents", ["course_id"])
    op.create_index("ix_documents_sha256", "documents", ["sha256"])
    op.create_table(
        "document_files",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.PrimaryKeyConstraint("document_id", name="pk_document_files"),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_files_document_id_documents",
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.String(100), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(100), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("embedding", postgresql.ARRAY(sa.REAL()), nullable=True),
        sa.Column("embedding_id", sa.String(200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chunks"),
        sa.UniqueConstraint("document_id", "position", name="uq_chunks_document_position"),
        sa.CheckConstraint(
            "(embedding IS NULL) = (embedding_id IS NULL)", name="ck_chunks_embedding_has_space"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_chunks_document_id_documents",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"], ["lessons.id"], name="fk_chunks_lesson_id_lessons", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_lesson_id", "chunks", ["lesson_id"])
    op.create_index("ix_chunks_embedding_id", "chunks", ["embedding_id"])

    # Supabase publishes every table through its REST "Data API" with a public anon key.
    # RLS with no policies gives the anon/authenticated roles nothing, while the app's
    # own role (the table owner) is unaffected. Harmless on Neon.
    for table in [*TABLES, "alembic_version"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
    for table in reversed(TABLES):
        op.drop_table(table)
