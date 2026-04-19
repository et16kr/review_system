from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.bot.review_runner import ReviewRunner
from app.config import get_settings
from app.db.session import get_session, init_db
from app.queueing import get_queue
from app.schemas import (
    BotStateResponse,
    NextBatchRequest,
    ReviewAcceptedResponse,
    ReviewTriggerRequest,
    WebhookAcceptedResponse,
)
from app.worker import execute_review_job, publish_next_batch_job


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Review Bot", version="0.1.0", lifespan=lifespan)
runner = ReviewRunner()
queue = get_queue()
settings = get_settings()
SessionDep = Annotated[Session, Depends(get_session)]
SUPPORTED_GITLAB_MR_ACTIONS = {"open", "update", "reopen"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/review/pr-opened", response_model=ReviewAcceptedResponse)
def review_pr_opened(
    payload: ReviewTriggerRequest,
    session: SessionDep,
):
    review_run = runner.create_review_run(session, payload.pr_id, payload.trigger or "pr_opened")
    try:
        job = queue.enqueue(execute_review_job, review_run.id)
        review_run.job_id = job.id
        session.commit()
    except Exception as exc:
        review_run.status = "failed"
        review_run.error_message = str(exc)
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReviewAcceptedResponse(
        accepted=True,
        review_run_id=review_run.id,
        status="queued",
        queue_name=queue.name,
    )


@app.post("/internal/review/pr-updated", response_model=ReviewAcceptedResponse)
def review_pr_updated(
    payload: ReviewTriggerRequest,
    session: SessionDep,
):
    review_run = runner.create_review_run(session, payload.pr_id, payload.trigger or "pr_updated")
    try:
        job = queue.enqueue(execute_review_job, review_run.id)
        review_run.job_id = job.id
        session.commit()
    except Exception as exc:
        review_run.status = "failed"
        review_run.error_message = str(exc)
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReviewAcceptedResponse(
        accepted=True,
        review_run_id=review_run.id,
        status="queued",
        queue_name=queue.name,
    )


@app.post("/internal/review/next-batch", response_model=ReviewAcceptedResponse)
def publish_next_batch(
    payload: NextBatchRequest,
    session: SessionDep,
):
    state = runner.build_state(session, payload.pr_id)
    if not state["last_review_run_id"]:
        raise HTTPException(status_code=400, detail="No previous review run exists.")
    try:
        queue.enqueue(publish_next_batch_job, payload.pr_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReviewAcceptedResponse(
        accepted=True,
        review_run_id=state["last_review_run_id"] or 0,
        status="queued",
        queue_name=queue.name,
    )


@app.get("/internal/review/state/{pr_id}", response_model=BotStateResponse)
def review_state(pr_id: int, session: SessionDep):
    return BotStateResponse(**runner.build_state(session, pr_id))


@app.post("/webhooks/gitlab/merge-request", response_model=WebhookAcceptedResponse)
async def gitlab_merge_request_webhook(
    request: Request,
    session: SessionDep,
    x_gitlab_event: Annotated[str | None, Header(alias="X-Gitlab-Event")] = None,
    x_gitlab_token: Annotated[str | None, Header(alias="X-Gitlab-Token")] = None,
):
    _verify_gitlab_webhook_secret(x_gitlab_token)

    payload = await request.json()
    if x_gitlab_event and x_gitlab_event != "Merge Request Hook":
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_merge_request",
            status="ignored",
            ignored_reason=f"unsupported_event_header:{x_gitlab_event}",
        )

    if payload.get("object_kind") != "merge_request":
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_merge_request",
            status="ignored",
            ignored_reason="object_kind_is_not_merge_request",
        )

    attrs = payload.get("object_attributes") or {}
    action = attrs.get("action")
    review_request_id = attrs.get("iid")
    if review_request_id is None:
        raise HTTPException(status_code=400, detail="GitLab merge request iid is required.")

    if action not in SUPPORTED_GITLAB_MR_ACTIONS:
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_merge_request",
            action=action,
            status="ignored",
            ignored_reason="unsupported_merge_request_action",
        )

    review_run = runner.create_review_run(
        session,
        int(review_request_id),
        f"gitlab:{action}",
    )
    try:
        job = queue.enqueue(execute_review_job, review_run.id)
        review_run.job_id = job.id
        session.commit()
    except Exception as exc:
        review_run.status = "failed"
        review_run.error_message = str(exc)
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return WebhookAcceptedResponse(
        accepted=True,
        event="gitlab_merge_request",
        action=action,
        review_run_id=review_run.id,
        status="queued",
        queue_name=queue.name,
    )


def _verify_gitlab_webhook_secret(provided_token: str | None) -> None:
    if not settings.gitlab_webhook_secret:
        return
    if provided_token == settings.gitlab_webhook_secret:
        return
    raise HTTPException(status_code=403, detail="GitLab webhook token mismatch.")
