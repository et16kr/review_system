from __future__ import annotations

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
