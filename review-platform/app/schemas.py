from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    name: str
    description: str = ""
    default_branch: str = "main"


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    storage_path: str
    default_branch: str
    clone_url: str
    created_at: datetime


class PullRequestCreate(BaseModel):
    repository_id: int
    title: str
    description: str = ""
    base_branch: str
    head_branch: str
    created_by: str | None = None


class PullRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    title: str
    description: str
    base_branch: str
    head_branch: str
    base_sha: str
    head_sha: str
    status: str
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class ChangedFileResponse(BaseModel):
    path: str
    status: str
    additions: int
    deletions: int
    patch: str


class PullRequestDiffResponse(BaseModel):
    pull_request: PullRequestResponse
    files: list[ChangedFileResponse] = Field(default_factory=list)


class CommentCreate(BaseModel):
    file_path: str | None = None
    line_no: int | None = None
    comment_type: str = "summary"
    author_type: str = "anonymous"
    created_by: str | None = None
    body: str


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pull_request_id: int
    file_path: str | None
    line_no: int | None
    comment_type: str
    author_type: str
    created_by: str | None
    body: str
    created_at: datetime


class StatusCreate(BaseModel):
    context: str
    state: str
    description: str
    created_by: str | None = None


class StatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pull_request_id: int
    context: str
    state: str
    description: str
    created_by: str | None
    created_at: datetime


class PullRequestListResponse(BaseModel):
    items: list[PullRequestResponse]


class BotReviewTrigger(BaseModel):
    trigger: str = "manual"


class BotNextBatchTrigger(BaseModel):
    reason: str = "manual_next_batch"


class BotReviewResponse(BaseModel):
    accepted: bool
    review_run_id: int
    status: str


class BotStateResponse(BaseModel):
    pr_id: int
    last_review_run_id: int | None
    last_head_sha: str | None
    published_batch_count: int
    open_finding_count: int
    resolved_finding_count: int
    next_batch_size: int
