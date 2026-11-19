"""User explanation level (beginner, intermediate, advanced).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The server default fills existing rows, so every account starts as a beginner.
    op.add_column(
        "users",
        sa.Column("level", sa.String(20), nullable=False, server_default=sa.text("'beginner'")),
    )
    op.create_check_constraint(
        "ck_users_level_valid", "users", "level IN ('beginner', 'intermediate', 'advanced')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_level_valid", "users", type_="check")
    op.drop_column("users", "level")
