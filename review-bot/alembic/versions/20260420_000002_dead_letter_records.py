from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_000002"
down_revision = "20260420_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dead_letter_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_run_id", sa.String(length=36), sa.ForeignKey("review_runs.id"), nullable=False),
        sa.Column("review_request_pk", sa.String(length=36), sa.ForeignKey("review_requests.id"), nullable=False),
        sa.Column("review_system", sa.String(length=32), nullable=False),
        sa.Column("project_ref", sa.String(length=255), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("replayable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in [
        "review_run_id",
        "review_request_pk",
        "review_system",
        "project_ref",
        "review_request_id",
        "stage",
    ]:
        op.create_index(f"ix_dead_letter_records_{column}", "dead_letter_records", [column])


def downgrade() -> None:
    op.drop_table("dead_letter_records")
