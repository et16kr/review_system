from __future__ import annotations

import difflib
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
        self._mr_cache: dict[int, dict[str, Any]] = {}
        self._file_cache: dict[tuple[str, str], str] = {}

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
        file_map: dict[str, dict[str, Any]] = {}
        for change in payload.get("changes", []):
            path = change.get("new_path") or change.get("old_path") or ""
            file_meta = {
                "new_path": change.get("new_path"),
                "old_path": change.get("old_path"),
                "renamed_file": bool(change.get("renamed_file")),
                "new_file": bool(change.get("new_file")),
                "deleted_file": bool(change.get("deleted_file")),
            }
            file_map[path] = file_meta
            files.append(
                {
                    "path": path,
                    "status": self._change_status(change),
                    "additions": 0,
                    "deletions": 0,
                    "patch": self._resolve_patch(project, change, diff_refs),
                }
            )
        self._mr_cache[review_request_id] = {
            "diff_refs": diff_refs,
            "file_map": file_map,
        }
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
        if file_path and line_no is not None:
            inline = self._post_inline_discussion(
                project,
                review_request_id,
                body=body,
                file_path=file_path,
                line_no=line_no,
            )
            if inline is not None:
                return inline
            raise RuntimeError(
                f"Unable to create inline discussion for {file_path}:{line_no}"
            )
        return self._post_note(
            project,
            review_request_id,
            body=body,
            file_path=file_path,
            line_no=line_no,
        )

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

    def _post_inline_discussion(
        self,
        project: str,
        review_request_id: int,
        *,
        body: str,
        file_path: str,
        line_no: int,
    ) -> dict[str, Any] | None:
        cache = self._mr_cache.get(review_request_id) or {}
        diff_refs = cache.get("diff_refs") or {}
        file_map = cache.get("file_map") or {}
        file_meta = file_map.get(file_path)
        if not file_meta:
            return None

        new_path = file_meta.get("new_path") or file_path
        old_path = file_meta.get("old_path") or new_path
        has_required_refs = (
            diff_refs.get("base_sha")
            and diff_refs.get("head_sha")
            and diff_refs.get("start_sha")
        )
        if not has_required_refs:
            return None

        data = {
            "body": body,
            "position[position_type]": "text",
            "position[base_sha]": diff_refs["base_sha"],
            "position[start_sha]": diff_refs["start_sha"],
            "position[head_sha]": diff_refs["head_sha"],
            "position[new_path]": new_path,
            "position[old_path]": old_path,
            "position[new_line]": str(line_no),
        }
        try:
            response = httpx.post(
                (
                    f"{self.base_url}/api/v4/projects/{quote(project, safe='')}"
                    f"/merge_requests/{review_request_id}/discussions"
                ),
                headers=self._headers(),
                data=data,
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
            notes = payload.get("notes") or []
            if notes:
                first = notes[0]
                return {
                    "id": first.get("id"),
                    "discussion_id": payload.get("id"),
                    "kind": "discussion",
                }
            return {"id": payload.get("id"), "kind": "discussion"}
        except httpx.HTTPStatusError:
            return None

    def _post_note(
        self,
        project: str,
        review_request_id: int,
        *,
        body: str,
        file_path: str | None,
        line_no: int | None,
    ) -> dict[str, Any]:
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

    def _change_status(self, change: dict[str, Any]) -> str:
        if change.get("new_file"):
            return "added"
        if change.get("deleted_file"):
            return "deleted"
        if change.get("renamed_file"):
            return "renamed"
        return "modified"

    def _resolve_patch(
        self,
        project: str,
        change: dict[str, Any],
        diff_refs: dict[str, str],
    ) -> str:
        patch = change.get("diff") or ""
        if patch.strip():
            return patch
        return self._build_patch_from_repository(project, change, diff_refs)

    def _build_patch_from_repository(
        self,
        project: str,
        change: dict[str, Any],
        diff_refs: dict[str, str],
    ) -> str:
        new_path = change.get("new_path") or change.get("old_path") or ""
        old_path = change.get("old_path") or new_path
        base_ref = diff_refs.get("base_sha") or diff_refs.get("start_sha")
        head_ref = diff_refs.get("head_sha")
        if not new_path or not head_ref:
            return ""

        if change.get("new_file"):
            new_text = self._fetch_file_text(project, new_path, head_ref)
            return self._build_unified_diff("", new_text, "/dev/null", new_path)

        if change.get("deleted_file"):
            if not base_ref:
                return ""
            old_text = self._fetch_file_text(project, old_path, base_ref)
            return self._build_unified_diff(old_text, "", old_path, "/dev/null")

        if not base_ref:
            return ""
        old_text = self._fetch_file_text(project, old_path, base_ref)
        new_text = self._fetch_file_text(project, new_path, head_ref)
        return self._build_unified_diff(old_text, new_text, old_path, new_path)

    def _fetch_file_text(self, project: str, path: str, ref: str) -> str:
        cache_key = (path, ref)
        if cache_key in self._file_cache:
            return self._file_cache[cache_key]

        response = httpx.get(
            (
                f"{self.base_url}/api/v4/projects/{quote(project, safe='')}"
                f"/repository/files/{quote(path, safe='')}/raw"
            ),
            headers=self._headers(),
            params={"ref": ref},
            timeout=30.0,
        )
        response.raise_for_status()
        text = response.text
        self._file_cache[cache_key] = text
        return text

    def _build_unified_diff(
        self,
        old_text: str,
        new_text: str,
        old_path: str,
        new_path: str,
    ) -> str:
        diff_lines = list(
            difflib.unified_diff(
                old_text.splitlines(),
                new_text.splitlines(),
                fromfile=old_path,
                tofile=new_path,
                lineterm="",
            )
        )
        return "\n".join(diff_lines)
