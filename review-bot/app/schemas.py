from __future__ import annotations

from pydantic import BaseModel


class ReviewTriggerRequest(BaseModel):
    pr_id: int
    trigger: str = "manual"


class NextBatchRequest(BaseModel):
    pr_id: int
    reason: str = "manual_next_batch"


class ReviewAcceptedResponse(BaseModel):
    accepted: bool
    review_run_id: int
    status: str
    queue_name: str | None = None


class BotStateResponse(BaseModel):
    pr_id: int
    last_review_run_id: int | None
    last_head_sha: str | None
    last_status: str | None = None
    published_batch_count: int
    open_finding_count: int
    resolved_finding_count: int
    failed_publication_count: int = 0
    next_batch_size: int
