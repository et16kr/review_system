from __future__ import annotations

import re
import subprocess
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Repository
from app.schemas import RepositoryCreate

SAFE_REPO_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class RepositoryService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def list_repositories(self, session: Session) -> list[Repository]:
        return session.query(Repository).order_by(Repository.id.asc()).all()

    def get_repository(self, session: Session, repo_id: int) -> Repository:
        repository = session.get(Repository, repo_id)
        if repository is None:
            raise HTTPException(status_code=404, detail=f"Repository not found: {repo_id}")
        return repository

    def create_repository(self, session: Session, payload: RepositoryCreate) -> Repository:
        if not SAFE_REPO_NAME.match(payload.name):
            raise HTTPException(
                status_code=400,
                detail="Repository name contains invalid characters.",
            )
        existing = (
            session.query(Repository)
            .filter(Repository.name == payload.name)
            .one_or_none()
        )
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Repository already exists: {payload.name}",
            )

        self.settings.storage_root.mkdir(parents=True, exist_ok=True)
        repo_path = self.settings.storage_root / f"{payload.name}.git"
        if repo_path.exists():
            raise HTTPException(
                status_code=409,
                detail=f"Repository storage path already exists: {repo_path}",
            )
        self._run_git(
            Path("."),
            "init",
            "--bare",
            f"--initial-branch={payload.default_branch}",
            str(repo_path),
        )
        repository = Repository(
            name=payload.name,
            description=payload.description,
            storage_path=str(repo_path),
            default_branch=payload.default_branch,
        )
        session.add(repository)
        session.commit()
        session.refresh(repository)
        return repository

    def resolve_branch_sha(self, repository: Repository, branch: str) -> str:
        try:
            output = self._run_git(
                Path(repository.storage_path),
                "rev-parse",
                f"refs/heads/{branch}",
            )
        except HTTPException as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Branch not found in {repository.name}: {branch}",
            ) from exc
        return output.strip()

    def _run_git(self, repo_path: Path, *args: str) -> str:
        command = ["git"]
        if repo_path != Path("."):
            command.extend(["--git-dir", str(repo_path)])
        command.extend(args)
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
