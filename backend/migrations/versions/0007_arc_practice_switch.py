"""Per-course admin switch for "Open in Practice" in Arc (Step 23a).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Off for every existing course: an admin opts each course in.
    op.add_column(
        "courses",
        sa.Column("arc_practice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("courses", "arc_practice_enabled")
