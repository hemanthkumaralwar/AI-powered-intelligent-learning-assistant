"""Quiz attempts: marked tries at a lesson's quiz, counted in progress next to exercises.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=20), server_default="app", nullable=False),
        sa.Column("correct", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("answers", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_attempts"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_quiz_attempts_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            name="fk_quiz_attempts_lesson_id_lessons",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("source IN ('app', 'platform')", name="ck_quiz_attempts_source"),
        sa.CheckConstraint(
            "total > 0 AND correct >= 0 AND correct <= total", name="ck_quiz_attempts_score"
        ),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])
    op.create_index("ix_quiz_attempts_lesson_id", "quiz_attempts", ["lesson_id"])
    # Same protection as 0001: no access through Supabase's public Data API.
    op.execute("ALTER TABLE quiz_attempts ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("quiz_attempts")
