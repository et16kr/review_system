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


class FindingOutcomesResponse(BaseModel):
    window: Literal["14d", "28d"] = "28d"
    project_ref: str | None = None
    source_family: str | None = None
    surfaced_distinct: int = 0
    resolved_distinct: int = 0
    fixed_distinct: int = 0
    manual_resolved_distinct: int = 0
    ignored_distinct: int = 0
    false_positive_distinct: int = 0
    reopened_distinct: int = 0
    surfaced_cohort_distinct: int = 0
    converted_cohort_distinct: int = 0
    fix_confirmation_rate: float = 0.0
    human_resolve_rate: float = 0.0
    false_positive_feedback_rate: float = 0.0
    fix_conversion_rate: float = 0.0


class WrongLanguagePairResponse(BaseModel):
    detected_language_id: str
    expected_language_id: str
    count: int


class WrongLanguageProfileResponse(BaseModel):
    detected_language_id: str
    expected_language_id: str
    profile_id: str | None = None
    context_id: str | None = None
    count: int


class WrongLanguagePathResponse(BaseModel):
    detected_language_id: str
    expected_language_id: str
    path_pattern: str
    count: int


class WrongLanguageTriageCandidateResponse(BaseModel):
    detected_language_id: str
    expected_language_id: str
    profile_id: str | None = None
    context_id: str | None = None
    path_pattern: str
    count: int
    priority: Literal["high", "medium", "low"] = "low"
    provenance: Literal["smoke", "production", "unknown"] = "unknown"
    triage_cause: Literal[
        "synthetic_smoke",
        "detector_miss",
        "wrong_thread_target",
        "policy_mismatch",
        "needs_inspection",
    ] = "needs_inspection"
    actionability: Literal[
        "ignore_for_detector_backlog",
        "inspect_thread",
        "update_policy_or_fixture",
        "fix_detector",
    ] = "inspect_thread"
    suggested_action: str


class WrongLanguageFeedbackResponse(BaseModel):
    window: Literal["14d", "28d"] = "28d"
    project_ref: str | None = None
    total_events: int = 0
    distinct_threads: int = 0
    distinct_findings: int = 0
    smoke_events: int = 0
    production_events: int = 0
    unknown_provenance_events: int = 0
    top_language_pairs: list[WrongLanguagePairResponse] = Field(default_factory=list)
    top_profiles: list[WrongLanguageProfileResponse] = Field(default_factory=list)
    top_paths: list[WrongLanguagePathResponse] = Field(default_factory=list)
    triage_candidates: list[WrongLanguageTriageCandidateResponse] = Field(default_factory=list)
