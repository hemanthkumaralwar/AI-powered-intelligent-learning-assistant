"""Course JSON only: drop the notes tag columns and restrict documents.kind to 'course'.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Never delete uploaded material silently: if notes exist, stop and let an admin
    # decide (DELETE /admin/documents/{id} on the previous release), then redeploy.
    notes = op.get_bind().scalar(sa.text("SELECT count(*) FROM documents WHERE kind = 'notes'"))
    if notes:
        raise RuntimeError(
            f"{notes} notes document(s) exist. Delete them via the API before upgrading: "
            "notes are no longer supported (convert them to course JSON instead)."
        )
    op.drop_index("ix_documents_lesson_id", "documents")
    op.drop_index("ix_documents_module_id", "documents")
    op.drop_constraint("fk_documents_lesson_id_lessons", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_module_id_modules", "documents", type_="foreignkey")
    op.drop_column("documents", "lesson_id")
    op.drop_column("documents", "module_id")
    op.drop_constraint("ck_documents_kind_valid", "documents", type_="check")
    op.create_check_constraint("ck_documents_kind_valid", "documents", "kind IN ('course')")


def downgrade() -> None:
    op.drop_constraint("ck_documents_kind_valid", "documents", type_="check")
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
