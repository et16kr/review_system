from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260420_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_system", sa.String(length=32), nullable=False),
        sa.Column("project_ref", sa.String(length=255), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("draft", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_branch", sa.String(length=255), nullable=True),
        sa.Column("target_branch", sa.String(length=255), nullable=True),
        sa.Column("latest_head_sha", sa.String(length=64), nullable=True),
        sa.Column("latest_base_sha", sa.String(length=64), nullable=True),
        sa.Column("latest_start_sha", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("review_system", "project_ref", "review_request_id", name="uq_review_request_key"),
    )
    for column in ["review_system", "project_ref", "review_request_id"]:
        op.create_index(f"ix_review_requests_{column}", "review_requests", [column])

    op.create_table(
        "review_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_request_pk", sa.String(length=36), sa.ForeignKey("review_requests.id"), nullable=False),
        sa.Column("review_system", sa.String(length=32), nullable=False),
        sa.Column("project_ref", sa.String(length=255), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("trigger", sa.String(length=64), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=True),
        sa.Column("base_sha", sa.String(length=64), nullable=True),
        sa.Column("start_sha", sa.String(length=64), nullable=True),
        sa.Column("head_sha", sa.String(length=64), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["review_request_pk", "review_system", "project_ref", "review_request_id"]:
        op.create_index(f"ix_review_runs_{column}", "review_runs", [column])

    op.create_table(
        "finding_evidences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_run_id", sa.String(length=36), sa.ForeignKey("review_runs.id"), nullable=False),
        sa.Column("review_request_pk", sa.String(length=36), sa.ForeignKey("review_requests.id"), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("patch_digest", sa.String(length=128), nullable=False),
        sa.Column("hunk_header", sa.String(length=255), nullable=True),
        sa.Column("candidate_line_nos", sa.JSON(), nullable=False),
        sa.Column("matched_patterns", sa.JSON(), nullable=False),
        sa.Column("change_snippet", sa.Text(), nullable=False),
        sa.Column("raw_engine_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["review_run_id", "review_request_pk"]:
        op.create_index(f"ix_finding_evidences_{column}", "finding_evidences", [column])

    op.create_table(
        "finding_decisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_run_id", sa.String(length=36), sa.ForeignKey("review_runs.id"), nullable=False),
        sa.Column("evidence_id", sa.String(length=36), sa.ForeignKey("finding_evidences.id"), nullable=False),
        sa.Column("review_request_pk", sa.String(length=36), sa.ForeignKey("review_requests.id"), nullable=False),
        sa.Column("review_system", sa.String(length=32), nullable=False),
        sa.Column("project_ref", sa.String(length=255), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=True),
        sa.Column("rule_no", sa.String(length=128), nullable=False),
        sa.Column("source_family", sa.String(length=64), nullable=False),
        sa.Column("reviewability", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("score_raw", sa.Float(), nullable=False),
        sa.Column("score_final", sa.Float(), nullable=False),
        sa.Column("anchor_signature", sa.String(length=255), nullable=False),
        sa.Column("anchor_payload", sa.JSON(), nullable=False),
        sa.Column("suppression_reason", sa.String(length=128), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("publication_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["review_run_id", "evidence_id", "review_request_pk", "review_system", "project_ref", "review_request_id", "fingerprint", "dedupe_key"]:
        op.create_index(f"ix_finding_decisions_{column}", "finding_decisions", [column])

    op.create_table(
        "publication_states",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("finding_decision_id", sa.String(length=36), sa.ForeignKey("finding_decisions.id"), nullable=False),
        sa.Column("review_request_pk", sa.String(length=36), sa.ForeignKey("review_requests.id"), nullable=False),
        sa.Column("review_system", sa.String(length=32), nullable=False),
        sa.Column("project_ref", sa.String(length=255), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("adapter_comment_ref", sa.String(length=255), nullable=True),
        sa.Column("adapter_thread_ref", sa.String(length=255), nullable=True),
        sa.Column("body_hash", sa.String(length=128), nullable=True),
        sa.Column("batch_no", sa.Integer(), nullable=False),
        sa.Column("publish_state", sa.String(length=32), nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for column in ["finding_decision_id", "review_request_pk", "review_system", "project_ref", "review_request_id"]:
        op.create_index(f"ix_publication_states_{column}", "publication_states", [column])

    op.create_table(
        "thread_sync_states",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_request_pk", sa.String(length=36), sa.ForeignKey("review_requests.id"), nullable=False),
        sa.Column("review_system", sa.String(length=32), nullable=False),
        sa.Column("project_ref", sa.String(length=255), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("finding_decision_id", sa.String(length=36), sa.ForeignKey("finding_decisions.id"), nullable=True),
        sa.Column("finding_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("anchor_signature", sa.String(length=255), nullable=False),
        sa.Column("body_hash", sa.String(length=128), nullable=True),
        sa.Column("adapter_thread_ref", sa.String(length=255), nullable=False),
        sa.Column("adapter_comment_ref", sa.String(length=255), nullable=True),
        sa.Column("sync_status", sa.String(length=32), nullable=False),
        sa.Column("last_seen_head_sha", sa.String(length=64), nullable=True),
        sa.Column("resolution_reason", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("adapter_thread_ref", name="uq_thread_sync_states_adapter_thread_ref"),
    )
    for column in ["review_request_pk", "review_system", "project_ref", "review_request_id", "finding_decision_id", "finding_fingerprint"]:
        op.create_index(f"ix_thread_sync_states_{column}", "thread_sync_states", [column])

    op.create_table(
        "feedback_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("review_request_pk", sa.String(length=36), sa.ForeignKey("review_requests.id"), nullable=False),
        sa.Column("review_system", sa.String(length=32), nullable=False),
        sa.Column("project_ref", sa.String(length=255), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("adapter_thread_ref", sa.String(length=255), nullable=True),
        sa.Column("adapter_comment_ref", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_ref", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_key", name="uq_feedback_event_key"),
    )
    for column in ["review_request_pk", "review_system", "project_ref", "review_request_id"]:
        op.create_index(f"ix_feedback_events_{column}", "feedback_events", [column])


def downgrade() -> None:
    op.drop_table("feedback_events")
    op.drop_table("thread_sync_states")
    op.drop_table("publication_states")
    op.drop_table("finding_decisions")
    op.drop_table("finding_evidences")
    op.drop_table("review_runs")
    op.drop_table("review_requests")
