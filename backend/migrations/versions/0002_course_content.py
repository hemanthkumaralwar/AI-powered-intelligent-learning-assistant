"""Course content: course language, module/lesson content, document kind and tags,
quiz questions, exercises.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ["quiz_questions", "exercises"]


def upgrade() -> None:
    # Courses, modules, lessons and documents are still empty everywhere when this runs
    # (nothing could be uploaded before Step 8), so NOT NULL columns can be added directly.
    op.add_column("courses", sa.Column("language", sa.String(20), nullable=False))
    op.create_check_constraint(
        "ck_courses_language_valid",
        "courses",
        "language IN ('c', 'cpp', 'java', 'python', 'javascript', 'sql')",
    )
    for table in ("modules", "lessons"):
        # Backfill '{}' for safety, then drop the default to match the model.
        op.add_column(
            table,
            sa.Column(
                "content", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")
            ),
        )
        op.alter_column(table, "content", server_default=None)

    op.add_column("documents", sa.Column("kind", sa.String(20), nullable=False))
    op.create_check_constraint(
        "ck_documents_kind_valid", "documents", "kind IN ('course', 'notes')"
    )
    op.add_column("documents", sa.Column("module_id", sa.String(100), nullable=True))
    op.add_column("documents", sa.Column("lesson_id", sa.String(100), nullable=True))
    op.create_foreign_key(
        "fk_documents_module_id_modules",
        "documents",
        "modules",
        ["module_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_documents_lesson_id_lessons",
        "documents",
        "lessons",
        ["lesson_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_documents_module_id", "documents", ["module_id"])
    op.create_index("ix_documents_lesson_id", "documents", ["lesson_id"])

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_questions"),
        sa.UniqueConstraint("lesson_id", "position", name="uq_quiz_questions_lesson_position"),
        sa.CheckConstraint(
            "correct_index >= 0 AND correct_index < jsonb_array_length(options)",
            name="ck_quiz_questions_correct_index_in_options",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            name="fk_quiz_questions_lesson_id_lessons",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_quiz_questions_lesson_id", "quiz_questions", ["lesson_id"])
    op.create_table(
        "exercises",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("starter_code", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("hints", postgresql.JSONB(), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=True),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("bug_explanation", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_exercises"),
        sa.UniqueConstraint("lesson_id", "kind", name="uq_exercises_lesson_kind"),
        sa.CheckConstraint(
            "kind IN ('interactive', 'mini_challenge', 'bug_hunt')",
            name="ck_exercises_kind_valid",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            name="fk_exercises_lesson_id_lessons",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_exercises_lesson_id", "exercises", ["lesson_id"])

    # Same protection as 0001: no access through Supabase's public Data API.
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
    op.drop_index("ix_documents_lesson_id", "documents")
    op.drop_index("ix_documents_module_id", "documents")
    op.drop_constraint("fk_documents_lesson_id_lessons", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_module_id_modules", "documents", type_="foreignkey")
    op.drop_column("documents", "lesson_id")
    op.drop_column("documents", "module_id")
    op.drop_constraint("ck_documents_kind_valid", "documents", type_="check")
    op.drop_column("documents", "kind")
    for table in ("lessons", "modules"):
        op.drop_column(table, "content")
    op.drop_constraint("ck_courses_language_valid", "courses", type_="check")
    op.drop_column("courses", "language")
