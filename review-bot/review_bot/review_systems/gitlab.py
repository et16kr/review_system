from __future__ import annotations

import difflib
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from review_bot.config import get_settings
from review_bot.contracts import (
    CheckPublishRequest,
    CheckPublishResult,
    CommentUpsertRequest,
    CommentUpsertResult,
    DiffPayload,
    FeedbackPage,
    FeedbackRecord,
    ReviewRequestKey,
    ReviewRequestMeta,
    ThreadNoteSnapshot,
    ThreadSnapshot,
)
from review_bot.errors import ReviewBotError
from review_bot.review_systems.base import ReviewSystemAdapterV2


class GitLabReviewSystemAdapter(ReviewSystemAdapterV2):
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 0,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._mr_cache: dict[tuple[str, str], dict[str, Any]] = {}
        self._file_cache: dict[tuple[str, str], str] = {}
        self._compare_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    def fetch_review_request_meta(self, key: ReviewRequestKey) -> ReviewRequestMeta:
        payload = self._get(
            self._api_path(
                key,
                f"/merge_requests/{key.review_request_id}",
            )
        )
        return ReviewRequestMeta(
            key=key,
            title=payload.get("title"),
            state=str(payload.get("state") or "opened"),
            draft=bool(payload.get("draft")),
            source_branch=payload.get("source_branch"),
            target_branch=payload.get("target_branch"),
            base_sha=(payload.get("diff_refs") or {}).get("base_sha"),
            start_sha=(payload.get("diff_refs") or {}).get("start_sha"),
            head_sha=(payload.get("diff_refs") or {}).get("head_sha"),
        )

    def fetch_diff(
        self,
        key: ReviewRequestKey,
        *,
        mode: str,
        base_sha: str | None = None,
    ) -> DiffPayload:
        payload = self._get(
            self._api_path(
                key,
                f"/merge_requests/{key.review_request_id}/changes",
            )
        )
        diff_refs = payload.get("diff_refs") or {}
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
        self._mr_cache[(key.project_ref, key.review_request_id)] = {
            "diff_refs": diff_refs,
            "file_map": file_map,
        }
        changes = payload.get("changes", [])
        if mode == "incremental" and base_sha and base_sha != diff_refs.get("head_sha"):
            changes = self._fetch_incremental_changes(
                key,
                base_sha=base_sha,
                head_sha=diff_refs.get("head_sha"),
                mr_changes=changes,
                file_map=file_map,
            )
        return DiffPayload(
            pull_request={
                "id": key.review_request_id,
                "base_sha": diff_refs.get("base_sha"),
                "start_sha": diff_refs.get("start_sha"),
                "head_sha": diff_refs.get("head_sha"),
            },
            files=[
                {
                    "path": (change.get("new_path") or change.get("old_path") or ""),
                    "status": self._change_status(change),
                    "additions": 0,
                    "deletions": 0,
                    "patch": self._resolve_patch(key, change, diff_refs),
                    "old_path": change.get("old_path"),
                    "new_path": change.get("new_path"),
                }
                for change in changes
            ],
        )

    def list_threads(self, key: ReviewRequestKey) -> list[ThreadSnapshot]:
        payload = self._get_paginated(
            self._api_path(
                key,
                f"/merge_requests/{key.review_request_id}/discussions",
            )
        )
        threads: list[ThreadSnapshot] = []
        for item in payload:
            notes: list[ThreadNoteSnapshot] = []
            discussion_notes = item.get("notes") or []
            note_timestamps: list[datetime] = []
            for note in discussion_notes:
                created_at = _parse_gitlab_datetime(note.get("created_at"))
                updated_at = _parse_gitlab_datetime(note.get("updated_at"))
                if created_at is not None:
                    note_timestamps.append(created_at)
                if updated_at is not None:
                    note_timestamps.append(updated_at)
                notes.append(
                    ThreadNoteSnapshot(
                        note_ref=str(note.get("id")),
                        body=str(note.get("body") or ""),
                        author_type=self._author_type(note),
                        author_ref=((note.get("author") or {}).get("username")),
                        created_at=created_at,
                        resolved=note.get("resolved"),
                    )
                )
            first_note = discussion_notes[0] if discussion_notes else {}
            thread_updated_at = _parse_gitlab_datetime(item.get("updated_at"))
            if note_timestamps:
                thread_updated_at = max([*note_timestamps, thread_updated_at] if thread_updated_at else note_timestamps)
            threads.append(
                ThreadSnapshot(
                    thread_ref=str(item.get("id")),
                    comment_ref=str(first_note.get("id")) if first_note.get("id") else None,
                    resolved=bool(item.get("resolved")),
                    resolvable=bool(item.get("resolvable")),
                    body=str(first_note.get("body") or ""),
                    updated_at=thread_updated_at,
                    notes=notes,
                )
            )
        return threads

    def upsert_comment(
        self,
        key: ReviewRequestKey,
        request: CommentUpsertRequest,
    ) -> CommentUpsertResult:
        if request.existing_thread_ref:
            if request.reopen_if_resolved:
                self._put(
                    self._api_path(
                        key,
                        f"/merge_requests/{key.review_request_id}/discussions/{request.existing_thread_ref}",
                    ),
                    data={"resolved": "false"},
                )
            payload = self._post(
                self._api_path(
                    key,
                    f"/merge_requests/{key.review_request_id}/discussions/{request.existing_thread_ref}/notes",
                ),
                data={"body": request.body},
            )
            return CommentUpsertResult(
                ok=True,
                action="updated",
                comment_ref=str(payload.get("id")) if payload.get("id") else None,
                thread_ref=request.existing_thread_ref,
                raw=payload,
            )

        cache = self._ensure_mr_cache(key)
        diff_refs = cache.get("diff_refs") or {}
        file_map = cache.get("file_map") or {}
        file_meta = file_map.get(request.anchor.file_path) or {}
        new_path = file_meta.get("new_path") or request.anchor.file_path
        old_path = file_meta.get("old_path") or new_path
        if not (
            diff_refs.get("base_sha")
            and diff_refs.get("start_sha")
            and diff_refs.get("head_sha")
        ):
            raise RuntimeError("Unable to create inline discussion without GitLab diff refs")

        try:
            payload = self._post(
                self._api_path(
                    key,
                    f"/merge_requests/{key.review_request_id}/discussions",
                ),
                data={
                    "body": request.body,
                    "position[position_type]": "text",
                    "position[base_sha]": diff_refs["base_sha"],
                    "position[start_sha]": diff_refs["start_sha"],
                    "position[head_sha]": diff_refs["head_sha"],
                    "position[new_path]": new_path,
                    "position[old_path]": old_path,
                    "position[new_line]": str(request.anchor.start_line),
                },
            )
        except ReviewBotError as exc:
            if exc.category == "gitlab_api":
                raise ReviewBotError(
                    f"Unable to create inline discussion for {request.anchor.file_path}:{request.anchor.start_line}: {exc}",
                    category="inline_anchor",
                    retryable=False,
                    metadata={"file_path": request.anchor.file_path, "line_no": request.anchor.start_line},
                ) from exc
            raise
        notes = payload.get("notes") or []
        first = notes[0] if notes else {}
        return CommentUpsertResult(
            ok=True,
            action="created",
            comment_ref=str(first.get("id")) if first.get("id") else None,
            thread_ref=str(payload.get("id")) if payload.get("id") else None,
            raw=payload,
        )

    def resolve_thread(
        self,
        key: ReviewRequestKey,
        thread_ref: str,
        *,
        reason: str,
    ) -> dict[str, str | bool]:
        del reason
        payload = self._put(
            self._api_path(
                key,
                f"/merge_requests/{key.review_request_id}/discussions/{thread_ref}",
            ),
            data={"resolved": "true"},
        )
        return {"ok": True, "resolved": bool(payload.get("resolved"))}

    def publish_check(
        self,
        key: ReviewRequestKey,
        request: CheckPublishRequest,
    ) -> CheckPublishResult:
        if not request.head_sha:
            return CheckPublishResult(
                ok=True,
                state=request.state,
                description=request.description,
                raw={"note": "head sha missing"},
            )
        payload = self._post(
            self._api_path(
                key,
                f"/statuses/{request.head_sha}",
            ),
            data={
                "state": request.state,
                "description": request.description,
                "context": "review-bot",
            },
        )
        return CheckPublishResult(
            ok=True,
            state=request.state,
            description=request.description,
            raw=payload,
        )

    def collect_feedback(
        self,
        key: ReviewRequestKey,
        *,
        since: str | None = None,
    ) -> FeedbackPage:
        del since
        events: list[FeedbackRecord] = []
        for thread in self.list_threads(key):
            transition_marker = _feedback_time_key(thread.updated_at)
            events.append(
                FeedbackRecord(
                    event_key=f"{thread.thread_ref}:resolved:{transition_marker}:{int(thread.resolved)}",
                    event_type="resolved" if thread.resolved else "unresolved",
                    adapter_thread_ref=thread.thread_ref,
                    adapter_comment_ref=thread.comment_ref,
                    actor_type="system",
                    payload={"resolved": thread.resolved},
                    occurred_at=thread.updated_at,
                )
            )
            for note in thread.notes[1:]:
                if note.author_type != "human":
                    continue
                events.append(
                    FeedbackRecord(
                        event_key=f"{thread.thread_ref}:reply:{note.note_ref}",
                        event_type="reply",
                        adapter_thread_ref=thread.thread_ref,
                        adapter_comment_ref=note.note_ref,
                        actor_type="human",
                        actor_ref=note.author_ref,
                        payload={"body": note.body},
                        occurred_at=note.created_at,
                    )
                )
        return FeedbackPage(events=events)

    # Compatibility helpers for existing tests and shimmed callers
    def get_pull_request_diff(self, review_request_id: int) -> dict[str, object]:
        settings = get_settings()
        project_ref = settings.legacy_project_ref
        key = ReviewRequestKey(
            review_system="gitlab",
            project_ref=project_ref,
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
        settings = get_settings()
        key = ReviewRequestKey(
            review_system="gitlab",
            project_ref=settings.legacy_project_ref,
            review_request_id=str(review_request_id),
        )
        line = line_no or 1
        return self.upsert_comment(
            key,
            CommentUpsertRequest(
                fingerprint=f"legacy:{review_request_id}:{file_path}:{line}",
                body=body,
                anchor={
                    "file_path": file_path or "",
                    "start_line": line,
                    "end_line": line,
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
        settings = get_settings()
        key = ReviewRequestKey(
            review_system="gitlab",
            project_ref=settings.legacy_project_ref,
            review_request_id=str(review_request_id),
        )
        return self.publish_check(
            key,
            CheckPublishRequest(state=state, description=description),
        ).model_dump()

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self.token}

    def _api_path(self, key: ReviewRequestKey, suffix: str) -> str:
        project = quote(key.project_ref, safe="")
        return f"{self.base_url}/api/v4/projects/{project}{suffix}"

    def _get(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        return self._request_json("GET", url, params=params)

    def _get_paginated(self, url: str) -> list[dict[str, Any]]:
        page = 1
        items: list[dict[str, Any]] = []
        while True:
            payload = self._get(url, params={"per_page": 100, "page": page})
            page_items = payload or []
            if not isinstance(page_items, list):
                raise ReviewBotError(
                    f"Expected list response from GitLab pagination endpoint: {url}",
                    category="gitlab_api",
                    retryable=False,
                )
            items.extend(page_items)
            if len(page_items) < 100:
                break
            page += 1
        return items

    def _post(self, url: str, *, data: dict[str, Any]) -> Any:
        return self._request_json("POST", url, data=data)

    def _put(self, url: str, *, data: dict[str, Any]) -> Any:
        return self._request_json("PUT", url, data=data)

    def _request_text(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return response.text
            except httpx.TimeoutException:
                last_error = ReviewBotError(
                    f"GitLab {method} timed out: {url}",
                    category="gitlab_timeout",
                    retryable=True,
                    metadata={"url": url},
                )
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code >= 500 or status_code == 429
                last_error = ReviewBotError(
                    f"GitLab {method} {url} failed with {status_code}: {exc.response.text[:400]}",
                    category="gitlab_api",
                    retryable=retryable,
                    metadata={"url": url, "status_code": status_code},
                )
            except httpx.HTTPError as exc:
                last_error = ReviewBotError(
                    f"GitLab {method} {url} transport failure: {exc}",
                    category="gitlab_transport",
                    retryable=True,
                    metadata={"url": url},
                )
            if attempt >= self.max_retries:
                assert last_error is not None
                raise last_error
            time.sleep(self.retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("unreachable")

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    data=data,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as exc:
                last_error = ReviewBotError(
                    f"GitLab {method} timed out: {url}",
                    category="gitlab_timeout",
                    retryable=True,
                    metadata={"url": url},
                )
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code >= 500 or status_code == 429
                last_error = ReviewBotError(
                    f"GitLab {method} {url} failed with {status_code}: {exc.response.text[:400]}",
                    category="gitlab_api",
                    retryable=retryable,
                    metadata={"url": url, "status_code": status_code},
                )
            except httpx.HTTPError as exc:
                last_error = ReviewBotError(
                    f"GitLab {method} {url} transport failure: {exc}",
                    category="gitlab_transport",
                    retryable=True,
                    metadata={"url": url},
                )
            if attempt >= self.max_retries:
                assert last_error is not None
                raise last_error
            time.sleep(self.retry_backoff_seconds * (attempt + 1))
        raise RuntimeError("unreachable")

    def _change_status(self, change: dict[str, Any]) -> str:
        if change.get("new_file"):
            return "added"
        if change.get("deleted_file"):
            return "deleted"
        if change.get("renamed_file"):
            return "renamed"
        return "modified"

    def _fetch_incremental_changes(
        self,
        key: ReviewRequestKey,
        *,
        base_sha: str,
        head_sha: str | None,
        mr_changes: list[dict[str, Any]],
        file_map: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not head_sha:
            return mr_changes
        try:
            payload = self._get(
                self._api_path(key, "/repository/compare"),
                params={"from": base_sha, "to": head_sha, "straight": "true"},
            )
        except ReviewBotError:
            return mr_changes

        compare_changes = payload.get("diffs") or payload.get("changes") or []
        if not compare_changes:
            return mr_changes

        filtered: list[dict[str, Any]] = []
        for change in compare_changes:
            path = change.get("new_path") or change.get("old_path") or ""
            if not path:
                continue
            merged = dict(file_map.get(path) or {})
            merged.update(change)
            filtered.append(merged)
        return filtered or mr_changes

    def _resolve_patch(
        self,
        key: ReviewRequestKey,
        change: dict[str, Any],
        diff_refs: dict[str, str],
    ) -> str:
        patch = change.get("diff") or ""
        if patch.strip():
            return patch
        compare_patch = self._build_patch_from_compare(key, change, diff_refs)
        if compare_patch.strip():
            return compare_patch
        return self._build_patch_from_repository(key, change, diff_refs)

    def _build_patch_from_compare(
        self,
        key: ReviewRequestKey,
        change: dict[str, Any],
        diff_refs: dict[str, str],
    ) -> str:
        head_sha = diff_refs.get("head_sha")
        base_sha = diff_refs.get("start_sha") or diff_refs.get("base_sha")
        if not base_sha or not head_sha:
            return ""
        try:
            compare_changes = self._fetch_compare_changes(key, from_sha=base_sha, to_sha=head_sha)
        except ReviewBotError:
            return ""

        paths = {
            change.get("new_path") or "",
            change.get("old_path") or "",
        }
        for compare_change in compare_changes:
            compare_paths = {
                compare_change.get("new_path") or "",
                compare_change.get("old_path") or "",
            }
            if paths.isdisjoint(compare_paths):
                continue
            compare_patch = compare_change.get("diff") or ""
            if compare_patch.strip():
                return compare_patch
        return ""

    def _build_patch_from_repository(
        self,
        key: ReviewRequestKey,
        change: dict[str, Any],
        diff_refs: dict[str, str],
    ) -> str:
        old_path = change.get("old_path") or change.get("new_path")
        new_path = change.get("new_path") or change.get("old_path")
        old_ref = diff_refs.get("start_sha") or diff_refs.get("base_sha")
        new_ref = diff_refs.get("head_sha")
        if not old_path and not new_path:
            return ""

        old_lines: list[str] = []
        new_lines: list[str] = []

        if not change.get("new_file") and old_path and old_ref:
            old_body = self._fetch_repository_file_if_available(key, old_path, old_ref)
            if old_body is not None:
                old_lines = old_body.splitlines()

        if not change.get("deleted_file") and new_path and new_ref:
            new_body = self._fetch_repository_file_if_available(key, new_path, new_ref)
            if new_body is not None:
                new_lines = new_body.splitlines()

        if not old_lines and not new_lines:
            return ""

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{old_path or new_path}",
            tofile=f"b/{new_path or old_path}",
            lineterm="",
        )
        return "\n".join(diff)

    def _fetch_repository_file(self, key: ReviewRequestKey, path: str, ref: str) -> str:
        cache_key = (f"{key.project_ref}:{path}", ref)
        cached = self._file_cache.get(cache_key)
        if cached is not None:
            return cached
        encoded_path = quote(path, safe="")
        text = self._request_text(
            "GET",
            self._api_path(key, f"/repository/files/{encoded_path}/raw"),
            params={"ref": ref},
        )
        self._file_cache[cache_key] = text
        return text

    def _fetch_repository_file_if_available(
        self,
        key: ReviewRequestKey,
        path: str,
        ref: str,
    ) -> str | None:
        try:
            return self._fetch_repository_file(key, path, ref)
        except ReviewBotError as exc:
            if exc.category == "gitlab_api" and exc.metadata.get("status_code") == 404:
                return None
            raise

    def _fetch_compare_changes(
        self,
        key: ReviewRequestKey,
        *,
        from_sha: str,
        to_sha: str,
    ) -> list[dict[str, Any]]:
        cache_key = (key.project_ref, from_sha, to_sha)
        cached = self._compare_cache.get(cache_key)
        if cached is not None:
            return cached
        payload = self._get(
            self._api_path(key, "/repository/compare"),
            params={"from": from_sha, "to": to_sha, "straight": "true"},
        )
        compare_changes = payload.get("diffs") or payload.get("changes") or []
        normalized = list(compare_changes)
        self._compare_cache[cache_key] = normalized
        return normalized

    def _author_type(self, note: dict[str, Any]) -> str:
        if note.get("system"):
            return "system"
        username = ((note.get("author") or {}).get("username")) or ""
        if username == get_settings().bot_author_name:
            return "bot"
        return "human"

    def _ensure_mr_cache(self, key: ReviewRequestKey) -> dict[str, Any]:
        cache_key = (key.project_ref, key.review_request_id)
        cached = self._mr_cache.get(cache_key)
        if cached:
            return cached

        payload = self._get(
            self._api_path(
                key,
                f"/merge_requests/{key.review_request_id}/changes",
            )
        )
        diff_refs = payload.get("diff_refs") or {}
        file_map: dict[str, dict[str, Any]] = {}
        for change in payload.get("changes", []):
            path = change.get("new_path") or change.get("old_path") or ""
            file_map[path] = {
                "new_path": change.get("new_path"),
                "old_path": change.get("old_path"),
                "renamed_file": bool(change.get("renamed_file")),
                "new_file": bool(change.get("new_file")),
                "deleted_file": bool(change.get("deleted_file")),
            }
        cached = {
            "diff_refs": diff_refs,
            "file_map": file_map,
        }
        self._mr_cache[cache_key] = cached
        return cached


def _parse_gitlab_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _feedback_time_key(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    return value.strftime("%Y%m%dT%H%M%S%f%z")
