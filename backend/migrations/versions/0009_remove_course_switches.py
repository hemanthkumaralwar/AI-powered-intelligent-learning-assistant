"""Remove the per-course switches for "Open in Practice" and spaced review (both features
were removed from the app).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("courses", "spaced_review_enabled")
    op.drop_column("courses", "arc_practice_enabled")


def downgrade() -> None:
    # Restored as off for every course, which was the default.
    op.add_column(
        "courses",
        sa.Column("arc_practice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "courses",
        sa.Column("spaced_review_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
