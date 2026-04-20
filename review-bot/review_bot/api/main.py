from __future__ import annotations

import time
from collections import deque
from contextlib import asynccontextmanager
import re
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import func
from sqlalchemy.orm import Session

from review_bot.bot.review_runner import ReviewRunner
from review_bot.contracts import ReviewRequestKey, ReviewRequestMeta
from review_bot.db.session import get_session, init_db
from review_bot.metrics import redis_queue_depth
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

_WEBHOOK_RATE_LIMIT = 100   # requests per window
_WEBHOOK_RATE_WINDOW = 60   # seconds
# NOTE: 프로세스 메모리 기반이므로 멀티 인스턴스/로드밸런서 환경에서는
# 인스턴스별로 독립 동작(분산 제어 아님). 단일 GitLab IP → 429 위험 있음.
# 운영형 전환 시 Redis 기반 슬라이딩 윈도우로 교체 필요.
_rate_limit_buckets: dict[str, deque[float]] = {}


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
    try:
        detect_queue.connection.ping()
        redis_status = "ok"
        for q_name, q_obj in [
            ("detect", detect_queue),
            ("publish", publish_queue),
            ("sync", sync_queue),
        ]:
            try:
                redis_queue_depth.labels(queue=q_name).set(len(q_obj))
            except Exception:
                pass
    except Exception:
        redis_status = "error"
    overall = "ok" if redis_status == "ok" else "degraded"
    return {"status": overall, "redis": redis_status}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    _enqueue_detect_job(session, review_run)
    return ReviewAcceptedResponse(
        accepted=True,
        review_run_id=review_run_id,
        status=review_run.status,
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
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many webhook requests.")
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
        status=review_run.status,
        queue_name=detect_queue.name,
    )


def _enqueue_detect_job(session: Session, review_run: object) -> bool:
    try:
        if getattr(review_run, "job_id", None):
            session.commit()
            return False
        job = detect_queue.enqueue(execute_detect_job, review_run.id)
        review_run.job_id = job.id
        session.commit()
        return True
    except Exception as exc:
        review_run.status = "failed"
        review_run.error_category = "queue"
        review_run.error_message = str(exc)
        session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _contains_gitlab_mention(body: str, username: str) -> bool:
    pattern = re.compile(rf"(?<![\w/-])@{re.escape(username)}\b", re.IGNORECASE)
    return bool(pattern.search(body))


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    bucket = _rate_limit_buckets.setdefault(client_ip, deque())
    while bucket and bucket[0] < now - _WEBHOOK_RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= _WEBHOOK_RATE_LIMIT:
        return False
    bucket.append(now)
    return True


@app.get("/internal/analytics/rule-effectiveness")
def rule_effectiveness(session: SessionDep):
    from sqlalchemy import case as sa_case
    from review_bot.db.models import FindingDecision as FD, ThreadSyncState as TSS

    # human-resolve fingerprint 집합 (개발자가 직접 resolve한 것만)
    human_fps: set[str] = {
        fp
        for (fp,) in session.query(TSS.finding_fingerprint).filter(
            TSS.sync_status == "resolved",
            TSS.resolution_reason == "remote_resolved",
        ).all()
    }

    rows = (
        session.query(
            FD.rule_no,
            FD.source_family,
            func.count(FD.id).label("total"),
            func.sum(sa_case((FD.state == "published", 1), else_=0)).label("published"),
            func.sum(sa_case((FD.state == "resolved", 1), else_=0)).label("resolved"),
            func.sum(sa_case((FD.state == "suppressed", 1), else_=0)).label("suppressed"),
        )
        .group_by(FD.rule_no, FD.source_family)
        .order_by(func.count(FD.id).desc())
        .limit(50)
        .all()
    )

    # human-resolve 건수를 규칙별로 집계
    human_resolved_by_rule: dict[str, int] = {}
    if human_fps:
        for rule_no, cnt in (
            session.query(FD.rule_no, func.count(FD.id))
            .filter(FD.state == "resolved", FD.fingerprint.in_(human_fps))
            .group_by(FD.rule_no)
            .all()
        ):
            human_resolved_by_rule[rule_no] = cnt

    results = []
    for rule_no, family, total, published, resolved, suppressed in rows:
        pub = int(published or 0)
        res = int(resolved or 0)
        sup = int(suppressed or 0)
        human_res = human_resolved_by_rule.get(rule_no, 0)
        # surfaced = 현재 게시중 + 해소됨 (auto-resolve 포함)
        surfaced = pub + res
        # human_resolve_rate = 개발자가 실제로 수정한 비율 (신뢰도 있는 지표)
        human_resolve_rate = round(human_res / surfaced, 3) if surfaced > 0 else 0.0
        resolve_rate = round(res / surfaced, 3) if surfaced > 0 else 0.0
        results.append(
            {
                "rule_no": rule_no,
                "source_family": family,
                "total": int(total),
                "published": pub,
                "resolved": res,
                "human_resolved": human_res,
                "suppressed": sup,
                "resolve_rate": resolve_rate,
                "human_resolve_rate": human_resolve_rate,
            }
        )
    return {"rules": results, "total_rules": len(results)}


def _verify_gitlab_webhook_secret(provided_token: str | None) -> None:
    settings = runner.settings
    if not settings.gitlab_webhook_secret:
        return
    if provided_token == settings.gitlab_webhook_secret:
        return
    raise HTTPException(status_code=403, detail="GitLab webhook token mismatch.")
