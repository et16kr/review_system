"""add evidence_snippet and auto_fix_lines to finding_decisions

Revision ID: 20260420_000003
Revises: 20260420_000002
Create Date: 2026-04-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260420_000003"
down_revision = "20260420_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("finding_decisions") as batch_op:
        batch_op.add_column(sa.Column("evidence_snippet", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("auto_fix_lines", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("finding_decisions") as batch_op:
        batch_op.drop_column("auto_fix_lines")
        batch_op.drop_column("evidence_snippet")
