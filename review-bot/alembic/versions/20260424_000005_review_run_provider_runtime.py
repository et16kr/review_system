"""add provider runtime metadata to review_runs

Revision ID: 20260424_000005
Revises: 20260421_000004
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260424_000005"
down_revision = "20260421_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_runs",
        sa.Column(
            "provider_runtime",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("review_runs", "provider_runtime")
