from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.clients.bot_client import BotClient
from app.config import get_settings
from app.db.models import PullRequestComment, PullRequestStatus, Repository
from app.db.session import get_session, init_db
from app.git.diff_service import DiffService
from app.git.repository_service import RepositoryService
from app.pr.service import PullRequestService
from app.schemas import (
    BotNextBatchTrigger,
    BotReviewResponse,
    BotReviewTrigger,
    BotStateResponse,
    CommentCreate,
    CommentResponse,
    PullRequestCreate,
    PullRequestDiffResponse,
    PullRequestListResponse,
    PullRequestResponse,
    RepositoryCreate,
    RepositoryResponse,
    StatusCreate,
    StatusResponse,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Review Platform", version="0.1.0", lifespan=lifespan)
settings = get_settings()
templates = Jinja2Templates(directory=str(settings.project_root / "templates"))
repository_service = RepositoryService()
pull_request_service = PullRequestService(repository_service)
diff_service = DiffService()
bot_client = BotClient(settings.bot_base_url)
SessionDep = Annotated[Session, Depends(get_session)]


def _repository_to_response(repository: Repository) -> RepositoryResponse:
    clone_url = (
        f"{settings.clone_base_url.rstrip('/')}/{repository.name}.git"
        if settings.clone_base_url
        else repository.storage_path
    )
    return RepositoryResponse.model_validate(
        {
            **repository.__dict__,
            "clone_url": clone_url,
        }
    )


def _try_get_bot_state(pr_id: int) -> BotStateResponse | None:
    try:
        return BotStateResponse(**bot_client.get_state(pr_id))
    except httpx.HTTPError:
        return None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session: SessionDep) -> HTMLResponse:
    repositories = [
        _repository_to_response(item)
        for item in repository_service.list_repositories(session)
    ]
    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={
            "repositories": repositories,
            "page_title": "Repositories",
        },
    )


@app.post("/repos")
def create_repository_form(
    session: SessionDep,
    name: str = Form(...),
    description: str = Form(""),
    default_branch: str = Form("main"),
):
    payload = RepositoryCreate(name=name, description=description, default_branch=default_branch)
    repository = repository_service.create_repository(session, payload)
    return RedirectResponse(url=f"/repos/{repository.id}", status_code=303)


@app.get("/repos/{repo_id}", response_class=HTMLResponse)
def repository_detail(repo_id: int, request: Request, session: SessionDep) -> HTMLResponse:
    repository = _repository_to_response(repository_service.get_repository(session, repo_id))
    pull_requests = [
        PullRequestResponse.model_validate(item, from_attributes=True)
        for item in pull_request_service.list_pull_requests(session, repository_id=repo_id)
    ]
    return templates.TemplateResponse(
        name="repository_detail.html",
        request=request,
        context={
            "repository": repository,
            "pull_requests": pull_requests,
            "page_title": repository.name,
        },
    )


@app.post("/repos/{repo_id}/pull-requests")
def create_pull_request_form(
    session: SessionDep,
    repo_id: int,
    title: str = Form(...),
    description: str = Form(""),
    base_branch: str = Form(...),
    head_branch: str = Form(...),
    created_by: str = Form("anonymous"),
):
    pull_request = pull_request_service.create_pull_request(
        session,
        PullRequestCreate(
            repository_id=repo_id,
            title=title,
            description=description,
            base_branch=base_branch,
            head_branch=head_branch,
            created_by=created_by or None,
        ),
    )
    return RedirectResponse(url=f"/pull-requests/{pull_request.id}", status_code=303)


@app.get("/pull-requests/{pr_id}", response_class=HTMLResponse)
def pull_request_detail(pr_id: int, request: Request, session: SessionDep) -> HTMLResponse:
    pull_request = pull_request_service.get_pull_request(session, pr_id)
    repository = _repository_to_response(
        repository_service.get_repository(session, pull_request.repository_id)
    )
    diff = get_pull_request_diff(pr_id, session)
    comments = list_comments(pr_id, session)
    statuses = list_statuses(pr_id, session)
    bot_state = _try_get_bot_state(pr_id)
    return templates.TemplateResponse(
        name="pull_request_detail.html",
        request=request,
        context={
            "repository": repository,
            "pull_request": PullRequestResponse.model_validate(pull_request, from_attributes=True),
            "diff": diff,
            "comments": comments,
            "statuses": statuses,
            "bot_state": bot_state,
            "page_title": pull_request.title,
        },
    )


@app.post("/pull-requests/{pr_id}/bot/review")
def trigger_review_form(pr_id: int, session: SessionDep) -> RedirectResponse:
    pull_request_service.get_pull_request(session, pr_id)
    bot_client.trigger_review(pr_id, trigger="manual")
    return RedirectResponse(url=f"/pull-requests/{pr_id}", status_code=303)


@app.post("/pull-requests/{pr_id}/bot/next-batch")
def trigger_next_batch_form(pr_id: int, session: SessionDep) -> RedirectResponse:
    pull_request_service.get_pull_request(session, pr_id)
    bot_client.publish_next_batch(pr_id, reason="manual_next_batch")
    return RedirectResponse(url=f"/pull-requests/{pr_id}", status_code=303)


@app.post("/api/repos", response_model=RepositoryResponse)
def create_repository(
    payload: RepositoryCreate,
    session: SessionDep,
) -> RepositoryResponse:
    return _repository_to_response(repository_service.create_repository(session, payload))


@app.get("/api/repos", response_model=list[RepositoryResponse])
def list_repositories(session: SessionDep) -> list[RepositoryResponse]:
    return [_repository_to_response(item) for item in repository_service.list_repositories(session)]


@app.get("/api/repos/{repo_id}", response_model=RepositoryResponse)
def get_repository(repo_id: int, session: SessionDep) -> RepositoryResponse:
    return _repository_to_response(repository_service.get_repository(session, repo_id))


@app.post("/api/pull-requests", response_model=PullRequestResponse)
def create_pull_request(
    payload: PullRequestCreate,
    session: SessionDep,
):
    return pull_request_service.create_pull_request(session, payload)


@app.get("/api/pull-requests/{pr_id}", response_model=PullRequestResponse)
def get_pull_request(pr_id: int, session: SessionDep):
    return pull_request_service.get_pull_request(session, pr_id)


@app.get("/api/pull-requests", response_model=PullRequestListResponse)
def list_pull_requests(session: SessionDep, repository_id: int | None = None):
    items = [
        PullRequestResponse.model_validate(item, from_attributes=True)
        for item in pull_request_service.list_pull_requests(session, repository_id=repository_id)
    ]
    return PullRequestListResponse(items=items)


@app.get("/api/pull-requests/{pr_id}/diff", response_model=PullRequestDiffResponse)
def get_pull_request_diff(
    pr_id: int,
    session: SessionDep,
    base_sha: Annotated[str | None, Query()] = None,
):
    pull_request = pull_request_service.get_pull_request(session, pr_id)
    repository = repository_service.get_repository(session, pull_request.repository_id)
    files = diff_service.get_changed_files(repository, pull_request, base_sha=base_sha)
    return PullRequestDiffResponse(
        pull_request=PullRequestResponse.model_validate(pull_request, from_attributes=True),
        files=files,
    )


@app.post("/api/pull-requests/{pr_id}/comments", response_model=CommentResponse)
def create_comment(
    pr_id: int,
    payload: CommentCreate,
    session: SessionDep,
):
    pull_request_service.get_pull_request(session, pr_id)
    comment = PullRequestComment(
        pull_request_id=pr_id,
        file_path=payload.file_path,
        line_no=payload.line_no,
        comment_type=payload.comment_type,
        author_type=payload.author_type,
        created_by=payload.created_by,
        body=payload.body,
    )
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return comment


@app.get("/api/pull-requests/{pr_id}/comments", response_model=list[CommentResponse])
def list_comments(pr_id: int, session: SessionDep):
    pull_request_service.get_pull_request(session, pr_id)
    return (
        session.query(PullRequestComment)
        .filter(PullRequestComment.pull_request_id == pr_id)
        .order_by(PullRequestComment.id.asc())
        .all()
    )


@app.post("/api/pull-requests/{pr_id}/statuses", response_model=StatusResponse)
def create_status(
    pr_id: int,
    payload: StatusCreate,
    session: SessionDep,
):
    pull_request_service.get_pull_request(session, pr_id)
    status = PullRequestStatus(
        pull_request_id=pr_id,
        context=payload.context,
        state=payload.state,
        description=payload.description,
        created_by=payload.created_by,
    )
    session.add(status)
    session.commit()
    session.refresh(status)
    return status


@app.get("/api/pull-requests/{pr_id}/statuses", response_model=list[StatusResponse])
def list_statuses(pr_id: int, session: SessionDep):
    pull_request_service.get_pull_request(session, pr_id)
    return (
        session.query(PullRequestStatus)
        .filter(PullRequestStatus.pull_request_id == pr_id)
        .order_by(PullRequestStatus.id.asc())
        .all()
    )


@app.post("/api/pull-requests/{pr_id}/bot/review", response_model=BotReviewResponse)
def trigger_bot_review(
    pr_id: int,
    payload: BotReviewTrigger,
    session: SessionDep,
) -> BotReviewResponse:
    pull_request_service.get_pull_request(session, pr_id)
    return BotReviewResponse(**bot_client.trigger_review(pr_id, trigger=payload.trigger))


@app.post("/api/pull-requests/{pr_id}/bot/next-batch", response_model=BotReviewResponse)
def trigger_bot_next_batch(
    pr_id: int,
    payload: BotNextBatchTrigger,
    session: SessionDep,
) -> BotReviewResponse:
    pull_request_service.get_pull_request(session, pr_id)
    return BotReviewResponse(**bot_client.publish_next_batch(pr_id, reason=payload.reason))


@app.get("/api/pull-requests/{pr_id}/bot/state", response_model=BotStateResponse)
def get_bot_state(pr_id: int, session: SessionDep) -> BotStateResponse:
    pull_request_service.get_pull_request(session, pr_id)
    return BotStateResponse(**bot_client.get_state(pr_id))
