from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from review_bot.clients.engine_client import EngineClient
from review_bot.config import get_settings
from review_bot.contracts import (
    AnchorPayload,
    CheckPublishRequest,
    CommentUpsertRequest,
    DiffPayload,
    FeedbackPage,
    ReviewRequestKey,
    ReviewRequestMeta,
)
from review_bot.db.models import (
    FeedbackEvent,
    FindingDecision,
    FindingEvidence,
    PublicationState,
    DeadLetterRecord,
    ReviewRequest,
    ReviewRun,
    ThreadSyncState,
)
from review_bot.errors import ReviewBotError
from review_bot.policy import ReviewPolicy, load_review_policy
from review_bot.providers.change_analysis import (
    classify_issue,
    extract_changed_excerpt,
    requires_direct_signal,
    select_candidate_line,
)
from review_bot.providers.base import FindingDraft
from review_bot.providers.factory import build_review_comment_provider
from review_bot.review_systems.factory import build_review_system_adapter

CPP_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
HUNK_RE = re.compile(r"@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")
MAX_LINES_PER_REVIEW_UNIT = 80
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChangedPatchLine:
    marker: str
    text: str
    old_line_no: int | None = None
    new_line_no: int | None = None


@dataclass(frozen=True)
class ReviewUnit:
    patch: str
    change_snippet: str
    default_line_no: int | None
    candidate_line_nos: tuple[int, ...]
    changed_lines: tuple[ChangedPatchLine, ...]


@dataclass(frozen=True)
class PublicationCandidate:
    decision: FindingDecision
    draft: FindingDraft
    body: str
    body_hash: str
    canonical_body_hash: str
    existing_thread: ThreadSyncState | None
    publication_key: tuple[str, int | None, str]
    priority_group: int
    reminder_candidate: bool = False


@dataclass(frozen=True)
class FeedbackSignal:
    resolved_count: int = 0
    unresolved_count: int = 0
    human_reply_count: int = 0
    ignore_requested: bool = False
    allow_requested: bool = False


class ReviewRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.review_system = build_review_system_adapter()
        self.platform_client = self.review_system
        self.engine_client = EngineClient(
            self.settings.engine_base_url,
            timeout_seconds=self.settings.engine_timeout_seconds,
            max_retries=self.settings.engine_max_retries,
            retry_backoff_seconds=self.settings.engine_retry_backoff_seconds,
        )
        self.provider = build_review_comment_provider()
        self.policy: ReviewPolicy = load_review_policy(self.settings.policy_path)

    # Compatibility path used by older tests and the local harness
    def run_review(self, session: Session, pr_id: int, trigger: str) -> ReviewRun:
        key = self._legacy_key(pr_id)
        review_run = self.create_review_run_for_key(
            session,
            key,
            trigger=trigger,
            mode="manual",
        )
        return self.execute_review_run(session, review_run.id)

    def create_review_run(self, session: Session, pr_id: int, trigger: str) -> ReviewRun:
        key = self._legacy_key(pr_id)
        return self.create_review_run_for_key(session, key, trigger=trigger, mode="manual")

    def create_review_run_for_key(
        self,
        session: Session,
        key: ReviewRequestKey,
        *,
        trigger: str,
        mode: str,
        meta: ReviewRequestMeta | None = None,
    ) -> ReviewRun:
        review_request = self._ensure_review_request(session, key, meta=meta)
        review_run = ReviewRun(
            review_request_pk=review_request.id,
            review_system=key.review_system,
            project_ref=key.project_ref,
            review_request_id=key.review_request_id,
            trigger=trigger,
            mode=mode,
            status="queued",
            base_sha=meta.base_sha if meta else review_request.latest_base_sha,
            start_sha=meta.start_sha if meta else review_request.latest_start_sha,
            head_sha=meta.head_sha if meta else review_request.latest_head_sha,
        )
        session.add(review_run)
        session.commit()
        session.refresh(review_run)
        return review_run

    def execute_review_run(self, session: Session, review_run_id: str) -> ReviewRun:
        self.execute_detect_phase(session, review_run_id)
        self.execute_publish_phase(session, review_run_id)
        self.execute_sync_phase(session, review_run_id)
        refreshed = session.get(ReviewRun, review_run_id)
        if refreshed is None:
            raise HTTPException(status_code=404, detail=f"Review run not found: {review_run_id}")
        return refreshed

    def execute_detect_phase(self, session: Session, review_run_id: str) -> None:
        review_run = self._get_review_run(session, review_run_id)
        key = self._key_from_run(review_run)
        review_request = self._get_review_request(session, review_run.review_request_pk)
        adapter = self._get_adapter()
        self._log_run_event(
            "detect_started",
            review_run,
            head_sha=review_run.head_sha or review_request.latest_head_sha,
        )

        review_run.status = "running"
        review_run.started_at = datetime.now(UTC)
        session.commit()
        self._safe_publish_check(
            adapter,
            key,
            CheckPublishRequest(
                head_sha=review_run.head_sha or review_request.latest_head_sha,
                state="running",
                description="자동 리뷰 실행 중",
            ),
        )

        try:
            meta = adapter.fetch_review_request_meta(key)
            diff_payload = adapter.fetch_diff(key, mode=review_run.mode, base_sha=review_run.base_sha)
            current_threads = {thread.thread_ref: thread for thread in adapter.list_threads(key)}
            self._apply_request_meta(review_request, meta, diff_payload)
            self._reconcile_thread_snapshots(
                session,
                review_request_pk=review_request.id,
                threads=current_threads,
                head_sha=diff_payload.pull_request.get("head_sha") or meta.head_sha,
            )
            self._ingest_feedback(
                session,
                review_request=review_request,
                feedback_page=adapter.collect_feedback(key),
            )
            review_run.base_sha = meta.base_sha or review_run.base_sha
            review_run.start_sha = meta.start_sha or review_run.start_sha
            review_run.head_sha = diff_payload.pull_request.get("head_sha") or meta.head_sha

            seen_human_keys: set[str] = set()
            for file_item in diff_payload.files:
                if not self._is_cpp_path(file_item.path):
                    continue
                for review_unit in self._iter_review_units(file_item.patch):
                    review = self.engine_client.review_diff(review_unit.patch, top_k=8)
                    detected_patterns = [str(item) for item in review.get("detected_patterns", [])]
                    for result in review.get("results", [])[:3]:
                        evidence = FindingEvidence(
                            review_run_id=review_run.id,
                            review_request_pk=review_request.id,
                            file_path=file_item.path,
                            patch_digest=self._sha1(review_unit.patch),
                            hunk_header=review_unit.patch.splitlines()[0] if review_unit.patch else None,
                            candidate_line_nos=list(review_unit.candidate_line_nos),
                            matched_patterns=detected_patterns,
                            change_snippet=review_unit.change_snippet,
                            raw_engine_payload=dict(result),
                        )
                        session.add(evidence)
                        session.flush()

                        decision = self._build_decision(
                            session=session,
                            review_run=review_run,
                            review_request=review_request,
                            evidence=evidence,
                            review_unit=review_unit,
                            result=result,
                            seen_human_keys=seen_human_keys,
                        )
                        if decision is not None:
                            session.add(decision)

            session.commit()
            self._log_run_event(
                "detect_completed",
                review_run,
                head_sha=review_run.head_sha,
            )
        except Exception as exc:
            error_category, retryable = self._classify_error(exc)
            review_run.status = "failed"
            review_run.error_category = error_category
            review_run.error_message = str(exc)
            review_run.completed_at = datetime.now(UTC)
            self._record_dead_letter(
                session,
                review_run=review_run,
                stage="detect",
                error_category=error_category,
                error_message=str(exc),
                replayable=retryable,
                payload={"head_sha": review_run.head_sha},
            )
            session.commit()
            self._log_run_event(
                "detect_failed",
                review_run,
                head_sha=review_run.head_sha,
                error_category=error_category,
                error_message=str(exc),
                retryable=retryable,
            )
            self._safe_publish_check(
                adapter,
                key,
                CheckPublishRequest(
                    head_sha=review_run.head_sha,
                    state="failed",
                    description=f"{error_category}: {str(exc)[:220]}",
                ),
            )
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    def execute_publish_phase(self, session: Session, review_run_id: str) -> None:
        review_run = self._get_review_run(session, review_run_id)
        review_request = self._get_review_request(session, review_run.review_request_pk)
        key = self._key_from_run(review_run)
        adapter = self._get_adapter()
        self._log_run_event("publish_started", review_run, head_sha=review_run.head_sha)
        try:
            eligible = (
                session.query(FindingDecision)
                .filter(
                    FindingDecision.review_run_id == review_run.id,
                    FindingDecision.state == "eligible",
                )
                .order_by(FindingDecision.score_final.desc(), FindingDecision.created_at.asc())
                .all()
            )
            candidates = self._prepare_publication_candidates(
                session=session,
                review_run=review_run,
                review_request=review_request,
                decisions=eligible,
            )
            selected = self._select_batch_candidates(candidates)
            current_batch = (
                session.query(func.max(PublicationState.batch_no))
                .filter(PublicationState.review_request_pk == review_request.id)
                .scalar()
            ) or 0
            batch_no = int(current_batch) + 1
            publication_failures = 0
            seen_publication_keys: set[tuple[str, int | None, str]] = set()
            noop_existing_candidates = [
                candidate for candidate in candidates if candidate.priority_group == 3
            ]

            self._log_run_event(
                "publish_candidates_built",
                review_run,
                eligible_count=len(eligible),
                selected_count=len(selected),
                noop_existing_count=len(noop_existing_candidates),
            )

            for candidate in noop_existing_candidates:
                decision = candidate.decision
                existing_thread = candidate.existing_thread
                if existing_thread is None:
                    continue
                publication = PublicationState(
                    finding_decision_id=decision.id,
                    review_request_pk=review_request.id,
                    review_system=review_run.review_system,
                    project_ref=review_run.project_ref,
                    review_request_id=review_run.review_request_id,
                    adapter_comment_ref=existing_thread.adapter_comment_ref,
                    adapter_thread_ref=existing_thread.adapter_thread_ref,
                    body_hash=candidate.body_hash,
                    batch_no=batch_no,
                    publish_state="skipped",
                    published_at=datetime.now(UTC),
                )
                session.add(publication)
                decision.state = "published"
                decision.publication_error = None

            for candidate in selected:
                decision = candidate.decision
                publication_key = candidate.publication_key
                if publication_key in seen_publication_keys:
                    decision.state = "suppressed"
                    decision.suppression_reason = "publish_batch_duplicate"
                    continue
                seen_publication_keys.add(publication_key)

                existing_thread = candidate.existing_thread
                try:
                    if (
                        existing_thread
                        and existing_thread.sync_status == "open"
                        and existing_thread.body_hash == candidate.body_hash
                    ):
                        publication = PublicationState(
                            finding_decision_id=decision.id,
                            review_request_pk=review_request.id,
                            review_system=review_run.review_system,
                            project_ref=review_run.project_ref,
                            review_request_id=review_run.review_request_id,
                            adapter_comment_ref=existing_thread.adapter_comment_ref,
                            adapter_thread_ref=existing_thread.adapter_thread_ref,
                            body_hash=candidate.body_hash,
                            batch_no=batch_no,
                            publish_state="skipped",
                            published_at=datetime.now(UTC),
                        )
                        session.add(publication)
                        decision.state = "published"
                        continue

                    request = CommentUpsertRequest(
                        fingerprint=decision.fingerprint,
                        body=candidate.body,
                        anchor=AnchorPayload.model_validate(decision.anchor_payload),
                        existing_thread_ref=(
                            existing_thread.adapter_thread_ref
                            if existing_thread and existing_thread.anchor_signature == decision.anchor_signature
                            else None
                        ),
                        existing_comment_ref=(
                            existing_thread.adapter_comment_ref
                            if existing_thread and existing_thread.anchor_signature == decision.anchor_signature
                            else None
                        ),
                        reopen_if_resolved=bool(existing_thread and existing_thread.sync_status == "resolved"),
                    )
                    result = adapter.upsert_comment(key, request)
                    publication = PublicationState(
                        finding_decision_id=decision.id,
                        review_request_pk=review_request.id,
                        review_system=review_run.review_system,
                        project_ref=review_run.project_ref,
                        review_request_id=review_run.review_request_id,
                        adapter_comment_ref=result.comment_ref,
                        adapter_thread_ref=result.thread_ref,
                        body_hash=candidate.body_hash,
                        batch_no=batch_no,
                        publish_state=result.action,
                        published_at=datetime.now(UTC),
                    )
                    session.add(publication)
                    decision.state = "published"
                    decision.publication_error = None

                    if existing_thread and existing_thread.anchor_signature != decision.anchor_signature:
                        existing_thread.sync_status = "stale"
                        existing_thread.resolution_reason = "anchor_changed"

                    thread_state = existing_thread
                    if thread_state is None or thread_state.anchor_signature != decision.anchor_signature:
                        thread_state = ThreadSyncState(
                            review_request_pk=review_request.id,
                            review_system=review_run.review_system,
                            project_ref=review_run.project_ref,
                            review_request_id=review_run.review_request_id,
                            finding_decision_id=decision.id,
                            finding_fingerprint=decision.fingerprint,
                            anchor_signature=decision.anchor_signature,
                            body_hash=candidate.body_hash,
                            adapter_thread_ref=result.thread_ref or "",
                            adapter_comment_ref=result.comment_ref,
                            sync_status="open",
                            last_seen_head_sha=review_run.head_sha,
                            last_synced_at=datetime.now(UTC),
                        )
                        session.add(thread_state)
                    else:
                        thread_state.finding_decision_id = decision.id
                        thread_state.body_hash = candidate.body_hash
                        thread_state.adapter_comment_ref = result.comment_ref
                        thread_state.sync_status = "open"
                        thread_state.resolution_reason = None
                        thread_state.last_seen_head_sha = review_run.head_sha
                        thread_state.last_synced_at = datetime.now(UTC)
                except Exception as exc:
                    error_category, retryable = self._classify_error(exc)
                    if self._should_suppress_inline_anchor_failure(
                        error_category=error_category,
                        retryable=retryable,
                        error_message=str(exc),
                    ):
                        decision.state = "suppressed"
                        decision.suppression_reason = "inline_anchor_unavailable"
                        decision.publication_error = str(exc)
                        session.add(
                            PublicationState(
                                finding_decision_id=decision.id,
                                review_request_pk=review_request.id,
                                review_system=review_run.review_system,
                                project_ref=review_run.project_ref,
                                review_request_id=review_run.review_request_id,
                                body_hash=candidate.body_hash,
                                batch_no=batch_no,
                                publish_state="suppressed",
                                error_category=error_category,
                                error_message=str(exc),
                                published_at=datetime.now(UTC),
                            )
                        )
                        self._log_run_event(
                            "publish_candidate_suppressed_inline_anchor",
                            review_run,
                            head_sha=review_run.head_sha,
                            error_category=error_category,
                            error_message=str(exc),
                            fingerprint=decision.fingerprint,
                            file_path=decision.file_path,
                            line_no=decision.line_no,
                        )
                        continue
                    decision.state = "failed_publication"
                    decision.publication_error = str(exc)
                    publication_failures += 1
                    session.add(
                        PublicationState(
                            finding_decision_id=decision.id,
                            review_request_pk=review_request.id,
                            review_system=review_run.review_system,
                            project_ref=review_run.project_ref,
                            review_request_id=review_run.review_request_id,
                            body_hash=candidate.body_hash,
                            batch_no=batch_no,
                            publish_state="failed",
                            error_category=error_category,
                            error_message=str(exc),
                            published_at=datetime.now(UTC),
                        )
                    )
                    self._record_dead_letter(
                        session,
                        review_run=review_run,
                        stage="publish",
                        error_category=error_category,
                        error_message=str(exc),
                        replayable=retryable,
                        payload={
                            "fingerprint": decision.fingerprint,
                            "file_path": decision.file_path,
                            "line_no": decision.line_no,
                        },
                    )
                    self._log_run_event(
                        "publish_candidate_failed",
                        review_run,
                        head_sha=review_run.head_sha,
                        error_category=error_category,
                        error_message=str(exc),
                        retryable=retryable,
                        fingerprint=decision.fingerprint,
                        file_path=decision.file_path,
                        line_no=decision.line_no,
                    )
            session.commit()
            self._safe_publish_check(
                adapter,
                key,
                CheckPublishRequest(
                    head_sha=review_run.head_sha,
                    state="partial" if publication_failures else "success",
                    description=(
                        f"자동 리뷰 게시 완료: {len(selected)}개 finding 처리"
                    ),
                ),
            )
            self._log_run_event(
                "publish_completed",
                review_run,
                head_sha=review_run.head_sha,
                selected_count=len(selected),
                publication_failures=publication_failures,
            )
        except Exception as exc:
            error_category, retryable = self._classify_error(exc)
            review_run.status = "failed"
            review_run.error_category = error_category
            review_run.error_message = str(exc)
            review_run.completed_at = datetime.now(UTC)
            self._record_dead_letter(
                session,
                review_run=review_run,
                stage="publish",
                error_category=error_category,
                error_message=str(exc),
                replayable=retryable,
                payload={"head_sha": review_run.head_sha},
            )
            session.commit()
            self._log_run_event(
                "publish_failed",
                review_run,
                head_sha=review_run.head_sha,
                error_category=error_category,
                error_message=str(exc),
                retryable=retryable,
            )
            self._safe_publish_check(
                adapter,
                key,
                CheckPublishRequest(
                    head_sha=review_run.head_sha,
                    state="failed",
                    description=f"{error_category}: {str(exc)[:220]}",
                ),
            )
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    def execute_sync_phase(self, session: Session, review_run_id: str) -> None:
        review_run = self._get_review_run(session, review_run_id)
        review_request = self._get_review_request(session, review_run.review_request_pk)
        key = self._key_from_run(review_run)
        adapter = self._get_adapter()
        self._log_run_event("sync_started", review_run, head_sha=review_run.head_sha)
        try:
            threads = {thread.thread_ref: thread for thread in adapter.list_threads(key)}
            self._reconcile_thread_snapshots(
                session,
                review_request_pk=review_request.id,
                threads=threads,
                head_sha=review_run.head_sha,
            )
            current_fingerprints = {
                fingerprint
                for (fingerprint,) in (
                    session.query(FindingDecision.fingerprint)
                    .filter(
                        FindingDecision.review_run_id == review_run.id,
                        FindingDecision.state.in_(["eligible", "published"]),
                    )
                    .all()
                )
            }
            current_file_paths = {
                file_path
                for (file_path,) in (
                    session.query(FindingEvidence.file_path)
                    .filter(FindingEvidence.review_run_id == review_run.id)
                    .distinct()
                    .all()
                )
            }

            open_thread_states = (
                session.query(ThreadSyncState)
                .filter(
                    ThreadSyncState.review_request_pk == review_request.id,
                    ThreadSyncState.sync_status == "open",
                )
                .all()
            )
            for thread_state in open_thread_states:
                snapshot = threads.get(thread_state.adapter_thread_ref)
                if snapshot is not None:
                    if snapshot.resolved:
                        thread_state.sync_status = "resolved"
                        self._mark_fingerprint_resolved(
                            session, review_request.id, thread_state.finding_fingerprint
                        )
                        continue
                    thread_state.last_synced_at = datetime.now(UTC)
                    thread_state.last_seen_head_sha = review_run.head_sha
                if thread_state.finding_fingerprint not in current_fingerprints:
                    if review_run.mode == "incremental" and not self._thread_targets_current_files(
                        session,
                        thread_state=thread_state,
                        current_file_paths=current_file_paths,
                    ):
                        continue
                    try:
                        adapter.resolve_thread(
                            key,
                            thread_state.adapter_thread_ref,
                            reason="no_longer_eligible",
                        )
                        thread_state.sync_status = "resolved"
                        thread_state.resolution_reason = "no_longer_eligible"
                        self._mark_fingerprint_resolved(
                            session, review_request.id, thread_state.finding_fingerprint
                        )
                    except Exception as exc:
                        error_category, retryable = self._classify_error(exc)
                        thread_state.sync_status = "stale"
                        thread_state.resolution_reason = "resolve_failed"
                        self._record_dead_letter(
                            session,
                            review_run=review_run,
                            stage="sync",
                            error_category=error_category,
                            error_message=str(exc),
                            replayable=retryable,
                            payload={
                                "thread_ref": thread_state.adapter_thread_ref,
                                "fingerprint": thread_state.finding_fingerprint,
                            },
                        )
                        self._log_run_event(
                            "sync_thread_resolve_failed",
                            review_run,
                            head_sha=review_run.head_sha,
                            error_category=error_category,
                            error_message=str(exc),
                            retryable=retryable,
                            thread_ref=thread_state.adapter_thread_ref,
                        )

            self._ingest_feedback(
                session,
                review_request=review_request,
                feedback_page=adapter.collect_feedback(key),
            )

            failed_publication_count = (
                session.query(func.count(FindingDecision.id))
                .filter(
                    FindingDecision.review_run_id == review_run.id,
                    FindingDecision.state == "failed_publication",
                )
                .scalar()
            ) or 0
            review_run.status = "partial" if failed_publication_count else "success"
            review_run.completed_at = datetime.now(UTC)
            session.commit()
            self._log_run_event(
                "sync_completed",
                review_run,
                head_sha=review_run.head_sha,
                failed_publication_count=failed_publication_count,
                open_thread_count=len(
                    [
                        thread_state
                        for thread_state in open_thread_states
                        if thread_state.sync_status == "open"
                    ]
                ),
            )
        except Exception as exc:
            error_category, retryable = self._classify_error(exc)
            review_run.status = "failed"
            review_run.error_category = error_category
            review_run.error_message = str(exc)
            review_run.completed_at = datetime.now(UTC)
            self._record_dead_letter(
                session,
                review_run=review_run,
                stage="sync",
                error_category=error_category,
                error_message=str(exc),
                replayable=retryable,
                payload={"head_sha": review_run.head_sha},
            )
            session.commit()
            self._log_run_event(
                "sync_failed",
                review_run,
                head_sha=review_run.head_sha,
                error_category=error_category,
                error_message=str(exc),
                retryable=retryable,
            )
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Compatibility helpers for older tests
    def publish_next_batch(
        self, session: Session, pr_id: int, review_run_id: str | None = None
    ) -> tuple[int, int]:
        key = self._legacy_key(pr_id)
        review_request = self._find_review_request(session, key)
        if review_request is None:
            raise HTTPException(status_code=400, detail="No previous review run exists for this pull request.")
        if review_run_id is None:
            run = (
                session.query(ReviewRun)
                .filter(ReviewRun.review_request_pk == review_request.id)
                .order_by(ReviewRun.created_at.desc())
                .first()
            )
            if run is None:
                raise HTTPException(status_code=400, detail="No previous review run exists for this pull request.")
            review_run_id = run.id
        before = self._published_count(session, review_request.id)
        self.execute_publish_phase(session, review_run_id)
        after = self._published_count(session, review_request.id)
        failed = (
            session.query(func.count(FindingDecision.id))
            .filter(
                FindingDecision.review_run_id == review_run_id,
                FindingDecision.state == "failed_publication",
            )
            .scalar()
        ) or 0
        return int(after - before), int(failed)

    def build_state(
        self,
        session: Session,
        pr_id: int | None = None,
        *,
        key: ReviewRequestKey | None = None,
    ) -> dict[str, int | str | None | ReviewRequestKey]:
        target_key = key or self._legacy_key(int(pr_id or 0))
        review_request = self._find_review_request(session, target_key)
        if review_request is None:
            return {
                "key": target_key,
                "pr_id": int(target_key.review_request_id) if target_key.review_request_id.isdigit() else None,
                "last_review_run_id": None,
                "last_head_sha": None,
                "last_status": None,
                "published_batch_count": 0,
                "open_finding_count": 0,
                "resolved_finding_count": 0,
                "failed_publication_count": 0,
                "next_batch_size": self.settings.batch_size,
                "open_thread_count": 0,
                "feedback_event_count": 0,
                "dead_letter_count": 0,
            }
        last_run = (
            session.query(ReviewRun)
            .filter(ReviewRun.review_request_pk == review_request.id)
            .order_by(ReviewRun.created_at.desc())
            .first()
        )
        published_batch_count = (
            session.query(func.max(PublicationState.batch_no))
            .filter(PublicationState.review_request_pk == review_request.id)
            .scalar()
        ) or 0
        open_finding_count = (
            session.query(func.count(FindingDecision.id))
            .filter(
                FindingDecision.review_request_pk == review_request.id,
                FindingDecision.state.in_(["eligible", "published", "failed_publication"]),
            )
            .scalar()
        ) or 0
        resolved_finding_count = (
            session.query(func.count(FindingDecision.id))
            .filter(
                FindingDecision.review_request_pk == review_request.id,
                FindingDecision.state == "resolved",
            )
            .scalar()
        ) or 0
        failed_publication_count = (
            session.query(func.count(FindingDecision.id))
            .filter(
                FindingDecision.review_request_pk == review_request.id,
                FindingDecision.state == "failed_publication",
            )
            .scalar()
        ) or 0
        open_thread_count = (
            session.query(func.count(ThreadSyncState.id))
            .filter(
                ThreadSyncState.review_request_pk == review_request.id,
                ThreadSyncState.sync_status == "open",
            )
            .scalar()
        ) or 0
        feedback_event_count = (
            session.query(func.count(FeedbackEvent.id))
            .filter(FeedbackEvent.review_request_pk == review_request.id)
            .scalar()
        ) or 0
        dead_letter_count = (
            session.query(func.count(DeadLetterRecord.id))
            .filter(DeadLetterRecord.review_request_pk == review_request.id)
            .scalar()
        ) or 0
        return {
            "key": target_key,
            "pr_id": int(target_key.review_request_id) if target_key.review_request_id.isdigit() else None,
            "last_review_run_id": last_run.id if last_run else None,
            "last_head_sha": last_run.head_sha if last_run else None,
            "last_status": last_run.status if last_run else None,
            "published_batch_count": int(published_batch_count),
            "open_finding_count": int(open_finding_count),
            "resolved_finding_count": int(resolved_finding_count),
            "failed_publication_count": int(failed_publication_count),
            "next_batch_size": self.settings.batch_size,
            "open_thread_count": int(open_thread_count),
            "feedback_event_count": int(feedback_event_count),
            "dead_letter_count": int(dead_letter_count),
        }

    def _build_decision(
        self,
        *,
        session: Session,
        review_run: ReviewRun,
        review_request: ReviewRequest,
        evidence: FindingEvidence,
        review_unit: ReviewUnit,
        result: dict[str, object],
        seen_human_keys: set[str],
    ) -> FindingDecision | None:
        score_raw = float(result.get("score", 0.0))
        reviewability = str(result.get("reviewability") or "auto_review")
        issue = classify_issue(
            extract_changed_excerpt(review_unit.change_snippet),
            result.get("category"),
            str(result.get("title") or ""),
            str(result.get("summary") or ""),
        )
        target_line_no = self._resolve_target_line_no(
            requested_line_no=None,
            review_unit=review_unit,
            result=result,
        )
        requires_precise = self._requires_precise_anchor(review_unit=review_unit, result=result)
        human_key = self._human_key(
            file_path=evidence.file_path,
            line_no=target_line_no,
            title=str(result.get("title") or ""),
            summary=str(result.get("summary") or ""),
        )
        if human_key in seen_human_keys:
            return None
        seen_human_keys.add(human_key)

        issue_signature = self._issue_signature(result, review_unit)
        anchor_signature = self._anchor_signature(
            file_path=evidence.file_path,
            line_no=target_line_no,
            hunk_header=evidence.hunk_header,
        )
        fingerprint = self._fingerprint(
            key=self._key_from_run(review_run),
            file_path=evidence.file_path,
            line_no=target_line_no,
            human_key=human_key,
            issue_signature=issue_signature,
        )
        feedback_signal = self._feedback_signal(session, review_request.id, fingerprint)
        (
            final_score,
            weak_anchor_penalty,
            resolved_penalty,
            risk_penalty,
            reply_penalty,
            policy_adjustment,
            policy_minimum_score,
        ) = self._score_candidate(
            session=session,
            review_request=review_request,
            file_path=evidence.file_path,
            rule_no=str(result.get("rule_no") or ""),
            fingerprint=fingerprint,
            score_raw=score_raw,
            false_positive_risk=str(result.get("false_positive_risk") or "medium"),
            weak_anchor=(target_line_no is None),
            feedback_signal=feedback_signal,
        )

        state = "eligible"
        suppression_reason = None
        if self._is_rule_suppressed_by_policy(str(result.get("rule_no") or "")):
            state = "suppressed"
            suppression_reason = "policy:suppressed_rule"
        elif self._is_rule_suppressed_for_path(evidence.file_path, str(result.get("rule_no") or "")):
            state = "suppressed"
            suppression_reason = "policy:path_rule_suppressed"
        elif feedback_signal.ignore_requested:
            state = "suppressed"
            suppression_reason = "feedback:ignore"
        elif reviewability != "auto_review":
            state = "suppressed"
            suppression_reason = f"reviewability:{reviewability}"
        elif requires_precise and target_line_no is None:
            state = "suppressed"
            suppression_reason = "weak_anchor"
        elif (
            feedback_signal.human_reply_count >= self.settings.feedback_reply_suppression_threshold
            and not feedback_signal.allow_requested
            and final_score < max(self.settings.minimum_publish_score + 0.1, 0.8)
        ):
            state = "suppressed"
            suppression_reason = "feedback:human_reply_history"
        elif final_score < max(self.settings.minimum_publish_score, policy_minimum_score or 0.0):
            state = "suppressed"
            suppression_reason = "below_threshold"

        if target_line_no is None and review_unit.candidate_line_nos:
            target_line_no = review_unit.candidate_line_nos[0]

        return FindingDecision(
            review_run_id=review_run.id,
            evidence_id=evidence.id,
            review_request_pk=review_request.id,
            review_system=review_run.review_system,
            project_ref=review_run.project_ref,
            review_request_id=review_run.review_request_id,
            fingerprint=fingerprint,
            dedupe_key=human_key,
            file_path=evidence.file_path,
            line_no=target_line_no,
            rule_no=str(result.get("rule_no") or ""),
            source_family=str(result.get("source_family") or ""),
            reviewability=reviewability,
            severity=self._severity_from_score(final_score),
            confidence=max(
                0.0,
                round(1.0 - weak_anchor_penalty - risk_penalty - reply_penalty, 4),
            ),
            score_raw=score_raw,
            score_final=final_score,
            anchor_signature=anchor_signature,
            anchor_payload={
                "file_path": evidence.file_path,
                "line_type": "new",
                "start_line": target_line_no or 1,
                "end_line": target_line_no or 1,
                "candidate_line_nos": tuple(review_unit.candidate_line_nos),
                "hunk_header": evidence.hunk_header,
                "changed_line_digest": self._sha1(review_unit.change_snippet),
                "incremental_publish_scope": "touched_line",
            },
            suppression_reason=suppression_reason,
            state=state,
        )

    def _score_candidate(
        self,
        *,
        session: Session,
        review_request: ReviewRequest,
        file_path: str,
        rule_no: str,
        fingerprint: str,
        score_raw: float,
        false_positive_risk: str,
        weak_anchor: bool,
        feedback_signal: FeedbackSignal,
    ) -> tuple[float, float, float, float, float, float, float | None]:
        risk_penalty = {"low": 0.0, "medium": 0.03, "high": 0.08}.get(false_positive_risk, 0.03)
        weak_anchor_penalty = 0.1 if weak_anchor else 0.0
        resolved_penalty = (
            self.settings.feedback_resolved_penalty
            if self._was_previously_resolved(session, review_request.id, fingerprint)
            else 0.0
        )
        reply_penalty = min(
            self.settings.feedback_reply_penalty * feedback_signal.human_reply_count,
            0.18,
        )
        policy_adjustment, policy_minimum_score = self._path_policy_adjustment(
            file_path=file_path,
            rule_no=rule_no,
            allow_requested=feedback_signal.allow_requested,
        )
        final_score = max(
            0.0,
            round(
                score_raw
                - risk_penalty
                - weak_anchor_penalty
                - resolved_penalty
                - reply_penalty
                + policy_adjustment,
                4,
            ),
        )
        return (
            final_score,
            weak_anchor_penalty,
            resolved_penalty,
            risk_penalty,
            reply_penalty,
            policy_adjustment,
            policy_minimum_score,
        )

    def _should_suppress_inline_anchor_failure(
        self,
        *,
        error_category: str,
        retryable: bool,
        error_message: str,
    ) -> bool:
        if error_category != "inline_anchor" or retryable:
            return False
        normalized = error_message.lower()
        return "line_code" in normalized or "valid line code" in normalized

    def _ingest_feedback(
        self,
        session: Session,
        *,
        review_request: ReviewRequest,
        feedback_page: FeedbackPage,
    ) -> None:
        for event in feedback_page.events:
            exists = (
                session.query(FeedbackEvent.id)
                .filter(FeedbackEvent.event_key == event.event_key)
                .first()
            )
            if exists:
                continue
            session.add(
                FeedbackEvent(
                    review_request_pk=review_request.id,
                    review_system=review_request.review_system,
                    project_ref=review_request.project_ref,
                    review_request_id=review_request.review_request_id,
                    event_key=event.event_key,
                    adapter_thread_ref=event.adapter_thread_ref,
                    adapter_comment_ref=event.adapter_comment_ref,
                    event_type=event.event_type,
                    actor_type=event.actor_type,
                    actor_ref=event.actor_ref,
                    payload=event.payload,
                    occurred_at=event.occurred_at,
                )
            )

    def _mark_fingerprint_resolved(
        self,
        session: Session,
        review_request_pk: str,
        fingerprint: str,
    ) -> None:
        decisions = (
            session.query(FindingDecision)
            .filter(
                FindingDecision.review_request_pk == review_request_pk,
                FindingDecision.fingerprint == fingerprint,
                FindingDecision.state.in_(["eligible", "published", "failed_publication"]),
            )
            .all()
        )
        for decision in decisions:
            decision.state = "resolved"

    def _mark_fingerprint_reopened(
        self,
        session: Session,
        review_request_pk: str,
        fingerprint: str,
    ) -> None:
        active_exists = (
            session.query(FindingDecision.id)
            .filter(
                FindingDecision.review_request_pk == review_request_pk,
                FindingDecision.fingerprint == fingerprint,
                FindingDecision.state.in_(["eligible", "published", "failed_publication"]),
            )
            .first()
            is not None
        )
        if active_exists:
            return
        latest_resolved = (
            session.query(FindingDecision)
            .filter(
                FindingDecision.review_request_pk == review_request_pk,
                FindingDecision.fingerprint == fingerprint,
                FindingDecision.state == "resolved",
            )
            .order_by(FindingDecision.updated_at.desc(), FindingDecision.created_at.desc())
            .first()
        )
        if latest_resolved is not None:
            latest_resolved.state = "published"

    def _reconcile_thread_snapshots(
        self,
        session: Session,
        *,
        review_request_pk: str,
        threads: dict[str, ThreadSnapshot],
        head_sha: str | None = None,
    ) -> None:
        if not threads:
            return
        tracked_threads = (
            session.query(ThreadSyncState)
            .filter(
                ThreadSyncState.review_request_pk == review_request_pk,
                ThreadSyncState.sync_status.in_(["open", "stale", "resolved"]),
            )
            .all()
        )
        refreshed_at = datetime.now(UTC)
        for thread_state in tracked_threads:
            snapshot = threads.get(thread_state.adapter_thread_ref)
            if snapshot is None:
                continue
            thread_state.adapter_comment_ref = snapshot.comment_ref or thread_state.adapter_comment_ref
            thread_state.last_synced_at = refreshed_at
            thread_state.last_seen_head_sha = head_sha or thread_state.last_seen_head_sha
            if snapshot.resolved:
                if thread_state.sync_status != "resolved":
                    thread_state.sync_status = "resolved"
                    thread_state.resolution_reason = "remote_resolved"
                    self._mark_fingerprint_resolved(
                        session,
                        review_request_pk,
                        thread_state.finding_fingerprint,
                    )
                continue
            if thread_state.sync_status == "resolved":
                thread_state.sync_status = "open"
                thread_state.resolution_reason = "remote_reopened"
                self._mark_fingerprint_reopened(
                    session,
                    review_request_pk,
                    thread_state.finding_fingerprint,
                )
                continue
            if (
                thread_state.sync_status == "stale"
                and thread_state.resolution_reason != "anchor_changed"
            ):
                thread_state.sync_status = "open"
                thread_state.resolution_reason = None

    def _feedback_signal(
        self,
        session: Session,
        review_request_pk: str,
        fingerprint: str,
    ) -> FeedbackSignal:
        thread_refs = [
            thread_ref
            for (thread_ref,) in (
                session.query(ThreadSyncState.adapter_thread_ref)
                .filter(
                    ThreadSyncState.review_request_pk == review_request_pk,
                    ThreadSyncState.finding_fingerprint == fingerprint,
                )
                .all()
            )
        ]
        if not thread_refs:
            return FeedbackSignal()

        events = (
            session.query(FeedbackEvent)
            .filter(
                FeedbackEvent.review_request_pk == review_request_pk,
                FeedbackEvent.adapter_thread_ref.in_(thread_refs),
            )
            .all()
        )
        resolved_count = 0
        unresolved_count = 0
        human_reply_count = 0
        ignore_requested = False
        allow_requested = False

        for event in events:
            if event.event_type == "resolved":
                resolved_count += 1
            elif event.event_type == "unresolved":
                unresolved_count += 1
            elif event.event_type == "reply" and event.actor_type == "human":
                human_reply_count += 1
                body = str((event.payload or {}).get("body") or "")
                if self._contains_feedback_command(body, "ignore"):
                    ignore_requested = True
                if self._contains_feedback_command(body, "allow"):
                    allow_requested = True

        return FeedbackSignal(
            resolved_count=resolved_count,
            unresolved_count=unresolved_count,
            human_reply_count=human_reply_count,
            ignore_requested=ignore_requested,
            allow_requested=allow_requested,
        )

    def _contains_feedback_command(self, body: str, command: str) -> bool:
        pattern = re.compile(
            rf"(?im)^\s*(?:/)?(?:review-bot|bot)(?::|\s+)\s*{re.escape(command)}(?:\s|$)"
        )
        return bool(pattern.search(body))

    def _path_policy_adjustment(
        self,
        *,
        file_path: str,
        rule_no: str,
        allow_requested: bool,
    ) -> tuple[float, float | None]:
        adjustment = 0.0
        minimum_score: float | None = None
        if rule_no in self.policy.allowed_rules or allow_requested:
            adjustment += 0.08
        for policy in self.policy.rules_for_path(file_path):
            if rule_no in policy.promote_rules:
                adjustment += 0.08
            adjustment += policy.score_adjustment
            if policy.minimum_score is not None:
                minimum_score = max(minimum_score or 0.0, policy.minimum_score)
        return adjustment, minimum_score

    def _is_rule_suppressed_by_policy(self, rule_no: str) -> bool:
        return rule_no in self.policy.suppressed_rules

    def _is_rule_suppressed_for_path(self, file_path: str, rule_no: str) -> bool:
        return any(
            rule_no in policy.suppress_rules
            for policy in self.policy.rules_for_path(file_path)
        )

    def _find_existing_thread(
        self,
        session: Session,
        review_request_pk: str,
        fingerprint: str,
        *,
        include_resolved: bool = False,
    ) -> ThreadSyncState | None:
        allowed_statuses = ["open"]
        if include_resolved:
            allowed_statuses.append("resolved")
        return (
            session.query(ThreadSyncState)
            .filter(
                ThreadSyncState.review_request_pk == review_request_pk,
                ThreadSyncState.finding_fingerprint == fingerprint,
                ThreadSyncState.sync_status.in_(allowed_statuses),
            )
            .order_by(ThreadSyncState.updated_at.desc())
            .first()
        )

    def _thread_targets_current_files(
        self,
        session: Session,
        *,
        thread_state: ThreadSyncState,
        current_file_paths: set[str],
    ) -> bool:
        if not current_file_paths or not thread_state.finding_decision_id:
            return False
        decision = session.get(FindingDecision, thread_state.finding_decision_id)
        if decision is None:
            return False
        return decision.file_path in current_file_paths

    def _published_count(self, session: Session, review_request_pk: str) -> int:
        return int(
            session.query(func.count(PublicationState.id))
            .filter(PublicationState.review_request_pk == review_request_pk)
            .scalar()
            or 0
        )

    def _safe_publish_check(
        self,
        adapter: object,
        key: ReviewRequestKey,
        request: CheckPublishRequest,
    ) -> None:
        try:
            adapter.publish_check(key, request)
        except Exception as exc:
            error_category, retryable = self._classify_error(exc)
            logger.warning(
                "review_check_publish_failed",
                extra={
                    "review_run_event": {
                        "event": "check_publish_failed",
                        "review_request_key": key.model_dump(),
                        "head_sha": request.head_sha,
                        "state": request.state,
                        "error_category": error_category,
                        "error_message": str(exc),
                        "retryable": retryable,
                    }
                },
            )
            return

    def _ensure_review_request(
        self,
        session: Session,
        key: ReviewRequestKey,
        *,
        meta: ReviewRequestMeta | None = None,
    ) -> ReviewRequest:
        existing = self._find_review_request(session, key)
        if existing is not None:
            if meta is not None:
                self._apply_meta_to_request(existing, meta)
            session.flush()
            return existing
        request = ReviewRequest(
            review_system=key.review_system,
            project_ref=key.project_ref,
            review_request_id=key.review_request_id,
        )
        if meta is not None:
            self._apply_meta_to_request(request, meta)
        session.add(request)
        session.flush()
        return request

    def _apply_request_meta(
        self,
        review_request: ReviewRequest,
        meta: ReviewRequestMeta,
        diff_payload: DiffPayload,
    ) -> None:
        self._apply_meta_to_request(review_request, meta)
        review_request.latest_base_sha = diff_payload.pull_request.get("base_sha") or review_request.latest_base_sha
        review_request.latest_start_sha = diff_payload.pull_request.get("start_sha") or review_request.latest_start_sha
        review_request.latest_head_sha = diff_payload.pull_request.get("head_sha") or review_request.latest_head_sha

    def _apply_meta_to_request(
        self,
        review_request: ReviewRequest,
        meta: ReviewRequestMeta,
    ) -> None:
        review_request.title = meta.title
        review_request.draft = meta.draft
        review_request.source_branch = meta.source_branch
        review_request.target_branch = meta.target_branch
        review_request.latest_base_sha = meta.base_sha or review_request.latest_base_sha
        review_request.latest_start_sha = meta.start_sha or review_request.latest_start_sha
        review_request.latest_head_sha = meta.head_sha or review_request.latest_head_sha

    def _find_review_request(self, session: Session, key: ReviewRequestKey) -> ReviewRequest | None:
        return (
            session.query(ReviewRequest)
            .filter(
                ReviewRequest.review_system == key.review_system,
                ReviewRequest.project_ref == key.project_ref,
                ReviewRequest.review_request_id == key.review_request_id,
            )
            .one_or_none()
        )

    def _get_review_request(self, session: Session, review_request_pk: str) -> ReviewRequest:
        review_request = session.get(ReviewRequest, review_request_pk)
        if review_request is None:
            raise HTTPException(status_code=404, detail=f"Review request not found: {review_request_pk}")
        return review_request

    def _get_review_run(self, session: Session, review_run_id: str) -> ReviewRun:
        review_run = session.get(ReviewRun, review_run_id)
        if review_run is None:
            raise HTTPException(status_code=404, detail=f"Review run not found: {review_run_id}")
        return review_run

    def _legacy_key(self, pr_id: int) -> ReviewRequestKey:
        return ReviewRequestKey(
            review_system=self.settings.legacy_review_system,
            project_ref=self.settings.legacy_project_ref,
            review_request_id=str(pr_id),
        )

    def _key_from_run(self, review_run: ReviewRun) -> ReviewRequestKey:
        return ReviewRequestKey(
            review_system=review_run.review_system,
            project_ref=review_run.project_ref,
            review_request_id=review_run.review_request_id,
        )

    def _get_adapter(self) -> object:
        if hasattr(self.platform_client, "fetch_diff"):
            return self.platform_client
        return _LegacyAdapterShim(self.platform_client)

    def _severity_from_score(self, score: float) -> str:
        if score >= 0.9:
            return "high"
        if score >= 0.75:
            return "medium"
        return "low"

    def _render_comment(self, decision: FindingDecision) -> str:
        lines = [
            f"[봇 리뷰] {decision.title}",
            "",
            decision.summary or "",
        ]
        if decision.suggested_fix:
            lines.extend(["", "권장 수정", decision.suggested_fix])
        return "\n".join(lines)

    def _render_reminder_comment(self, decision: FindingDecision) -> str:
        lines = [
            f"[봇 리뷰] {decision.title}",
            "",
            "이전 리뷰에서 지적했던 내용이 이번 전체 재검토에서도 계속 확인되었습니다.",
        ]
        if decision.summary:
            lines.extend(["", decision.summary])
        if decision.suggested_fix:
            lines.extend(["", "권장 수정", decision.suggested_fix])
        return "\n".join(lines)

    def _is_cpp_path(self, path: str) -> bool:
        return any(path.endswith(ext) for ext in CPP_EXTENSIONS)

    def _extract_line_no(self, patch: str) -> int | None:
        match = HUNK_RE.search(patch)
        if match is None:
            return None
        return int(match.group("new"))

    def _iter_review_units(self, patch: str) -> list[ReviewUnit]:
        lines = patch.splitlines()
        units: list[ReviewUnit] = []
        current_header: str | None = None
        current_lines: list[str] = []

        for line in lines:
            if line.startswith("@@"):
                if current_header is not None:
                    units.append(self._build_review_unit(current_header, current_lines))
                current_header = line
                current_lines = []
                continue
            if current_header is not None:
                current_lines.append(line)

        if current_header is not None:
            units.append(self._build_review_unit(current_header, current_lines))

        if units:
            expanded: list[ReviewUnit] = []
            for unit in units:
                expanded.extend(self._split_large_added_unit(unit))
            return expanded
        return [
            ReviewUnit(
                patch=patch,
                change_snippet=patch,
                default_line_no=self._extract_line_no(patch),
                candidate_line_nos=(),
                changed_lines=(),
            )
        ]

    def _build_review_unit(self, header: str, hunk_lines: list[str]) -> ReviewUnit:
        match = HUNK_RE.match(header)
        old_line_no = int(match.group("old")) if match else None
        new_line_no = int(match.group("new")) if match else None
        changed_lines: list[ChangedPatchLine] = []
        candidate_line_nos: list[int] = []
        numbered_lines: list[str] = [header]

        for raw_line in hunk_lines:
            if raw_line.startswith("\\"):
                continue
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                changed_lines.append(
                    ChangedPatchLine(marker="+", text=raw_line[1:], new_line_no=new_line_no)
                )
                if new_line_no is not None:
                    candidate_line_nos.append(new_line_no)
                    numbered_lines.append(f"L{new_line_no} | + {raw_line[1:]}")
                    new_line_no += 1
                continue
            if raw_line.startswith("-") and not raw_line.startswith("---"):
                changed_lines.append(
                    ChangedPatchLine(marker="-", text=raw_line[1:], old_line_no=old_line_no)
                )
                if old_line_no is not None:
                    numbered_lines.append(f"OLD{old_line_no} | - {raw_line[1:]}")
                    old_line_no += 1
                continue
            if raw_line.startswith(" "):
                if old_line_no is not None:
                    old_line_no += 1
                if new_line_no is not None:
                    new_line_no += 1

        normalized_candidates = tuple(dict.fromkeys(candidate_line_nos))
        default_line_no = normalized_candidates[0] if normalized_candidates else self._extract_line_no(header)
        return ReviewUnit(
            patch="\n".join([header, *hunk_lines]),
            change_snippet="\n".join(numbered_lines),
            default_line_no=default_line_no,
            candidate_line_nos=normalized_candidates,
            changed_lines=tuple(changed_lines),
        )

    def _split_large_added_unit(self, unit: ReviewUnit) -> list[ReviewUnit]:
        if len(unit.candidate_line_nos) <= MAX_LINES_PER_REVIEW_UNIT:
            return [unit]
        if not unit.changed_lines or any(line.marker != "+" for line in unit.changed_lines):
            return [unit]

        added_lines = [line for line in unit.changed_lines if line.new_line_no is not None]
        if len(added_lines) <= MAX_LINES_PER_REVIEW_UNIT:
            return [unit]

        split_units: list[ReviewUnit] = []
        for start in range(0, len(added_lines), MAX_LINES_PER_REVIEW_UNIT):
            chunk = added_lines[start : start + MAX_LINES_PER_REVIEW_UNIT]
            first_line_no = chunk[0].new_line_no
            if first_line_no is None:
                continue
            header = f"@@ -0,0 +{first_line_no},{len(chunk)} @@"
            patch_lines = [header, *[f"+{line.text}" for line in chunk]]
            numbered_lines = [header, *[f"L{line.new_line_no} | + {line.text}" for line in chunk]]
            candidate_line_nos = tuple(
                line.new_line_no for line in chunk if line.new_line_no is not None
            )
            split_units.append(
                ReviewUnit(
                    patch="\n".join(patch_lines),
                    change_snippet="\n".join(numbered_lines),
                    default_line_no=candidate_line_nos[0] if candidate_line_nos else first_line_no,
                    candidate_line_nos=candidate_line_nos,
                    changed_lines=tuple(chunk),
                )
            )
        return split_units or [unit]

    def _issue_signature(self, result: dict[str, object], review_unit: ReviewUnit) -> str:
        changed_lines = [
            line.text.strip() for line in review_unit.changed_lines if line.text.strip()
        ]
        signature_source = " ".join(changed_lines[:3]) or review_unit.patch
        signature_source += f"|{result.get('rule_no')}|{result.get('title')}|{result.get('summary')}"
        return self._sha1(signature_source)

    def _resolve_target_line_no(
        self,
        *,
        requested_line_no: int | None,
        review_unit: ReviewUnit,
        result: dict[str, object],
    ) -> int | None:
        if requested_line_no is not None and requested_line_no in review_unit.candidate_line_nos:
            return requested_line_no

        issue = classify_issue(
            extract_changed_excerpt(review_unit.change_snippet),
            result.get("category"),
            str(result.get("title") or ""),
            str(result.get("summary") or ""),
        )
        inferred_line = select_candidate_line(
            change_snippet=review_unit.change_snippet,
            candidate_line_nos=review_unit.candidate_line_nos,
            issue=issue,
        )
        if inferred_line is not None:
            return inferred_line
        if requires_direct_signal(issue):
            return None
        if review_unit.default_line_no in review_unit.candidate_line_nos:
            return review_unit.default_line_no
        if review_unit.candidate_line_nos:
            return review_unit.candidate_line_nos[0]
        return requested_line_no or review_unit.default_line_no

    def _requires_precise_anchor(self, *, review_unit: ReviewUnit, result: dict[str, object]) -> bool:
        issue = classify_issue(
            extract_changed_excerpt(review_unit.change_snippet),
            result.get("category"),
            str(result.get("title") or ""),
            str(result.get("summary") or ""),
        )
        return requires_direct_signal(issue)

    def _human_key(self, *, file_path: str, line_no: int | None, title: str, summary: str) -> str:
        normalized_line = (line_no or 0) // 64
        source = f"{file_path}|{normalized_line}|{title}|{summary}"
        return self._sha1(source)[:12]

    def _fingerprint(
        self,
        *,
        key: ReviewRequestKey,
        file_path: str,
        line_no: int | None,
        human_key: str,
        issue_signature: str,
    ) -> str:
        payload = (
            f"{key.review_system}|{key.project_ref}|{key.review_request_id}|"
            f"{file_path}|{line_no or 0}|{human_key}|{issue_signature}"
        )
        return self._sha256(payload)

    def _anchor_signature(self, *, file_path: str, line_no: int | None, hunk_header: str | None) -> str:
        return self._sha1(f"{file_path}|{line_no or 0}|{hunk_header or ''}")

    def _was_previously_resolved(self, session: Session, review_request_pk: str, fingerprint: str) -> bool:
        return (
            session.query(ThreadSyncState.id)
            .filter(
                ThreadSyncState.review_request_pk == review_request_pk,
                ThreadSyncState.finding_fingerprint == fingerprint,
                ThreadSyncState.sync_status == "resolved",
            )
            .first()
            is not None
        )

    def _prepare_publication_candidates(
        self,
        *,
        session: Session,
        review_run: ReviewRun,
        review_request: ReviewRequest,
        decisions: list[FindingDecision],
    ) -> list[PublicationCandidate]:
        candidates: list[PublicationCandidate] = []
        for decision in decisions:
            draft = self.provider.build_draft(
                file_path=decision.file_path,
                rule_no=decision.rule_no,
                title=str(decision.evidence.raw_engine_payload.get("title") or decision.rule_no),
                summary=str(decision.evidence.raw_engine_payload.get("summary") or decision.rule_no),
                rule_text=decision.evidence.raw_engine_payload.get("text"),
                fix_guidance=decision.evidence.raw_engine_payload.get("fix_guidance"),
                category=str(decision.evidence.raw_engine_payload.get("category") or ""),
                change_snippet=decision.evidence.change_snippet,
                line_no=decision.line_no,
                candidate_line_nos=tuple(decision.evidence.candidate_line_nos),
            )
            if not draft.should_publish:
                decision.state = "suppressed"
                decision.suppression_reason = "provider_should_not_publish"
                continue

            decision.title = draft.title
            decision.summary = draft.summary
            decision.suggested_fix = draft.suggested_fix
            base_body = self._render_comment(decision)
            base_body_hash = self._sha256(base_body)
            existing_thread = self._find_existing_thread(
                session,
                review_request.id,
                decision.fingerprint,
                include_resolved=True,
            )
            reminder_candidate = self._should_resurface_open_thread(
                review_run=review_run,
                decision=decision,
                existing_thread=existing_thread,
            )
            body = (
                self._render_reminder_comment(decision)
                if reminder_candidate
                else base_body
            )
            body_hash = self._sha256(body)
            if review_run.mode == "incremental" and existing_thread is None:
                candidate_lines = tuple(decision.evidence.candidate_line_nos)
                if decision.line_no is None or decision.line_no not in candidate_lines:
                    decision.state = "suppressed"
                    decision.suppression_reason = "incremental_out_of_scope"
                    continue

            candidates.append(
                PublicationCandidate(
                    decision=decision,
                    draft=draft,
                    body=body,
                    body_hash=body_hash,
                    canonical_body_hash=base_body_hash,
                    existing_thread=existing_thread,
                    publication_key=(
                        decision.file_path,
                        draft.line_no or decision.line_no,
                        draft.title.strip(),
                    ),
                    priority_group=self._candidate_priority_group(
                        review_run=review_run,
                        decision=decision,
                        existing_thread=existing_thread,
                        canonical_body_hash=base_body_hash,
                        reminder_candidate=reminder_candidate,
                    ),
                    reminder_candidate=reminder_candidate,
                )
            )
        return candidates

    def _candidate_priority_group(
        self,
        *,
        review_run: ReviewRun,
        decision: FindingDecision,
        existing_thread: ThreadSyncState | None,
        canonical_body_hash: str,
        reminder_candidate: bool,
    ) -> int:
        del review_run
        if existing_thread is None:
            return 1
        if existing_thread.sync_status == "resolved":
            return 0
        if existing_thread.anchor_signature != decision.anchor_signature:
            return 0
        if reminder_candidate:
            return 2
        if existing_thread.body_hash != canonical_body_hash:
            return 0
        return 3

    def _should_resurface_open_thread(
        self,
        *,
        review_run: ReviewRun,
        decision: FindingDecision,
        existing_thread: ThreadSyncState | None,
    ) -> bool:
        if review_run.mode == "incremental":
            return False
        if existing_thread is None:
            return False
        if existing_thread.sync_status != "open":
            return False
        return existing_thread.anchor_signature == decision.anchor_signature

    def _select_batch_candidates(
        self,
        candidates: list[PublicationCandidate],
    ) -> list[PublicationCandidate]:
        selected: list[PublicationCandidate] = []
        seen_file_titles: set[tuple[str, str]] = set()
        title_counts: dict[str, int] = {}
        ordered_candidates = sorted(
            (
                candidate
                for candidate in candidates
                if candidate.priority_group != 3
            ),
            key=lambda candidate: (
                candidate.priority_group,
                -candidate.decision.score_final,
                candidate.decision.created_at,
            ),
        )
        for candidate in ordered_candidates:
            decision = candidate.decision
            file_title = (decision.file_path, decision.rule_no)
            if file_title in seen_file_titles:
                continue
            title_counts[decision.rule_no] = title_counts.get(decision.rule_no, 0)
            if title_counts[decision.rule_no] >= self.settings.rule_family_cap:
                continue
            selected.append(candidate)
            seen_file_titles.add(file_title)
            title_counts[decision.rule_no] += 1
            if len(selected) >= self.settings.batch_size:
                break
        return selected

    def _log_run_event(
        self,
        event: str,
        review_run: ReviewRun,
        **fields: Any,
    ) -> None:
        payload: dict[str, Any] = {
            "event": event,
            "review_run_id": review_run.id,
            "review_request_key": {
                "review_system": review_run.review_system,
                "project_ref": review_run.project_ref,
                "review_request_id": review_run.review_request_id,
            },
            "mode": review_run.mode,
            "trigger": review_run.trigger,
            "status": review_run.status,
        }
        payload.update(fields)
        logger.info("review_run_event", extra={"review_run_event": payload})

    def _classify_error(self, exc: Exception) -> tuple[str, bool]:
        if isinstance(exc, ReviewBotError):
            return exc.category, exc.retryable
        if isinstance(exc, HTTPException):
            return "http", exc.status_code >= 500
        return "unexpected", False

    def _record_dead_letter(
        self,
        session: Session,
        *,
        review_run: ReviewRun,
        stage: str,
        error_category: str,
        error_message: str,
        replayable: bool,
        payload: dict[str, object],
    ) -> None:
        if not self.settings.dead_letter_enabled:
            return
        session.add(
            DeadLetterRecord(
                review_run_id=review_run.id,
                review_request_pk=review_run.review_request_pk,
                review_system=review_run.review_system,
                project_ref=review_run.project_ref,
                review_request_id=review_run.review_request_id,
                stage=stage,
                error_category=error_category,
                error_message=error_message,
                replayable=replayable,
                payload=payload,
            )
        )

    def _sha1(self, value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()

    def _sha256(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _LegacyAdapterShim:
    def __init__(self, client: object) -> None:
        self.client = client

    def fetch_review_request_meta(self, key: ReviewRequestKey) -> ReviewRequestMeta:
        payload = self.client.get_pull_request_diff(int(key.review_request_id))
        pull_request = payload.get("pull_request", {})
        return ReviewRequestMeta(
            key=key,
            head_sha=pull_request.get("head_sha"),
            base_sha=pull_request.get("base_sha"),
            start_sha=pull_request.get("start_sha"),
        )

    def fetch_diff(self, key: ReviewRequestKey, *, mode: str, base_sha: str | None = None) -> DiffPayload:
        del mode, base_sha
        return DiffPayload.model_validate(self.client.get_pull_request_diff(int(key.review_request_id)))

    def list_threads(self, key: ReviewRequestKey) -> list[object]:
        del key
        return []

    def upsert_comment(self, key: ReviewRequestKey, request: CommentUpsertRequest):
        payload = self.client.post_comment(
            int(key.review_request_id),
            body=request.body,
            file_path=request.anchor.file_path,
            line_no=request.anchor.start_line,
        )
        return type("CompatResult", (), {
            "comment_ref": str(payload.get("id")) if payload.get("id") else None,
            "thread_ref": str(payload.get("discussion_id") or payload.get("id")) if payload else None,
            "action": "updated" if request.existing_thread_ref else "created",
        })()

    def resolve_thread(self, key: ReviewRequestKey, thread_ref: str, *, reason: str):
        del key, thread_ref, reason
        return {"ok": True, "resolved": True}

    def publish_check(self, key: ReviewRequestKey, request: CheckPublishRequest):
        if hasattr(self.client, "post_status"):
            self.client.post_status(
                int(key.review_request_id),
                state=request.state,
                description=request.description,
            )
        return {"ok": True}

    def collect_feedback(self, key: ReviewRequestKey, *, since: str | None = None) -> FeedbackPage:
        del key, since
        return FeedbackPage(events=[])
