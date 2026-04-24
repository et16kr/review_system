"""scope adapter remote refs to review request

Revision ID: 20260424_000006
Revises: 20260424_000005
Create Date: 2026-04-24
"""

from __future__ import annotations

from alembic import op

revision = "20260424_000006"
down_revision = "20260424_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("thread_sync_states") as batch_op:
        batch_op.drop_constraint("uq_thread_sync_states_adapter_thread_ref", type_="unique")
        batch_op.create_unique_constraint(
            "uq_thread_sync_states_request_thread_ref",
            ["review_request_pk", "adapter_thread_ref"],
        )

    with op.batch_alter_table("feedback_events") as batch_op:
        batch_op.drop_constraint("uq_feedback_event_key", type_="unique")
        batch_op.create_unique_constraint(
            "uq_feedback_events_request_event_key",
            ["review_request_pk", "event_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("feedback_events") as batch_op:
        batch_op.drop_constraint("uq_feedback_events_request_event_key", type_="unique")
        batch_op.create_unique_constraint("uq_feedback_event_key", ["event_key"])

    with op.batch_alter_table("thread_sync_states") as batch_op:
        batch_op.drop_constraint("uq_thread_sync_states_request_thread_ref", type_="unique")
        batch_op.create_unique_constraint(
            "uq_thread_sync_states_adapter_thread_ref",
            ["adapter_thread_ref"],
        )
