from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.review_systems.base import ReviewSystemAdapter


class GitLabReviewSystemAdapter(ReviewSystemAdapter):
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        project_id: str | None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project_id = project_id

    def get_pull_request_diff(self, review_request_id: int) -> dict[str, Any]:
        project = self._project_ref()
        response = httpx.get(
            (
                f"{self.base_url}/api/v4/projects/{quote(project, safe='')}"
                f"/merge_requests/{review_request_id}/changes"
            ),
            headers=self._headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        diff_refs = payload.get("diff_refs") or {}
        files: list[dict[str, Any]] = []
        for change in payload.get("changes", []):
            files.append(
                {
                    "path": change.get("new_path") or change.get("old_path") or "",
                    "status": self._change_status(change),
                    "additions": 0,
                    "deletions": 0,
                    "patch": change.get("diff") or "",
                }
            )
        return {
            "pull_request": {
                "id": review_request_id,
                "base_sha": diff_refs.get("base_sha"),
                "head_sha": diff_refs.get("head_sha"),
            },
            "files": files,
        }

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
        del comment_type, author_type
        project = self._project_ref()
        rendered = body
        if file_path:
            rendered = f"{body}\n\n_Path_: `{file_path}`"
        if line_no is not None:
            rendered = f"{rendered}\n_Line_: `{line_no}`"
        response = httpx.post(
            (
                f"{self.base_url}/api/v4/projects/{quote(project, safe='')}"
                f"/merge_requests/{review_request_id}/notes"
            ),
            headers=self._headers(),
            data={"body": rendered},
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
        del review_request_id
        return {
            "ok": True,
            "state": state,
            "description": description,
            "note": "GitLab adapter does not publish commit status in the MVP path.",
        }

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self.token}

    def _project_ref(self) -> str:
        if self.project_id:
            return self.project_id
        raise ValueError(
            "GITLAB_PROJECT_ID is required for the GitLab adapter in the current MVP."
        )

    def _change_status(self, change: dict[str, Any]) -> str:
        if change.get("new_file"):
            return "added"
        if change.get("deleted_file"):
            return "deleted"
        if change.get("renamed_file"):
            return "renamed"
        return "modified"
