from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from review_bot.db.session import Base


def _uuid() -> str:
    return str(uuid4())


class ReviewRequest(Base):
    __tablename__ = "review_requests"
    __table_args__ = (
        UniqueConstraint(
            "review_system",
            "project_ref",
            "review_request_id",
            name="uq_review_request_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    draft: Mapped[bool] = mapped_column(default=False)
    source_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latest_head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_base_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_start_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    runs: Mapped[list[ReviewRun]] = relationship(back_populates="review_request")


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_request_pk: Mapped[str] = mapped_column(
        ForeignKey("review_requests.id"), index=True
    )
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    trigger: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(32), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_runtime: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    review_request: Mapped[ReviewRequest] = relationship(back_populates="runs")
    evidences: Mapped[list[FindingEvidence]] = relationship(back_populates="review_run")
    decisions: Mapped[list[FindingDecision]] = relationship(back_populates="review_run")


class FindingEvidence(Base):
    __tablename__ = "finding_evidences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_run_id: Mapped[str] = mapped_column(ForeignKey("review_runs.id"), index=True)
    review_request_pk: Mapped[str] = mapped_column(ForeignKey("review_requests.id"), index=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    patch_digest: Mapped[str] = mapped_column(String(128))
    hunk_header: Mapped[str | None] = mapped_column(String(255), nullable=True)
    candidate_line_nos: Mapped[list[int]] = mapped_column(JSON, default=list)
    matched_patterns: Mapped[list[str]] = mapped_column(JSON, default=list)
    change_snippet: Mapped[str] = mapped_column(Text)
    raw_engine_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    review_run: Mapped[ReviewRun] = relationship(back_populates="evidences")
    decisions: Mapped[list[FindingDecision]] = relationship(back_populates="evidence")


class FindingDecision(Base):
    __tablename__ = "finding_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_run_id: Mapped[str] = mapped_column(ForeignKey("review_runs.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("finding_evidences.id"), index=True)
    review_request_pk: Mapped[str] = mapped_column(ForeignKey("review_requests.id"), index=True)
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), index=True)
    file_path: Mapped[str] = mapped_column(String(1000))
    line_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_no: Mapped[str] = mapped_column(String(128))
    source_family: Mapped[str] = mapped_column(String(64))
    reviewability: Mapped[str] = mapped_column(String(32), default="auto_review")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    score_raw: Mapped[float] = mapped_column(Float)
    score_final: Mapped[float] = mapped_column(Float)
    anchor_signature: Mapped[str] = mapped_column(String(255))
    anchor_payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    suppression_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="candidate")
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_fix_lines: Mapped[list[str]] = mapped_column(JSON, default=list)
    publication_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    review_run: Mapped[ReviewRun] = relationship(back_populates="decisions")
    evidence: Mapped[FindingEvidence] = relationship(back_populates="decisions")
    publications: Mapped[list[PublicationState]] = relationship(back_populates="finding")


class PublicationState(Base):
    __tablename__ = "publication_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    finding_decision_id: Mapped[str] = mapped_column(
        ForeignKey("finding_decisions.id"), index=True
    )
    review_request_pk: Mapped[str] = mapped_column(ForeignKey("review_requests.id"), index=True)
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    adapter_comment_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adapter_thread_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    batch_no: Mapped[int] = mapped_column(Integer, default=1)
    publish_state: Mapped[str] = mapped_column(String(32), default="pending")
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    finding: Mapped[FindingDecision] = relationship(back_populates="publications")


class ThreadSyncState(Base):
    __tablename__ = "thread_sync_states"
    __table_args__ = (
        UniqueConstraint(
            "review_request_pk",
            "adapter_thread_ref",
            name="uq_thread_sync_states_request_thread_ref",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_request_pk: Mapped[str] = mapped_column(ForeignKey("review_requests.id"), index=True)
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    finding_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("finding_decisions.id"), nullable=True, index=True
    )
    finding_fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    anchor_signature: Mapped[str] = mapped_column(String(255))
    body_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    adapter_thread_ref: Mapped[str] = mapped_column(String(255))
    adapter_comment_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(32), default="open")
    last_seen_head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (
        UniqueConstraint(
            "review_request_pk",
            "event_key",
            name="uq_feedback_events_request_event_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_request_pk: Mapped[str] = mapped_column(ForeignKey("review_requests.id"), index=True)
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    event_key: Mapped[str] = mapped_column(String(255))
    adapter_thread_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    adapter_comment_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FindingLifecycleEvent(Base):
    __tablename__ = "finding_lifecycle_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_request_pk: Mapped[str] = mapped_column(ForeignKey("review_requests.id"), index=True)
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    finding_fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    finding_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("finding_decisions.id"), nullable=True, index=True
    )
    adapter_thread_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    rule_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rule_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    event_reason: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    observed_head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compared_from_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class DeadLetterRecord(Base):
    __tablename__ = "dead_letter_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_run_id: Mapped[str] = mapped_column(ForeignKey("review_runs.id"), index=True)
    review_request_pk: Mapped[str] = mapped_column(ForeignKey("review_requests.id"), index=True)
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    error_category: Mapped[str] = mapped_column(String(64))
    error_message: Mapped[str] = mapped_column(Text)
    replayable: Mapped[bool] = mapped_column(default=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
