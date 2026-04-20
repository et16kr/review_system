from __future__ import annotations

from datetime import UTC, datetime

import httpx

from review_bot.contracts import CommentUpsertRequest, ReviewRequestKey, ThreadNoteSnapshot, ThreadSnapshot
from review_bot.review_systems.gitlab import GitLabReviewSystemAdapter


def test_gitlab_adapter_rebuilds_patch_when_gitlab_omits_large_new_file_diff(monkeypatch) -> None:
    adapter = GitLabReviewSystemAdapter(
        base_url="http://gitlab.local",
        token="token",
    )
    key = ReviewRequestKey(
        review_system="gitlab",
        project_ref="root/altidev4-review",
        review_request_id="2",
    )

    def fake_request(method: str, url: str, *, headers=None, params=None, data=None, timeout=None):
        del headers, timeout, data
        assert method == "GET"
        if url.endswith("/merge_requests/2/changes"):
            payload = {
                "diff_refs": {
                    "base_sha": "base123",
                    "start_sha": "base123",
                    "head_sha": "head123",
                },
                "changes": [
                    {
                        "new_path": "src/id/ids/idsTde.cpp",
                        "old_path": "src/id/ids/idsTde.cpp",
                        "new_file": True,
                        "deleted_file": False,
                        "renamed_file": False,
                        "diff": "",
                    }
                ],
            }
            request = httpx.Request("GET", url)
            return httpx.Response(200, json=payload, request=request)

        if url.endswith("/repository/files/src%2Fid%2Fids%2FidsTde.cpp/raw"):
            assert params == {"ref": "head123"}
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                text="char* p = (char*)malloc(10);\nfree(p);\n",
                request=request,
            )
        if url.endswith("/repository/compare"):
            request = httpx.Request("GET", url)
            return httpx.Response(200, json={"diffs": []}, request=request)

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx, "request", fake_request)

    payload = adapter.fetch_diff(key, mode="full")

    assert payload.files[0].status == "added"
    assert "@@ -0,0 +1,2 @@" in payload.files[0].patch
    assert "+char* p = (char*)malloc(10);" in payload.files[0].patch
    assert "+free(p);" in payload.files[0].patch


def test_gitlab_adapter_uses_compare_diff_for_incremental_mode(monkeypatch) -> None:
    adapter = GitLabReviewSystemAdapter(
        base_url="http://gitlab.local",
        token="token",
    )
    key = ReviewRequestKey(
        review_system="gitlab",
        project_ref="root/altidev4-review",
        review_request_id="2",
    )

    def fake_request(method: str, url: str, *, headers=None, params=None, data=None, timeout=None):
        del headers, timeout, data
        request = httpx.Request(method, url)
        if url.endswith("/merge_requests/2/changes"):
            return httpx.Response(
                200,
                json={
                    "diff_refs": {
                        "base_sha": "mr-base",
                        "start_sha": "mr-start",
                        "head_sha": "head123",
                    },
                    "changes": [
                        {
                            "new_path": "src/id/ids/idsTde.cpp",
                            "old_path": "src/id/ids/idsTde.cpp",
                            "new_file": False,
                            "deleted_file": False,
                            "renamed_file": False,
                            "diff": "@@ -10,1 +10,1 @@\n-old\n+new\n",
                        },
                        {
                            "new_path": "src/sm/smm/smmManager.cpp",
                            "old_path": "src/sm/smm/smmManager.cpp",
                            "new_file": False,
                            "deleted_file": False,
                            "renamed_file": False,
                            "diff": "@@ -20,1 +20,1 @@\n-old\n+new\n",
                        },
                    ],
                },
                request=request,
            )

        if url.endswith("/repository/compare"):
            assert params == {"from": "oldrev123", "to": "head123", "straight": "true"}
            return httpx.Response(
                200,
                json={
                    "diffs": [
                        {
                            "new_path": "src/sm/smm/smmManager.cpp",
                            "old_path": "src/sm/smm/smmManager.cpp",
                            "new_file": False,
                            "deleted_file": False,
                            "renamed_file": False,
                            "diff": "@@ -30,1 +30,1 @@\n-old-continue\n+no-continue\n",
                        }
                    ]
                },
                request=request,
            )

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx, "request", fake_request)

    payload = adapter.fetch_diff(key, mode="incremental", base_sha="oldrev123")

    assert [item.path for item in payload.files] == ["src/sm/smm/smmManager.cpp"]
    assert payload.files[0].patch == "@@ -30,1 +30,1 @@\n-old-continue\n+no-continue\n"


def test_gitlab_adapter_rebuilds_modified_patch_from_repository_versions_when_gitlab_omits_diff(
    monkeypatch,
) -> None:
    adapter = GitLabReviewSystemAdapter(
        base_url="http://gitlab.local",
        token="token",
    )
    key = ReviewRequestKey(
        review_system="gitlab",
        project_ref="root/altidev4-review",
        review_request_id="3",
    )

    def fake_request(method: str, url: str, *, headers=None, params=None, data=None, timeout=None):
        del headers, timeout, data
        request = httpx.Request(method, url)
        if url.endswith("/merge_requests/3/changes"):
            return httpx.Response(
                200,
                json={
                    "diff_refs": {
                        "base_sha": "base123",
                        "start_sha": "start123",
                        "head_sha": "head123",
                    },
                    "changes": [
                        {
                            "new_path": "src/sm/smm/smmManager.cpp",
                            "old_path": "src/sm/smm/smmManager.cpp",
                            "new_file": False,
                            "deleted_file": False,
                            "renamed_file": False,
                            "diff": "",
                        }
                    ],
                },
                request=request,
            )
        if url.endswith("/repository/compare"):
            return httpx.Response(200, json={"diffs": []}, request=request)
        if url.endswith("/repository/files/src%2Fsm%2Fsmm%2FsmmManager.cpp/raw"):
            if params == {"ref": "start123"}:
                return httpx.Response(
                    200,
                    text="if (mode) {\n    runOld();\n}\n",
                    request=request,
                )
            if params == {"ref": "head123"}:
                return httpx.Response(
                    200,
                    text="if (mode) {\n    runNew();\n    flush();\n}\n",
                    request=request,
                )
        raise AssertionError(f"Unexpected URL: {url} params={params}")

    monkeypatch.setattr(httpx, "request", fake_request)

    payload = adapter.fetch_diff(key, mode="full")

    assert payload.files[0].status == "modified"
    assert "@@ -1,3 +1,4 @@" in payload.files[0].patch
    assert "-    runOld();" in payload.files[0].patch
    assert "+    runNew();" in payload.files[0].patch
    assert "+    flush();" in payload.files[0].patch


def test_gitlab_adapter_collects_resolve_and_human_reply_feedback(monkeypatch) -> None:
    adapter = GitLabReviewSystemAdapter(
        base_url="http://gitlab.local",
        token="token",
    )
    key = ReviewRequestKey(
        review_system="gitlab",
        project_ref="root/altidev4-review",
        review_request_id="5",
    )

    monkeypatch.setattr(
        adapter,
        "list_threads",
        lambda _key: [
            ThreadSnapshot(
                thread_ref="thread-1",
                comment_ref="note-1",
                resolved=True,
                body="[봇 리뷰] first",
                updated_at=datetime(2026, 4, 20, 1, 2, 3, tzinfo=UTC),
                notes=[
                    ThreadNoteSnapshot(
                        note_ref="note-1",
                        body="[봇 리뷰] first",
                        author_type="bot",
                    ),
                    ThreadNoteSnapshot(
                        note_ref="note-2",
                        body="사람이 남긴 코멘트",
                        author_type="human",
                        author_ref="reviewer",
                    ),
                ],
            )
        ],
    )

    feedback = adapter.collect_feedback(key)

    assert [event.event_type for event in feedback.events] == ["resolved", "reply"]
    assert feedback.events[0].event_key == "thread-1:resolved:20260420T010203000000+0000:1"
    assert feedback.events[0].occurred_at == datetime(2026, 4, 20, 1, 2, 3, tzinfo=UTC)
    assert feedback.events[1].actor_ref == "reviewer"


def test_gitlab_adapter_reopens_resolved_discussion_before_reply(monkeypatch) -> None:
    adapter = GitLabReviewSystemAdapter(
        base_url="http://gitlab.local",
        token="token",
    )
    key = ReviewRequestKey(
        review_system="gitlab",
        project_ref="root/altidev4-review",
        review_request_id="8",
    )

    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method: str, url: str, *, headers=None, params=None, data=None, timeout=None):
        del headers, params, timeout
        calls.append((method, url, data))
        request = httpx.Request(method, url)
        if url.endswith("/merge_requests/8/discussions/thread-1"):
            return httpx.Response(200, json={"resolved": False}, request=request)
        if url.endswith("/merge_requests/8/discussions/thread-1/notes"):
            return httpx.Response(201, json={"id": 77}, request=request)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx, "request", fake_request)

    result = adapter.upsert_comment(
        key,
        CommentUpsertRequest.model_validate(
            {
                "fingerprint": "abc",
                "body": "[봇 리뷰] reopen",
                "anchor": {"file_path": "src/a.cpp", "start_line": 10, "end_line": 10},
                "existing_thread_ref": "thread-1",
                "reopen_if_resolved": True,
            }
        ),
    )

    assert result.action == "updated"
    assert [call[0] for call in calls] == ["PUT", "POST"]
