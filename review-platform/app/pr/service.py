from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import PullRequest
from app.git.repository_service import RepositoryService
from app.schemas import PullRequestCreate


class PullRequestService:
    def __init__(self, repository_service: RepositoryService | None = None) -> None:
        self.repository_service = repository_service or RepositoryService()

    def create_pull_request(self, session: Session, payload: PullRequestCreate) -> PullRequest:
        repository = self.repository_service.get_repository(session, payload.repository_id)
        if payload.base_branch == payload.head_branch:
            raise HTTPException(status_code=400, detail="Base branch and head branch must differ.")
        base_sha = self.repository_service.resolve_branch_sha(repository, payload.base_branch)
        head_sha = self.repository_service.resolve_branch_sha(repository, payload.head_branch)
        if base_sha == head_sha:
            raise HTTPException(status_code=400, detail="No diff between base and head branches.")

        pull_request = PullRequest(
            repository_id=repository.id,
            title=payload.title,
            description=payload.description,
            base_branch=payload.base_branch,
            head_branch=payload.head_branch,
            base_sha=base_sha,
            head_sha=head_sha,
            status="open",
            created_by=payload.created_by,
        )
        session.add(pull_request)
        session.commit()
        session.refresh(pull_request)
        return pull_request

    def list_pull_requests(
        self,
        session: Session,
        repository_id: int | None = None,
    ) -> list[PullRequest]:
        query = session.query(PullRequest)
        if repository_id is not None:
            query = query.filter(PullRequest.repository_id == repository_id)
        return query.order_by(PullRequest.updated_at.desc(), PullRequest.id.desc()).all()

    def get_pull_request(self, session: Session, pr_id: int) -> PullRequest:
        pull_request = session.get(PullRequest, pr_id)
        if pull_request is None:
            raise HTTPException(status_code=404, detail=f"Pull request not found: {pr_id}")
        return pull_request
