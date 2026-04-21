from __future__ import annotations

from datetime import datetime

import httpx

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
from review_bot.review_systems.base import ReviewSystemAdapterV2


class LocalPlatformReviewSystemAdapter(ReviewSystemAdapterV2):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def fetch_review_request_meta(self, key: ReviewRequestKey) -> ReviewRequestMeta:
        pr_id = int(key.review_request_id)
        response = httpx.get(
            f"{self.base_url}/api/pull-requests/{pr_id}",
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return ReviewRequestMeta(
            key=key,
            title=payload.get("title"),
            state="opened",
            draft=False,
            source_branch=payload.get("source_branch"),
            target_branch=payload.get("target_branch"),
        )

    def fetch_diff(
        self,
        key: ReviewRequestKey,
        *,
        mode: str,
        base_sha: str | None = None,
    ) -> DiffPayload:
        params: dict[str, str] | None = None
        if mode == "incremental" and base_sha:
            params = {"base_sha": base_sha}
        response = httpx.get(
            f"{self.base_url}/api/pull-requests/{int(key.review_request_id)}/diff",
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        return DiffPayload.model_validate(response.json())

    def list_threads(self, key: ReviewRequestKey) -> list[ThreadSnapshot]:
        del key
        return []

    def upsert_comment(
        self,
        key: ReviewRequestKey,
        request: CommentUpsertRequest,
    ) -> CommentUpsertResult:
        response = httpx.post(
            f"{self.base_url}/api/pull-requests/{int(key.review_request_id)}/comments",
            json={
                "file_path": request.anchor.file_path,
                "line_no": request.anchor.start_line,
                "comment_type": "inline",
                "author_type": "bot",
                "created_by": "review-bot",
                "body": request.body,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return CommentUpsertResult(
            ok=True,
            action="created",
            comment_ref=str(payload.get("id")),
            thread_ref=str(payload.get("id")),
            raw=payload,
        )

    def resolve_thread(
        self,
        key: ReviewRequestKey,
        thread_ref: str,
        *,
        reason: str,
    ) -> dict[str, str | bool]:
        del key, thread_ref, reason
        return {"ok": True, "resolved": True}

    def publish_check(
        self,
        key: ReviewRequestKey,
        request: CheckPublishRequest,
    ) -> CheckPublishResult:
        response = httpx.post(
            f"{self.base_url}/api/pull-requests/{int(key.review_request_id)}/statuses",
            json={
                "context": "review-bot",
                "state": request.state,
                "description": request.description,
                "created_by": "review-bot",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return CheckPublishResult(
            ok=True,
            state=request.state,
            description=request.description,
            raw=response.json(),
        )

    def collect_feedback(
        self,
        key: ReviewRequestKey,
        *,
        since: str | None = None,
    ) -> FeedbackPage:
        del key, since
        return FeedbackPage(events=[])

    # Compatibility helpers for existing tests and local harness
    def get_pull_request_diff(self, review_request_id: int) -> dict[str, object]:
        key = ReviewRequestKey(
            review_system="local_platform",
            project_ref="local/default",
            review_request_id=str(review_request_id),
        )
        return self.fetch_diff(key, mode="full").model_dump()

    def post_comment(
        self,
        review_request_id: int,
        *,
        body: str,
        file_path: str | None,
        line_no: int | None,
        comment_type: str = "inline",
        author_type: str = "bot",
    ) -> dict[str, object]:
        del comment_type, author_type
        anchor_line = line_no or 1
        key = ReviewRequestKey(
            review_system="local_platform",
            project_ref="local/default",
            review_request_id=str(review_request_id),
        )
        return self.upsert_comment(
            key,
            CommentUpsertRequest(
                fingerprint=f"legacy:{review_request_id}:{file_path}:{anchor_line}",
                body=body,
                anchor={
                    "file_path": file_path or "",
                    "start_line": anchor_line,
                    "end_line": anchor_line,
                },
            ),
        ).model_dump()

    def post_status(
        self,
        review_request_id: int,
        *,
        state: str,
        description: str,
    ) -> dict[str, object]:
        key = ReviewRequestKey(
            review_system="local_platform",
            project_ref="local/default",
            review_request_id=str(review_request_id),
        )
        return self.publish_check(
            key,
            CheckPublishRequest(state=state, description=description),
        ).model_dump()
