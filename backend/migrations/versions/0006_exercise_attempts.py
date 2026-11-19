"""Exercise attempts: AI-graded results of bug hunts, challenges and interactive exercises.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exercise_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exercise_attempts"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_exercise_attempts_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["exercise_id"],
            ["exercises.id"],
            name="fk_exercise_attempts_exercise_id_exercises",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_exercise_attempts_user_id", "exercise_attempts", ["user_id"])
    op.create_index("ix_exercise_attempts_exercise_id", "exercise_attempts", ["exercise_id"])
    # Same protection as 0001: no access through Supabase's public Data API.
    op.execute("ALTER TABLE exercise_attempts ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("exercise_attempts")
