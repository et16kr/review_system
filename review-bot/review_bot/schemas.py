from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from review_bot.contracts import ReviewRequestKey


class ReviewRunCreateRequest(BaseModel):
    key: ReviewRequestKey
    trigger: str = "manual"
    mode: Literal["full", "incremental", "manual", "sync-only"] = "manual"
    title: str | None = None
    draft: bool = False
    source_branch: str | None = None
    target_branch: str | None = None
    base_sha: str | None = None
    start_sha: str | None = None
    head_sha: str | None = None


class LegacyReviewTriggerRequest(BaseModel):
    pr_id: int
    trigger: str = "manual"


class ReviewAcceptedResponse(BaseModel):
    accepted: bool
    review_run_id: str
    status: str
    queue_name: str | None = None


class WebhookAcceptedResponse(BaseModel):
    accepted: bool
    event: str
    action: str | None = None
    review_run_id: str | None = None
    status: str
    queue_name: str | None = None
    ignored_reason: str | None = None


class ReviewRequestStateResponse(BaseModel):
    key: ReviewRequestKey
    last_review_run_id: str | None
    last_head_sha: str | None
    last_status: str | None = None
    published_batch_count: int
    open_finding_count: int
    resolved_finding_count: int
    failed_publication_count: int = 0
    next_batch_size: int
    open_thread_count: int = 0
    feedback_event_count: int = 0
    dead_letter_count: int = 0


class ReviewFullReportCountsResponse(BaseModel):
    published_inline: int = 0
    already_open: int = 0
    pending_batch: int = 0
    backlog_existing_open: int = 0
    backlog_resolved_unchanged: int = 0
    backlog_feedback_later: int = 0
    suppressed_feedback_ignore: int = 0
    suppressed_feedback_false_positive: int = 0
    suppressed_other: int = 0
    failed_publication: int = 0


class ReviewFullReportItemResponse(BaseModel):
    fingerprint: str
    file_path: str
    line_no: int | None = None
    rule_no: str
    severity: str
    title: str | None = None
    summary: str | None = None
    state: str
    disposition: str
    reason: str | None = None
    score_final: float | None = None
    thread_ref: str | None = None


class ReviewFullReportResponse(BaseModel):
    key: ReviewRequestKey
    review_request_title: str | None = None
    last_review_run_id: str | None = None
    last_status: str | None = None
    last_head_sha: str | None = None
    report_review_run_id: str | None = None
    report_status: str | None = None
    report_head_sha: str | None = None
    in_flight_review_run_id: str | None = None
    in_flight_status: str | None = None
    in_flight_head_sha: str | None = None
    generated_at: datetime
    counts: ReviewFullReportCountsResponse = Field(
        default_factory=ReviewFullReportCountsResponse
    )
    published_inline: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    already_open: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    pending_batch: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    backlog_existing_open: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    backlog_resolved_unchanged: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    backlog_feedback_later: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    suppressed_feedback_ignore: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    suppressed_feedback_false_positive: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    suppressed_other: list[ReviewFullReportItemResponse] = Field(default_factory=list)
    failed_publication: list[ReviewFullReportItemResponse] = Field(default_factory=list)


class PublishRunResponse(BaseModel):
    accepted: bool
    review_run_id: str
    queue_name: str | None = None
    status: str = "queued"


class SyncRunResponse(BaseModel):
    accepted: bool
    review_run_id: str
    queue_name: str | None = None
    status: str = "queued"
