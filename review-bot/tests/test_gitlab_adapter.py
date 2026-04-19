from __future__ import annotations

from unittest.mock import patch

import httpx

from app.review_systems.gitlab import GitLabReviewSystemAdapter


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "http://example.test")

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status={self.status_code}",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )


def test_gitlab_adapter_posts_inline_discussion_when_diff_context_exists() -> None:
    adapter = GitLabReviewSystemAdapter(
        base_url="http://gitlab",
        token="token",
        project_id="root/altidev4",
    )
    discussion_calls: list[tuple[str, dict]] = []

    def fake_get(url: str, headers: dict, timeout: float):
        del headers, timeout
        assert url.endswith("/merge_requests/1/changes")
        return FakeResponse(
            {
                "diff_refs": {
                    "base_sha": "base",
                    "start_sha": "start",
                    "head_sha": "head",
                },
                "changes": [
                    {
                        "new_path": "src/a.cpp",
                        "old_path": "src/a.cpp",
                        "diff": "@@ -1 +1 @@\n+ int x = 0;\n",
                    }
                ],
            }
        )

    def fake_post(url: str, headers: dict, data: dict, timeout: float):
        del headers, timeout
        discussion_calls.append((url, data))
        return FakeResponse({"id": "discussion-1", "notes": [{"id": 42}]})

    with patch("app.review_systems.gitlab.httpx.get", side_effect=fake_get):
        adapter.get_pull_request_diff(1)
    with patch("app.review_systems.gitlab.httpx.post", side_effect=fake_post):
        comment = adapter.post_comment(
            1,
            body="review body",
            file_path="src/a.cpp",
            line_no=1,
        )

    assert comment["id"] == 42
    url, data = discussion_calls[0]
    assert url.endswith("/merge_requests/1/discussions")
    assert data["position[new_line]"] == "1"
    assert data["position[new_path]"] == "src/a.cpp"


def test_gitlab_adapter_falls_back_to_note_when_inline_discussion_fails() -> None:
    adapter = GitLabReviewSystemAdapter(
        base_url="http://gitlab",
        token="token",
        project_id="root/altidev4",
    )
    calls: list[tuple[str, dict]] = []

    def fake_get(url: str, headers: dict, timeout: float):
        del url, headers, timeout
        return FakeResponse(
            {
                "diff_refs": {
                    "base_sha": "base",
                    "start_sha": "start",
                    "head_sha": "head",
                },
                "changes": [
                    {
                        "new_path": "src/a.cpp",
                        "old_path": "src/a.cpp",
                        "diff": "@@ -1 +1 @@\n+ int x = 0;\n",
                    }
                ],
            }
        )

    def fake_post(url: str, headers: dict, data: dict, timeout: float):
        del headers, timeout
        calls.append((url, data))
        if url.endswith("/discussions"):
            return FakeResponse({"message": "bad position"}, status_code=400)
        return FakeResponse({"id": 99})

    with patch("app.review_systems.gitlab.httpx.get", side_effect=fake_get):
        adapter.get_pull_request_diff(1)
    with patch("app.review_systems.gitlab.httpx.post", side_effect=fake_post):
        comment = adapter.post_comment(
            1,
            body="review body",
            file_path="src/a.cpp",
            line_no=1,
        )

    assert comment["id"] == 99
    assert calls[0][0].endswith("/merge_requests/1/discussions")
    assert calls[1][0].endswith("/merge_requests/1/notes")
    assert calls[1][1]["body"].startswith("review body")
