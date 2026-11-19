"""Chat history: chat_sessions and chat_messages.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ["chat_sessions", "chat_messages"]


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_sessions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_chat_sessions_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("standalone", sa.Text(), nullable=True),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
        sa.UniqueConstraint("session_id", "position", name="uq_chat_messages_session_position"),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role_valid"),
        sa.CheckConstraint("position >= 0", name="ck_chat_messages_position_non_negative"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name="fk_chat_messages_session_id_chat_sessions",
            ondelete="CASCADE",
        ),
    )

    # Same protection as 0001: no access through Supabase's public Data API.
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
