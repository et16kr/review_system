"""add finding_lifecycle_events table

Revision ID: 20260421_000004
Revises: 20260420_000003
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260421_000004"
down_revision = "20260420_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finding_lifecycle_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_request_pk", sa.String(length=36), sa.ForeignKey("review_requests.id"), nullable=False),
        sa.Column("review_system", sa.String(length=32), nullable=False),
        sa.Column("project_ref", sa.String(length=255), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("finding_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("finding_decision_id", sa.String(length=36), sa.ForeignKey("finding_decisions.id"), nullable=True),
        sa.Column("adapter_thread_ref", sa.String(length=255), nullable=True),
        sa.Column("rule_no", sa.String(length=128), nullable=True),
        sa.Column("rule_family", sa.String(length=64), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_reason", sa.String(length=128), nullable=True),
        sa.Column("observed_head_sha", sa.String(length=64), nullable=True),
        sa.Column("compared_from_sha", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in [
        "review_request_pk",
        "review_system",
        "project_ref",
        "review_request_id",
        "finding_fingerprint",
        "finding_decision_id",
        "adapter_thread_ref",
        "event_type",
        "event_reason",
        "event_at",
    ]:
        op.create_index(f"ix_finding_lifecycle_events_{column}", "finding_lifecycle_events", [column])


def downgrade() -> None:
    op.drop_table("finding_lifecycle_events")
