from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.config import get_settings
from app.db.models import PullRequestComment, PullRequestStatus
from app.db.session import SessionLocal, engine


def test_repository_and_pull_request_flow(tmp_path: Path) -> None:
    _reset_platform_state()

    with TestClient(app) as client:
        repo_response = client.post(
            "/api/repos",
            json={"name": "sample", "description": "sample repo", "default_branch": "main"},
        )
        assert repo_response.status_code == 200
        repository = repo_response.json()
        bare_repo_path = Path(repository["storage_path"])
        assert bare_repo_path.exists()

        working_copy = tmp_path / "sample-work"
        _run(["git", "clone", str(bare_repo_path), str(working_copy)])
        _run(["git", "config", "user.name", "Tester"], cwd=working_copy)
        _run(["git", "config", "user.email", "tester@example.com"], cwd=working_copy)

        source_file = working_copy / "src.cpp"
        source_file.write_text("int main() {\n    return 0;\n}\n", encoding="utf-8")
        _run(["git", "add", "src.cpp"], cwd=working_copy)
        _run(["git", "commit", "-m", "initial"], cwd=working_copy)
        _run(["git", "push", "origin", "main"], cwd=working_copy)

        _run(["git", "checkout", "-b", "feature/memory-fix"], cwd=working_copy)
        source_file.write_text(
            "int main() {\n    char* ptr = (char*)malloc(10);\n    free(ptr);\n    return 0;\n}\n",
            encoding="utf-8",
        )
        _run(["git", "add", "src.cpp"], cwd=working_copy)
        _run(["git", "commit", "-m", "memory fix"], cwd=working_copy)
        _run(["git", "push", "origin", "feature/memory-fix"], cwd=working_copy)

        pr_response = client.post(
            "/api/pull-requests",
            json={
                "repository_id": repository["id"],
                "title": "Memory handling update",
                "description": "test PR",
                "base_branch": "main",
                "head_branch": "feature/memory-fix",
            },
        )
        assert pr_response.status_code == 200
        pull_request = pr_response.json()

        diff_response = client.get(f"/api/pull-requests/{pull_request['id']}/diff")
        assert diff_response.status_code == 200
        diff_payload = diff_response.json()
        assert diff_payload["files"][0]["path"] == "src.cpp"
        assert "malloc" in diff_payload["files"][0]["patch"]
        assert "free" in diff_payload["files"][0]["patch"]

        session = SessionLocal()
        try:
            session.add(
                PullRequestComment(
                    pull_request_id=pull_request["id"],
                    file_path="src.cpp",
                    line_no=2,
                    comment_type="inline",
                    author_type="bot",
                    created_by="review-bot",
                    body="malloc/free는 RAII로 감싸는 편이 안전합니다.",
                )
            )
            session.add(
                PullRequestStatus(
                    pull_request_id=pull_request["id"],
                    context="review-bot",
                    state="success",
                    description="자동 리뷰 완료",
                    created_by="review-bot",
                )
            )
            session.commit()
        finally:
            session.close()

        with patch("app.api.main._try_get_bot_state") as mock_state:
            mock_state.return_value = {
                "pr_id": pull_request["id"],
                "last_review_run_id": 1,
                "last_head_sha": pull_request["head_sha"],
                "published_batch_count": 1,
                "open_finding_count": 1,
                "resolved_finding_count": 0,
                "next_batch_size": 5,
            }
            page_response = client.get(f"/pull-requests/{pull_request['id']}")

        assert page_response.status_code == 200
        assert "Memory handling update" in page_response.text
        assert "malloc/free" in page_response.text
        assert "자동 리뷰 완료" in page_response.text
        assert "다음 5개 게시" in page_response.text


def test_pull_request_diff_supports_optional_base_sha(tmp_path: Path) -> None:
    _reset_platform_state()

    with TestClient(app) as client:
        repo_response = client.post(
            "/api/repos",
            json={"name": "sample-base-sha", "description": "sample repo", "default_branch": "main"},
        )
        repository = repo_response.json()
        bare_repo_path = Path(repository["storage_path"])

        working_copy = tmp_path / "sample-base-sha-work"
        _run(["git", "clone", str(bare_repo_path), str(working_copy)])
        _run(["git", "config", "user.name", "Tester"], cwd=working_copy)
        _run(["git", "config", "user.email", "tester@example.com"], cwd=working_copy)

        source_file = working_copy / "src.cpp"
        source_file.write_text("int main() {\n    return 0;\n}\n", encoding="utf-8")
        _run(["git", "add", "src.cpp"], cwd=working_copy)
        _run(["git", "commit", "-m", "initial"], cwd=working_copy)
        _run(["git", "push", "origin", "main"], cwd=working_copy)

        _run(["git", "checkout", "-b", "feature/base-sha"], cwd=working_copy)
        source_file.write_text(
            "int main() {\n    char* ptr = (char*)malloc(10);\n    return 0;\n}\n",
            encoding="utf-8",
        )
        _run(["git", "add", "src.cpp"], cwd=working_copy)
        _run(["git", "commit", "-m", "feature-1"], cwd=working_copy)
        first_feature_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=working_copy,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        source_file.write_text(
            "int main() {\n    char* ptr = (char*)malloc(10);\n    free(ptr);\n    return 0;\n}\n",
            encoding="utf-8",
        )
        _run(["git", "add", "src.cpp"], cwd=working_copy)
        _run(["git", "commit", "-m", "feature-2"], cwd=working_copy)
        _run(["git", "push", "origin", "feature/base-sha"], cwd=working_copy)

        pr_response = client.post(
            "/api/pull-requests",
            json={
                "repository_id": repository["id"],
                "title": "Base SHA diff",
                "description": "test PR",
                "base_branch": "main",
                "head_branch": "feature/base-sha",
            },
        )
        assert pr_response.status_code == 200
        pull_request = pr_response.json()

        full_diff_response = client.get(f"/api/pull-requests/{pull_request['id']}/diff")
        assert full_diff_response.status_code == 200
        full_patch = full_diff_response.json()["files"][0]["patch"]
        assert "malloc" in full_patch
        assert "free" in full_patch

        incremental_diff_response = client.get(
            f"/api/pull-requests/{pull_request['id']}/diff",
            params={"base_sha": first_feature_sha},
        )
        assert incremental_diff_response.status_code == 200
        incremental_patch = incremental_diff_response.json()["files"][0]["patch"]
        assert "+    free(ptr);" in incremental_patch
        assert "+    char* ptr = (char*)malloc(10);" not in incremental_patch


def test_bot_facade_routes_forward_requests() -> None:
    settings = _reset_platform_state()
    with TestClient(app) as client, patch("app.api.main.bot_client") as mock_bot:
        repo_response = client.post(
            "/api/repos",
            json={"name": "bot-facade", "description": "bot repo", "default_branch": "main"},
        )
        repository = repo_response.json()
        bare_repo_path = Path(repository["storage_path"])

        with TemporaryGitRepo(
            tmp_path=Path(settings.project_root) / "storage" / "tmp-bot-facade",
            bare_repo_path=bare_repo_path,
        ) as working_copy:
            source_file = working_copy / "sample.cpp"
            source_file.write_text("int main() { return 0; }\n", encoding="utf-8")
            _run(["git", "add", "sample.cpp"], cwd=working_copy)
            _run(["git", "commit", "-m", "initial"], cwd=working_copy)
            _run(["git", "push", "origin", "main"], cwd=working_copy)

            _run(["git", "checkout", "-b", "feature/review"], cwd=working_copy)
            source_file.write_text(
                "int main() { char* p = (char*)malloc(8); free(p); }\n",
                encoding="utf-8",
            )
            _run(["git", "add", "sample.cpp"], cwd=working_copy)
            _run(["git", "commit", "-m", "update"], cwd=working_copy)
            _run(["git", "push", "origin", "feature/review"], cwd=working_copy)

        pr = client.post(
            "/api/pull-requests",
            json={
                "repository_id": repository["id"],
                "title": "Trigger bot",
                "description": "",
                "base_branch": "main",
                "head_branch": "feature/review",
            },
        ).json()
        mock_bot.trigger_review.return_value = {
            "accepted": True,
            "review_run_id": 9,
            "status": "queued",
        }
        mock_bot.publish_next_batch.return_value = {
            "accepted": True,
            "review_run_id": 9,
            "status": "queued",
        }
        mock_bot.get_state.return_value = {
            "pr_id": pr["id"],
            "last_review_run_id": 9,
            "last_head_sha": pr["head_sha"],
            "published_batch_count": 1,
            "open_finding_count": 3,
            "resolved_finding_count": 0,
            "next_batch_size": 5,
        }

        review_response = client.post(f"/api/pull-requests/{pr['id']}/bot/review", json={})
        next_batch_response = client.post(f"/api/pull-requests/{pr['id']}/bot/next-batch", json={})
        state_response = client.get(f"/api/pull-requests/{pr['id']}/bot/state")

        assert review_response.status_code == 200
        assert review_response.json()["status"] == "queued"
        assert next_batch_response.status_code == 200
        assert state_response.status_code == 200
        assert state_response.json()["last_review_run_id"] == 9


def _run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)


def _reset_platform_state():
    settings = get_settings()
    engine.dispose()
    db_path = Path(settings.database_url.removeprefix("sqlite:///"))
    if db_path.exists():
        db_path.unlink()
    if settings.storage_root.exists():
        shutil.rmtree(settings.storage_root)
    return settings


class TemporaryGitRepo:
    def __init__(self, *, tmp_path: Path, bare_repo_path: Path) -> None:
        self.tmp_path = tmp_path
        self.bare_repo_path = bare_repo_path

    def __enter__(self) -> Path:
        if self.tmp_path.exists():
            shutil.rmtree(self.tmp_path)
        _run(["git", "clone", str(self.bare_repo_path), str(self.tmp_path)])
        _run(["git", "config", "user.name", "Tester"], cwd=self.tmp_path)
        _run(["git", "config", "user.email", "tester@example.com"], cwd=self.tmp_path)
        return self.tmp_path

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        if self.tmp_path.exists():
            shutil.rmtree(self.tmp_path)
