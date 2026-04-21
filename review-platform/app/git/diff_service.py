from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import HTTPException

from app.db.models import PullRequest, Repository
from app.schemas import ChangedFileResponse


class DiffService:
    def get_changed_files(
        self, repository: Repository, pull_request: PullRequest, *, base_sha: str | None = None
    ) -> list[ChangedFileResponse]:
        repo_path = Path(repository.storage_path)
        from_sha = base_sha or pull_request.base_sha
        to_sha = pull_request.head_sha
        name_status = self._run_git(
            repo_path,
            "diff",
            "--name-status",
            from_sha,
            to_sha,
        )
        stats_output = self._run_git(
            repo_path,
            "diff",
            "--numstat",
            from_sha,
            to_sha,
        )
        stats_by_path = self._parse_numstat(stats_output)

        files: list[ChangedFileResponse] = []
        for raw_line in name_status.splitlines():
            if not raw_line.strip():
                continue
            tokens = raw_line.split("\t")
            status_token = tokens[0]
            path = tokens[-1]
            additions, deletions = stats_by_path.get(path, (0, 0))
            patch = self._run_git(
                repo_path,
                "diff",
                "--unified=3",
                from_sha,
                to_sha,
                "--",
                path,
            )
            files.append(
                ChangedFileResponse(
                    path=path,
                    status=self._normalize_status(status_token),
                    additions=additions,
                    deletions=deletions,
                    patch=patch,
                )
            )
        return files

    def _parse_numstat(self, output: str) -> dict[str, tuple[int, int]]:
        stats: dict[str, tuple[int, int]] = {}
        for raw_line in output.splitlines():
            if not raw_line.strip():
                continue
            tokens = raw_line.split("\t")
            if len(tokens) < 3:
                continue
            additions = 0 if tokens[0] == "-" else int(tokens[0])
            deletions = 0 if tokens[1] == "-" else int(tokens[1])
            path = tokens[-1]
            stats[path] = (additions, deletions)
        return stats

    def _normalize_status(self, token: str) -> str:
        if token.startswith("A"):
            return "added"
        if token.startswith("D"):
            return "deleted"
        if token.startswith("R"):
            return "renamed"
        return "modified"

    def _run_git(self, repo_path: Path, *args: str) -> str:
        command = ["git", "--git-dir", str(repo_path), *args]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or exc.stdout.strip() or "git command failed"
            raise HTTPException(status_code=400, detail=stderr) from exc
        return completed.stdout
