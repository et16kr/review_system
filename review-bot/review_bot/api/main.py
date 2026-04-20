from __future__ import annotations

from contextlib import asynccontextmanager
import re
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy.orm import Session

from review_bot.bot.review_runner import ReviewRunner
from review_bot.contracts import ReviewRequestKey, ReviewRequestMeta
from review_bot.db.session import get_session, init_db
from review_bot.queueing import get_detect_queue, get_publish_queue, get_sync_queue
from review_bot.schemas import (
    PublishRunResponse,
    ReviewAcceptedResponse,
    ReviewRequestStateResponse,
    ReviewRunCreateRequest,
    SyncRunResponse,
    WebhookAcceptedResponse,
)
from review_bot.worker import execute_detect_job, execute_publish_job, execute_sync_job


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Review Bot", version="0.2.0", lifespan=lifespan)
runner = ReviewRunner()
detect_queue = get_detect_queue()
publish_queue = get_publish_queue()
sync_queue = get_sync_queue()
SessionDep = Annotated[Session, Depends(get_session)]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/review/runs", response_model=ReviewAcceptedResponse)
def create_review_run(payload: ReviewRunCreateRequest, session: SessionDep):
    meta = ReviewRequestMeta(
        key=payload.key,
        title=payload.title,
        draft=payload.draft,
        source_branch=payload.source_branch,
        target_branch=payload.target_branch,
        base_sha=payload.base_sha,
        start_sha=payload.start_sha,
        head_sha=payload.head_sha,
    )
    review_run = runner.create_review_run_for_key(
        session,
        payload.key,
        trigger=payload.trigger,
        mode=payload.mode,
        meta=meta,
    )
    review_run_id = review_run.id
    try:
        job = detect_queue.enqueue(execute_detect_job, review_run.id)
        review_run.job_id = job.id
        session.commit()
    except Exception as exc:
        review_run.status = "failed"
        review_run.error_category = "queue"
        review_run.error_message = str(exc)
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ReviewAcceptedResponse(
        accepted=True,
        review_run_id=review_run_id,
        status="queued",
        queue_name=detect_queue.name,
    )


@app.post("/internal/review/runs/{run_id}/publish", response_model=PublishRunResponse)
def publish_review_run(run_id: str):
    try:
        publish_queue.enqueue(execute_publish_job, run_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PublishRunResponse(
        accepted=True,
        review_run_id=run_id,
        queue_name=publish_queue.name,
    )


@app.post("/internal/review/runs/{run_id}/sync", response_model=SyncRunResponse)
def sync_review_run(run_id: str):
    try:
        sync_queue.enqueue(execute_sync_job, run_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return SyncRunResponse(
        accepted=True,
        review_run_id=run_id,
        queue_name=sync_queue.name,
    )


@app.get(
    "/internal/review/requests/{review_system}/{project_ref:path}/{review_request_id}",
    response_model=ReviewRequestStateResponse,
)
def review_request_state(
    review_system: str,
    project_ref: str,
    review_request_id: str,
    session: SessionDep,
):
    state = runner.build_state(
        session,
        key=ReviewRequestKey(
            review_system=review_system,
            project_ref=project_ref,
            review_request_id=review_request_id,
        ),
    )
    return ReviewRequestStateResponse(**state)


@app.post("/webhooks/gitlab/merge-request", response_model=WebhookAcceptedResponse)
async def gitlab_merge_request_webhook(
    request: Request,
    session: SessionDep,
    x_gitlab_event: Annotated[str | None, Header(alias="X-Gitlab-Event")] = None,
    x_gitlab_token: Annotated[str | None, Header(alias="X-Gitlab-Token")] = None,
):
    _verify_gitlab_webhook_secret(x_gitlab_token)

    payload = await request.json()
    if x_gitlab_event == "Note Hook" or payload.get("object_kind") == "note":
        return _handle_gitlab_note_hook(payload, session=session)
    if x_gitlab_event == "Merge Request Hook" or payload.get("object_kind") == "merge_request":
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_merge_request",
            status="ignored",
            ignored_reason="manual_review_requires_bot_mention_comment",
        )
    return WebhookAcceptedResponse(
        accepted=False,
        event="gitlab_merge_request",
        status="ignored",
        ignored_reason=f"unsupported_event_header:{x_gitlab_event or payload.get('object_kind')}",
    )


def _handle_gitlab_note_hook(payload: dict, *, session: Session) -> WebhookAcceptedResponse:
    if payload.get("object_kind") != "note":
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_note",
            status="ignored",
            ignored_reason="object_kind_is_not_note",
        )
    attrs = payload.get("object_attributes") or {}
    if attrs.get("noteable_type") != "MergeRequest":
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_note",
            status="ignored",
            ignored_reason="note_is_not_on_merge_request",
        )
    if bool(attrs.get("system")):
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_note",
            status="ignored",
            ignored_reason="system_note",
        )

    note_body = str(attrs.get("note") or "")
    mention = f"@{runner.settings.bot_author_name}"
    if not _contains_gitlab_mention(note_body, runner.settings.bot_author_name):
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_note",
            status="ignored",
            ignored_reason=f"missing_review_request_mention:{mention}",
        )

    author_username = str((payload.get("user") or {}).get("username") or "")
    if author_username == runner.settings.bot_author_name:
        return WebhookAcceptedResponse(
            accepted=False,
            event="gitlab_note",
            status="ignored",
            ignored_reason="bot_authored_note",
        )

    project_ref = (
        (payload.get("project") or {}).get("path_with_namespace")
        or (payload.get("project") or {}).get("path")
    )
    if not project_ref:
        raise HTTPException(status_code=400, detail="GitLab project path is required.")

    merge_request = payload.get("merge_request") or {}
    review_request_id = merge_request.get("iid")
    if review_request_id is None:
        raise HTTPException(status_code=400, detail="GitLab merge request iid is required.")

    key = ReviewRequestKey(
        review_system="gitlab",
        project_ref=str(project_ref),
        review_request_id=str(review_request_id),
    )
    meta = ReviewRequestMeta(
        key=key,
        title=merge_request.get("title"),
        draft=bool(merge_request.get("work_in_progress") or merge_request.get("draft")),
        source_branch=merge_request.get("source_branch"),
        target_branch=merge_request.get("target_branch"),
        head_sha=((merge_request.get("last_commit") or {}).get("id")),
    )
    review_run = runner.create_review_run_for_key(
        session,
        key,
        trigger="gitlab:note_mention",
        mode="manual",
        meta=meta,
    )
    review_run_id = review_run.id
    try:
        _enqueue_detect_job(session, review_run)
    except HTTPException as exc:
        raise exc
    return WebhookAcceptedResponse(
        accepted=True,
        event="gitlab_note",
        action="mention",
        review_run_id=review_run_id,
        status="queued",
        queue_name=detect_queue.name,
    )


def _enqueue_detect_job(session: Session, review_run: object) -> None:
    try:
        job = detect_queue.enqueue(execute_detect_job, review_run.id)
        review_run.job_id = job.id
        session.commit()
    except Exception as exc:
        review_run.status = "failed"
        review_run.error_category = "queue"
        review_run.error_message = str(exc)
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _contains_gitlab_mention(body: str, username: str) -> bool:
    pattern = re.compile(rf"(?<![\w/-])@{re.escape(username)}\b", re.IGNORECASE)
    return bool(pattern.search(body))


def _verify_gitlab_webhook_secret(provided_token: str | None) -> None:
    settings = runner.settings
    if not settings.gitlab_webhook_secret:
        return
    if provided_token == settings.gitlab_webhook_secret:
        return
    raise HTTPException(status_code=403, detail="GitLab webhook token mismatch.")
