from __future__ import annotations

from typing import Any, Protocol

from review_bot.contracts import (
    CheckPublishRequest,
    CheckPublishResult,
    CommentUpsertRequest,
    CommentUpsertResult,
    DiffPayload,
    FeedbackPage,
    ReviewRequestKey,
    ReviewRequestMeta,
    ThreadSnapshot,
)


class ReviewSystemAdapterV2(Protocol):
    def fetch_review_request_meta(self, key: ReviewRequestKey) -> ReviewRequestMeta:
        raise NotImplementedError

    def fetch_diff(
        self,
        key: ReviewRequestKey,
        *,
        mode: str,
        base_sha: str | None = None,
    ) -> DiffPayload:
        raise NotImplementedError

    def list_threads(self, key: ReviewRequestKey) -> list[ThreadSnapshot]:
        raise NotImplementedError

    def upsert_comment(
        self,
        key: ReviewRequestKey,
        request: CommentUpsertRequest,
    ) -> CommentUpsertResult:
        raise NotImplementedError

    def resolve_thread(
        self,
        key: ReviewRequestKey,
        thread_ref: str,
        *,
        reason: str,
    ) -> dict[str, str | bool]:
        raise NotImplementedError

    def publish_check(
        self,
        key: ReviewRequestKey,
        request: CheckPublishRequest,
    ) -> CheckPublishResult:
        raise NotImplementedError

    def collect_feedback(
        self,
        key: ReviewRequestKey,
        *,
        since: str | None = None,
    ) -> FeedbackPage:
        raise NotImplementedError

    def fetch_file_content(
        self,
        key: ReviewRequestKey,
        path: str,
        ref: str,
    ) -> str | None:
        return None

    def post_general_note(
        self,
        key: ReviewRequestKey,
        body: str,
    ) -> dict[str, Any]:
        return {"ok": False, "reason": "not_supported"}


ReviewSystemAdapter = ReviewSystemAdapterV2
