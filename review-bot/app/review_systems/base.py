from __future__ import annotations

from typing import Any


class ReviewSystemAdapter:
    def get_pull_request_diff(self, review_request_id: int) -> dict[str, Any]:
        raise NotImplementedError

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
        raise NotImplementedError

    def post_status(
        self,
        review_request_id: int,
        *,
        state: str,
        description: str,
    ) -> dict[str, Any]:
        raise NotImplementedError
