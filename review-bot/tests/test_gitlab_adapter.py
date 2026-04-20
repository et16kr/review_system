from __future__ import annotations

import httpx

from app.review_systems.gitlab import GitLabReviewSystemAdapter


def test_gitlab_adapter_rebuilds_patch_when_gitlab_omits_large_new_file_diff(monkeypatch) -> None:
    adapter = GitLabReviewSystemAdapter(
        base_url="http://gitlab.local",
        token="token",
        project_id="root/altidev4-review",
    )

    def fake_get(url: str, *, headers=None, params=None, timeout=None):
        del headers, timeout
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

        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(httpx, "get", fake_get)

    payload = adapter.get_pull_request_diff(2)

    assert payload["files"][0]["status"] == "added"
    assert "@@ -0,0 +1,2 @@" in payload["files"][0]["patch"]
    assert "+char* p = (char*)malloc(10);" in payload["files"][0]["patch"]
    assert "+free(p);" in payload["files"][0]["patch"]
