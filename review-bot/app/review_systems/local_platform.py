from __future__ import annotations

from typing import Any

import httpx

from app.review_systems.base import ReviewSystemAdapter


class LocalPlatformReviewSystemAdapter(ReviewSystemAdapter):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def get_pull_request_diff(self, review_request_id: int) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/api/pull-requests/{review_request_id}/diff",
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    def post_comment(
        self,
        review_request_id: int,
        *,
        body: str,
        file_path: str | None,
        line_no: int | None,
        comment_type: str = "inline",
        author_type: str = "bot",
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/pull-requests/{review_request_id}/comments",
            json={
                "file_path": file_path,
                "line_no": line_no,
                "comment_type": comment_type,
                "author_type": author_type,
                "created_by": "review-bot",
                "body": body,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()

    def post_status(
        self,
        review_request_id: int,
        *,
        state: str,
        description: str,
    ) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/pull-requests/{review_request_id}/statuses",
            json={
                "context": "review-bot",
                "state": state,
                "description": description,
                "created_by": "review-bot",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
