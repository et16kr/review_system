from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewRequestKey(BaseModel):
    model_config = ConfigDict(frozen=True)

    review_system: str
    project_ref: str
    review_request_id: str


class ReviewRequestMeta(BaseModel):
    key: ReviewRequestKey
    title: str | None = None
    state: str = "opened"
    draft: bool = False
    source_branch: str | None = None
    target_branch: str | None = None
    base_sha: str | None = None
    start_sha: str | None = None
    head_sha: str | None = None


class DiffFile(BaseModel):
    path: str
    status: str = "modified"
    patch: str
    additions: int = 0
    deletions: int = 0
    old_path: str | None = None
    new_path: str | None = None


class DiffPayload(BaseModel):
    pull_request: dict[str, Any]
    files: list[DiffFile]


class AnchorPayload(BaseModel):
    file_path: str
    line_type: Literal["new"] = "new"
    start_line: int
    end_line: int
    candidate_line_nos: tuple[int, ...] = ()
    hunk_header: str | None = None
    changed_line_digest: str | None = None


class ThreadNoteSnapshot(BaseModel):
    note_ref: str
    body: str
    author_type: Literal["bot", "human", "system"]
    author_ref: str | None = None
    created_at: datetime | None = None
    resolved: bool | None = None


class ThreadSnapshot(BaseModel):
    thread_ref: str
    comment_ref: str | None = None
    resolved: bool = False
    resolvable: bool = False
    body: str = ""
    updated_at: datetime | None = None
    notes: list[ThreadNoteSnapshot] = Field(default_factory=list)


class CommentUpsertRequest(BaseModel):
    fingerprint: str
    body: str
    anchor: AnchorPayload
    existing_thread_ref: str | None = None
    existing_comment_ref: str | None = None
    reopen_if_resolved: bool = False
    mode: Literal["create_or_update"] = "create_or_update"


class CommentUpsertResult(BaseModel):
    ok: bool = True
    action: Literal["created", "updated", "skipped"] = "created"
    comment_ref: str | None = None
    thread_ref: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class CheckPublishRequest(BaseModel):
    head_sha: str | None = None
    state: str
    description: str


class CheckPublishResult(BaseModel):
    ok: bool = True
    state: str
    description: str
    raw: dict[str, Any] = Field(default_factory=dict)


class FeedbackRecord(BaseModel):
    event_key: str
    event_type: Literal["resolved", "unresolved", "reply"]
    adapter_thread_ref: str | None = None
    adapter_comment_ref: str | None = None
    actor_type: Literal["bot", "human", "system"]
    actor_ref: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class FeedbackPage(BaseModel):
    events: list[FeedbackRecord] = Field(default_factory=list)
