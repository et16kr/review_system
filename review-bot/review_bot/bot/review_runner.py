from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

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
    DeadLetterRecord,
    FindingLifecycleEvent,
    PublicationState,
    ReviewRequest,
    ReviewRun,
    ThreadSyncState,
)
from review_bot.errors import ReviewBotError
from review_bot.language_registry import get_language_registry
from review_bot.metrics import (
    detect_phase_duration_seconds,
    engine_call_duration_seconds,
    feedback_commands_total,
    finding_resolution_events_total,
    findings_published_total,
    findings_resolved_total,
    findings_suppressed_total,
    publish_phase_duration_seconds,
    review_runs_total,
    verify_attempts_total,
    verify_dropped_total,
)
from review_bot.policy import ReviewPolicy, load_review_policy
from review_bot.providers.change_analysis import (
    classify_issue,
    extract_changed_excerpt,
    requires_direct_signal,
    select_candidate_line,
)
from review_bot.providers.base import FindingDraft, VerifyDraftResult
from review_bot.providers.factory import build_review_comment_provider
from review_bot.review_systems.factory import build_review_system_adapter
from review_bot.review_systems.base import render_general_note_purpose_marker
HUNK_RE = re.compile(r"@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@")
MAX_LINES_PER_REVIEW_UNIT = 80
MAX_COMMENT_BODY = 3800  # GitLab 4000자 제한 여유
FILE_CONTEXT_MAX_CHARS = 4000  # LLM 프롬프트에 포함할 파일 컨텍스트 최대 길이
_FILE_CONTEXT_KEY = "_file_context"  # raw_engine_payload 내 파일 컨텍스트 저장 키
_SIMILAR_CODE_KEY = "_similar_code"  # raw_engine_payload 내 유사 코드 저장 키
_REPORTABLE_REVIEW_RUN_STATUSES = ("success", "partial", "failed")
_IN_FLIGHT_REVIEW_RUN_STATUSES = ("queued", "running")
_NOTE_MENTION_EXPECTED_HEAD_RETRIES = 5
_NOTE_MENTION_EXPECTED_HEAD_SLEEP_SECONDS = 1.0
_FULL_REPORT_SECTION_ORDER = (
    "published_inline",
    "already_open",
    "pending_batch",
    "backlog_existing_open",
    "backlog_resolved_unchanged",
    "backlog_feedback_later",
    "suppressed_feedback_ignore",
    "suppressed_feedback_false_positive",
    "suppressed_other",
    "failed_publication",
)
_FULL_REPORT_SECTION_TITLES = {
    "published_inline": "이번 run에서 inline으로 게시된 항목",
    "already_open": "이미 열린 thread에 반영되어 재게시하지 않은 항목",
    "pending_batch": "다음 batch 후보",
    "backlog_existing_open": "기존 open thread backlog",
    "backlog_resolved_unchanged": "resolved 이후 unchanged backlog",
    "backlog_feedback_later": "`bot:later`로 보류된 항목",
    "suppressed_feedback_ignore": "`bot:ignore`로 suppress된 항목",
    "suppressed_feedback_false_positive": "`bot:false-positive`로 suppress된 항목",
    "suppressed_other": "기타 억제 항목",
    "failed_publication": "게시 실패 항목",
}
_FULL_REPORT_SECTION_SUMMARY_LABELS = {
    "published_inline": "inline 게시",
    "already_open": "이미 열린 thread 반영",
    "pending_batch": "다음 batch 대기",
    "backlog_existing_open": "기존 open backlog",
    "backlog_resolved_unchanged": "resolved backlog",
    "backlog_feedback_later": "`bot:later` 보류",
    "suppressed_feedback_ignore": "`bot:ignore` suppress",
    "suppressed_feedback_false_positive": "`bot:false-positive` suppress",
    "suppressed_other": "기타 suppress",
    "failed_publication": "게시 실패",
}
_BACKLOG_ONLY_SECTION_ORDER = (
    "backlog_existing_open",
    "backlog_resolved_unchanged",
    "backlog_feedback_later",
)
_RULE_EFFECTIVENESS_MEANINGFUL_STATES = (
    "published",
    "resolved",
    "suppressed",
    "failed_publication",
)
_RULE_EFFECTIVENESS_SURFACED_STATES = ("published", "resolved", "suppressed")
_DOCS_EXTENSIONS = {".md", ".mdx", ".markdown", ".rst", ".adoc"}
_DOCS_FILENAMES = {
    "readme",
    "readme.md",
    "changelog",
    "changelog.md",
    "contributing",
    "contributing.md",
    "security.md",
    "code_of_conduct.md",
}
_CI_PATH_BUCKETS = {".github", ".github/workflows", ".gitlab-ci.yml", ".gitlab-ci.yaml"}
_CI_CONTEXTS = {"github_actions", "gitlab_ci"}


def _compute_top_k(patch: str) -> int:
    """패치 크기에 따라 동적으로 top_k를 계산한다."""
    lines = patch.count("\n")
    if lines < 20:
        return 5
    if lines < 50:
        return 8
    if lines < 100:
        return 12
    return 15
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
    same_line_category_key: tuple[str, int, str] | None
    priority_group: int
    reminder_candidate: bool = False
    backlog_only: bool = False
    backlog_reason: str | None = None


@dataclass(frozen=True)
class FeedbackSignal:
    resolved_count: int = 0
    unresolved_count: int = 0
    human_reply_count: int = 0
    ignore_requested: bool = False
    wrong_language_requested: bool = False
    false_positive_requested: bool = False
    later_requested: bool = False
    allow_requested: bool = False
    expected_language_id: str | None = None


@dataclass(frozen=True)
class ParsedFeedbackCommand:
    command: str
    expected_language_id: str | None = None


@dataclass(frozen=True)
class BacklogEntry:
    section: str
    thread: ThreadSyncState
    reason: str
    feedback_signal: FeedbackSignal


@dataclass(frozen=True)
class RuleEffectivenessFingerprintState:
    fingerprint: str
    project_ref: str
    rule_no: str
    source_family: str
    state: str


class ReviewRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.language_registry = get_language_registry()
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
        requested_base_sha = meta.base_sha if meta else review_request.latest_base_sha
        requested_start_sha = meta.start_sha if meta else review_request.latest_start_sha
        requested_head_sha = meta.head_sha if meta else review_request.latest_head_sha

        # best-effort dedupe: 동일 target(mode + base/start/head sha)의 pending run만 재사용
        pending_runs = (
            session.query(ReviewRun)
            .filter(
                ReviewRun.review_request_pk == review_request.id,
                ReviewRun.status.in_(["queued", "running"]),
                ReviewRun.mode == mode,
            )
            .order_by(ReviewRun.created_at.desc(), ReviewRun.id.desc())
            .all()
        )
        existing = next(
            (
                candidate
                for candidate in pending_runs
                if (
                    candidate.base_sha == requested_base_sha
                    and candidate.start_sha == requested_start_sha
                    and candidate.head_sha == requested_head_sha
                )
            ),
            None,
        )
        if existing is not None:
            logger.info(
                "review_run_deduplicated review_run_id=%s trigger=%s mode=%s key=%s/%s/%s",
                existing.id,
                trigger,
                mode,
                key.review_system,
                key.project_ref,
                key.review_request_id,
            )
            return existing

        review_run = ReviewRun(
            review_request_pk=review_request.id,
            review_system=key.review_system,
            project_ref=key.project_ref,
            review_request_id=key.review_request_id,
            trigger=trigger,
            mode=mode,
            status="queued",
            base_sha=requested_base_sha,
            start_sha=requested_start_sha,
            head_sha=requested_head_sha,
            created_at=datetime.now(UTC),
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
            meta, diff_payload = self._refresh_detect_inputs_for_expected_head(
                adapter=adapter,
                key=key,
                review_run=review_run,
                meta=meta,
                diff_payload=diff_payload,
            )
            current_threads = {thread.thread_ref: thread for thread in adapter.list_threads(key)}
            self._apply_request_meta(review_request, meta, diff_payload)
            self._reconcile_thread_snapshots(
                session,
                review_request=review_request,
                key=key,
                adapter=adapter,
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

            # autoflush=False 환경에서 새 FeedbackEvent가 보이도록 명시적 flush
            session.flush()
            # N+1 방지: 피드백 신호와 규칙 가중치를 루프 전에 일괄 로드
            feedback_cache = self._load_feedback_cache(session, review_request.id)
            rule_weights = self._load_rule_effectiveness_weights(session)

            seen_human_keys: set[str] = set()
            detect_t0 = __import__("time").monotonic()
            for file_item in diff_payload.files:
                file_context = self._fetch_file_context(
                    adapter, key, file_item.path, review_run.head_sha
                )
                language_match = self.language_registry.resolve(
                    file_path=file_item.path,
                    source_text=file_context or file_item.patch,
                )
                if not language_match.reviewable:
                    continue
                for review_unit in self._iter_review_units(file_item.patch):
                    top_k = _compute_top_k(review_unit.patch)
                    t0 = __import__("time").monotonic()
                    review = self._engine_review_diff(
                        review_unit.patch,
                        top_k=top_k,
                        file_path=file_item.path,
                        file_context=file_context,
                        language_id=language_match.language_id,
                        profile_id=language_match.profile_id,
                        context_id=language_match.context_id,
                        dialect_id=language_match.dialect_id,
                    )
                    engine_call_duration_seconds.observe(__import__("time").monotonic() - t0)
                    detected_patterns = [str(item) for item in review.get("detected_patterns", [])]
                    # RAG: 유사 코드 패턴 검색 (codebase가 인덱싱된 경우에만 동작)
                    similar_code = self.engine_client.search_codebase(
                        review_unit.change_snippet[:500], top_k=2
                    )
                    for result in review.get("results", [])[:3]:
                        payload = dict(result)
                        runtime_defaults = {
                            "language_id": language_match.language_id,
                            "profile_id": language_match.profile_id,
                            "context_id": language_match.context_id,
                            "dialect_id": language_match.dialect_id,
                        }
                        for runtime_key, fallback in runtime_defaults.items():
                            if review.get(runtime_key) is not None:
                                payload[runtime_key] = review.get(runtime_key)
                            elif fallback is not None:
                                payload[runtime_key] = fallback
                        if review.get("prompt_overlay_refs") is not None:
                            payload["prompt_overlay_refs"] = review.get("prompt_overlay_refs")
                        payload["language_match_source"] = language_match.match_source
                        if file_context:
                            payload[_FILE_CONTEXT_KEY] = file_context[:FILE_CONTEXT_MAX_CHARS]
                        if similar_code:
                            payload[_SIMILAR_CODE_KEY] = similar_code
                        evidence = FindingEvidence(
                            review_run_id=review_run.id,
                            review_request_pk=review_request.id,
                            file_path=file_item.path,
                            patch_digest=self._sha1(review_unit.patch),
                            hunk_header=review_unit.patch.splitlines()[0] if review_unit.patch else None,
                            candidate_line_nos=list(review_unit.candidate_line_nos),
                            matched_patterns=detected_patterns,
                            change_snippet=review_unit.change_snippet,
                            raw_engine_payload=payload,
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
                            feedback_cache=feedback_cache,
                            rule_weights=rule_weights,
                        )
                        if decision is not None:
                            session.add(decision)
                            if decision.state == "suppressed":
                                findings_suppressed_total.labels(
                                    reason=decision.suppression_reason or "unknown"
                                ).inc()

            detect_phase_duration_seconds.observe(__import__("time").monotonic() - detect_t0)
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

    def _refresh_detect_inputs_for_expected_head(
        self,
        *,
        adapter: Any,
        key: ReviewRequestKey,
        review_run: ReviewRun,
        meta: ReviewRequestMeta,
        diff_payload: DiffPayload,
    ) -> tuple[ReviewRequestMeta, DiffPayload]:
        expected_head_sha = review_run.head_sha
        if review_run.trigger != "gitlab:note_mention" or not expected_head_sha:
            return meta, diff_payload

        observed_head_sha = diff_payload.pull_request.get("head_sha") or meta.head_sha
        if not observed_head_sha or observed_head_sha == expected_head_sha:
            return meta, diff_payload

        refreshed_meta = meta
        refreshed_diff = diff_payload
        for _ in range(_NOTE_MENTION_EXPECTED_HEAD_RETRIES):
            time.sleep(_NOTE_MENTION_EXPECTED_HEAD_SLEEP_SECONDS)
            refreshed_meta = adapter.fetch_review_request_meta(key)
            refreshed_diff = adapter.fetch_diff(
                key,
                mode=review_run.mode,
                base_sha=review_run.base_sha,
            )
            observed_head_sha = refreshed_diff.pull_request.get("head_sha") or refreshed_meta.head_sha
            if observed_head_sha == expected_head_sha:
                return refreshed_meta, refreshed_diff

        logger.warning(
            "detect_head_not_settled review_run_id=%s project_ref=%s review_request_id=%s expected_head_sha=%s observed_head_sha=%s",
            review_run.id,
            key.project_ref,
            key.review_request_id,
            expected_head_sha,
            observed_head_sha,
        )
        return refreshed_meta, refreshed_diff

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
            feedback_cache = self._load_feedback_cache(session, review_request.id)
            candidates = self._prepare_publication_candidates(
                session=session,
                review_run=review_run,
                review_request=review_request,
                decisions=eligible,
                feedback_cache=feedback_cache,
            )
            selected = self._select_batch_candidates(candidates)
            current_batch = (
                session.query(func.max(PublicationState.batch_no))
                .filter(PublicationState.review_request_pk == review_request.id)
                .scalar()
            ) or 0
            batch_no = int(current_batch) + 1
            publication_failures = 0
            successful_publications: list[PublicationCandidate] = []
            seen_publication_keys: set[tuple[str, int | None, str]] = set()
            noop_existing_candidates = [
                candidate
                for candidate in candidates
                if candidate.priority_group == 3 and not candidate.backlog_only
            ]
            backlog_counts: dict[str, int] = {}
            for candidate in candidates:
                if candidate.backlog_only and candidate.backlog_reason:
                    backlog_counts[candidate.backlog_reason] = (
                        backlog_counts.get(candidate.backlog_reason, 0) + 1
                    )
            suppressed_feedback_counts = self._suppressed_feedback_counts(session, review_run.id)

            self._log_run_event(
                "publish_candidates_built",
                review_run,
                eligible_count=len(eligible),
                selected_count=len(selected),
                noop_existing_count=len(noop_existing_candidates),
                backlog_counts=backlog_counts,
                suppressed_feedback_counts=suppressed_feedback_counts,
            )

            for candidate in candidates:
                if candidate.backlog_only and candidate.backlog_reason == "existing_open_thread":
                    candidate.decision.state = "published"
                    candidate.decision.publication_error = None

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
                        and existing_thread.resolution_reason != "remote_reopened"
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
                    findings_published_total.labels(
                        severity=decision.severity or "medium",
                        rule_family=decision.source_family or "unknown",
                    ).inc()
                    if result.action in {"created", "updated"}:
                        successful_publications.append(candidate)

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

            # PR 요약 생성 및 게시 (실제 created/updated 성공분만 반영)
            if successful_publications:
                self._post_pr_summary(
                    adapter=adapter,
                    key=key,
                    review_run=review_run,
                    published_candidates=successful_publications,
                    batch_no=batch_no,
                    backlog_counts=backlog_counts,
                    suppressed_feedback_counts=suppressed_feedback_counts,
                )

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
                review_request=review_request,
                key=key,
                adapter=adapter,
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
                        previous_head_sha = thread_state.last_seen_head_sha
                        thread_decision = self._decision_for_thread_state(session, thread_state)
                        thread_state.sync_status = "resolved"
                        thread_state.resolution_reason = "no_longer_eligible"
                        thread_state.last_seen_head_sha = review_run.head_sha
                        thread_state.last_synced_at = datetime.now(UTC)
                        if thread_decision is not None:
                            finding_resolution_events_total.labels(
                                rule_family=thread_decision.source_family or "unknown",
                                resolution_reason="no_longer_eligible",
                            ).inc()
                        self._record_finding_lifecycle_event(
                            session,
                            review_request=review_request,
                            thread_state=thread_state,
                            decision=thread_decision,
                            event_type="resolved",
                            event_reason="no_longer_eligible",
                            observed_head_sha=review_run.head_sha,
                            compared_from_sha=previous_head_sha,
                            payload={"mode": review_run.mode, "auto_resolved": True},
                        )
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
            run = self._latest_review_run_for_request(session, review_request.id)
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
        last_run = self._latest_review_run_for_request(session, review_request.id)
        published_batch_count = (
            session.query(func.count(func.distinct(PublicationState.batch_no)))
            .filter(
                PublicationState.review_request_pk == review_request.id,
                PublicationState.publish_state.in_(["created", "updated"]),
            )
            .scalar()
        ) or 0
        open_finding_count = (
            session.query(func.count(func.distinct(FindingDecision.fingerprint)))
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

    def build_full_report(
        self,
        session: Session,
        pr_id: int | None = None,
        *,
        key: ReviewRequestKey | None = None,
        view: Literal["full", "backlog"] = "full",
    ) -> dict[str, Any]:
        target_key = key or self._legacy_key(int(pr_id or 0))
        report = self._empty_full_report(target_key)
        review_request = self._find_review_request(session, target_key)
        if review_request is None:
            return report

        report["review_request_title"] = review_request.title
        last_run = self._latest_review_run_for_request(session, review_request.id)
        if last_run is not None:
            report["last_review_run_id"] = last_run.id
            report["last_status"] = last_run.status
            report["last_head_sha"] = last_run.head_sha or review_request.latest_head_sha
        report_run = self._latest_review_run_for_request(
            session,
            review_request.id,
            statuses=_REPORTABLE_REVIEW_RUN_STATUSES,
        )
        if report_run is not None:
            report["report_review_run_id"] = report_run.id
            report["report_status"] = report_run.status
            report["report_head_sha"] = report_run.head_sha or review_request.latest_head_sha
        in_flight_run = self._latest_review_run_for_request(
            session,
            review_request.id,
            statuses=_IN_FLIGHT_REVIEW_RUN_STATUSES,
        )
        if in_flight_run is not None and self._is_newer_run(in_flight_run, report_run):
            report["in_flight_review_run_id"] = in_flight_run.id
            report["in_flight_status"] = in_flight_run.status
            report["in_flight_head_sha"] = in_flight_run.head_sha or review_request.latest_head_sha

        feedback_cache = self._load_feedback_cache(session, review_request.id)
        counts = dict(report["counts"])
        latest_run_fingerprints: set[str] = set()

        if report_run is not None:
            decisions = (
                session.query(FindingDecision)
                .filter(FindingDecision.review_run_id == report_run.id)
                .order_by(FindingDecision.score_final.desc(), FindingDecision.created_at.asc())
                .all()
            )
            publications = self._latest_publications_for_decisions(
                session,
                [decision.id for decision in decisions],
            )

            for decision in decisions:
                existing_thread = self._find_existing_thread(
                    session,
                    review_request.id,
                    decision.fingerprint,
                    include_resolved=True,
                )
                reminder_candidate = self._should_resurface_open_thread(
                    review_run=report_run,
                    decision=decision,
                    existing_thread=existing_thread,
                )
                feedback_signal = self._feedback_signal(
                    session,
                    review_request.id,
                    decision.fingerprint,
                    feedback_cache=feedback_cache,
                )
                backlog_only, backlog_reason = self._classify_backlog(
                    existing_thread=existing_thread,
                    canonical_body_hash=self._sha256(self._render_comment(decision)),
                    decision=decision,
                    feedback_signal=feedback_signal,
                    reminder_candidate=reminder_candidate,
                )
                section = self._classify_full_report_section(
                    decision=decision,
                    publication=publications.get(decision.id),
                    backlog_only=backlog_only,
                    backlog_reason=backlog_reason,
                )
                if section is None:
                    # Resolved-unchanged / feedback:later cases are rendered
                    # via the current-state backlog view below.
                    continue
                counts[section] += 1
                latest_run_fingerprints.add(decision.fingerprint)
                report[section].append(
                    self._build_full_report_item(
                        decision=decision,
                        disposition=section,
                        existing_thread=existing_thread,
                        reason=self._full_report_reason(
                            decision=decision,
                            section=section,
                            backlog_reason=backlog_reason,
                            publication=publications.get(decision.id),
                        ),
                    )
                )

        # Backlog sections always come from the current ThreadSyncState so
        # they reflect what actually remains open on the MR rather than just
        # whatever was re-detected in the latest run.
        for entry in self._current_backlog_entries(
            session,
            review_request_pk=review_request.id,
            feedback_cache=feedback_cache,
        ):
            fingerprint = entry.thread.finding_fingerprint
            if fingerprint in latest_run_fingerprints:
                continue
            latest_decision = self._latest_decision_for_fingerprint(
                session,
                review_request_pk=review_request.id,
                fingerprint=fingerprint,
            )
            counts[entry.section] += 1
            report[entry.section].append(
                self._build_backlog_report_item(
                    section=entry.section,
                    thread=entry.thread,
                    decision=latest_decision,
                    reason=entry.reason,
                )
            )

        report["counts"] = counts
        return self._filter_full_report_view(report, view=view)

    def post_full_report_note(
        self,
        session: Session,
        *,
        key: ReviewRequestKey,
        adapter: Any | None = None,
    ) -> bool:
        target_adapter = adapter or self._get_adapter()
        if not hasattr(target_adapter, "post_general_note"):
            return False
        body = self._render_full_report_note(self.build_full_report(session, key=key))
        return self._publish_general_note(
            adapter=target_adapter,
            key=key,
            body=body,
            purpose="full-report",
        )

    def post_backlog_note(
        self,
        session: Session,
        *,
        key: ReviewRequestKey,
        adapter: Any | None = None,
    ) -> bool:
        target_adapter = adapter or self._get_adapter()
        if not hasattr(target_adapter, "post_general_note"):
            return False
        body = self._render_backlog_note(self.build_full_report(session, key=key, view="backlog"))
        return self._publish_general_note(
            adapter=target_adapter,
            key=key,
            body=body,
            purpose="backlog",
        )

    def post_help_note(
        self,
        *,
        key: ReviewRequestKey,
        adapter: Any | None = None,
    ) -> bool:
        target_adapter = adapter or self._get_adapter()
        if not hasattr(target_adapter, "post_general_note"):
            return False
        return self._publish_general_note(
            adapter=target_adapter,
            key=key,
            body=self._render_help_note(),
            purpose="help",
        )

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
        feedback_cache: tuple[dict, dict] | None = None,
        rule_weights: dict[str, float] | None = None,
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
        feedback_signal = self._feedback_signal(
            session, review_request.id, fingerprint, feedback_cache=feedback_cache
        )
        # 규칙 유효성 가중치 적용 (피드백 기반 학습)
        rule_no_str = str(result.get("rule_no") or "")
        if rule_weights and rule_no_str in rule_weights:
            score_raw = score_raw * rule_weights[rule_no_str]
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
        elif feedback_signal.wrong_language_requested:
            state = "suppressed"
            suppression_reason = "feedback:wrong_language"
        elif feedback_signal.false_positive_requested:
            state = "suppressed"
            suppression_reason = "feedback:false_positive"
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
            payload = dict(event.payload or {})
            parsed_command: ParsedFeedbackCommand | None = None
            if event.event_type == "reply" and event.actor_type == "human":
                parsed_command = self._feedback_command_from_payload(payload)
                if parsed_command is not None:
                    payload["feedback_command"] = parsed_command.command
                    if parsed_command.expected_language_id:
                        payload["expected_language_id"] = parsed_command.expected_language_id
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
                    payload=payload,
                    occurred_at=event.occurred_at,
                )
            )
            if parsed_command is not None:
                feedback_commands_total.labels(command=parsed_command.command).inc()

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
            findings_resolved_total.labels(rule_no=decision.rule_no or "unknown").inc()

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

    def _decision_for_thread_state(
        self,
        session: Session,
        thread_state: ThreadSyncState,
    ) -> FindingDecision | None:
        if thread_state.finding_decision_id:
            decision = session.get(FindingDecision, thread_state.finding_decision_id)
            if decision is not None:
                return decision
        return (
            session.query(FindingDecision)
            .filter(
                FindingDecision.review_request_pk == thread_state.review_request_pk,
                FindingDecision.fingerprint == thread_state.finding_fingerprint,
            )
            .order_by(FindingDecision.updated_at.desc(), FindingDecision.created_at.desc())
            .first()
        )

    def _record_finding_lifecycle_event(
        self,
        session: Session,
        *,
        review_request: ReviewRequest,
        thread_state: ThreadSyncState,
        decision: FindingDecision | None,
        event_type: str,
        event_reason: str | None,
        observed_head_sha: str | None,
        compared_from_sha: str | None,
        payload: dict[str, Any] | None = None,
        event_at: datetime | None = None,
    ) -> None:
        session.add(
            FindingLifecycleEvent(
                review_request_pk=review_request.id,
                review_system=review_request.review_system,
                project_ref=review_request.project_ref,
                review_request_id=review_request.review_request_id,
                finding_fingerprint=thread_state.finding_fingerprint,
                finding_decision_id=decision.id if decision is not None else None,
                adapter_thread_ref=thread_state.adapter_thread_ref,
                rule_no=decision.rule_no if decision is not None else None,
                rule_family=decision.source_family if decision is not None else None,
                file_path=(
                    decision.file_path
                    if decision is not None
                    else str((payload or {}).get("file_path") or "") or None
                ),
                event_type=event_type,
                event_reason=event_reason,
                observed_head_sha=observed_head_sha,
                compared_from_sha=compared_from_sha,
                payload=payload or {},
                event_at=event_at or datetime.now(UTC),
            )
        )

    def _classify_resolution_reason(
        self,
        session: Session,
        *,
        review_request: ReviewRequest,
        key: ReviewRequestKey | None,
        adapter: Any | None,
        thread_state: ThreadSyncState,
        decision: FindingDecision | None,
        observed_head_sha: str | None,
    ) -> tuple[str, dict[str, Any]]:
        del review_request, session
        previous_head_sha = thread_state.last_seen_head_sha
        anchor_payload = dict(decision.anchor_payload or {}) if decision is not None else {}
        file_path = str(anchor_payload.get("file_path") or (decision.file_path if decision else "") or "")
        candidate_line_nos = {
            int(line_no)
            for line_no in (anchor_payload.get("candidate_line_nos") or [])
            if line_no is not None
        }
        start_line = anchor_payload.get("start_line")
        end_line = anchor_payload.get("end_line")
        hunk_header = str(anchor_payload.get("hunk_header") or "")
        changed_line_digest = str(anchor_payload.get("changed_line_digest") or "")

        payload: dict[str, Any] = {
            "file_path": file_path or None,
            "candidate_line_nos": sorted(candidate_line_nos),
            "anchor_range": [start_line, end_line],
        }
        if not previous_head_sha or not observed_head_sha:
            payload["classifier_reason"] = "missing_head_sha"
            return "remote_resolved_manual_only", payload
        if previous_head_sha == observed_head_sha:
            payload["classifier_reason"] = "head_unchanged"
            return "remote_resolved_manual_only", payload
        if adapter is None or key is None or not file_path:
            payload["classifier_reason"] = "insufficient_context"
            return "remote_resolved_manual_only", payload

        try:
            diff_payload = adapter.fetch_diff(key, mode="incremental", base_sha=previous_head_sha)
        except Exception as exc:
            logger.warning(
                "resolution_classifier_failed thread_ref=%s error=%s",
                thread_state.adapter_thread_ref,
                exc,
            )
            payload["classifier_reason"] = "diff_fetch_failed"
            payload["classifier_error"] = str(exc)
            return "remote_resolved_manual_only", payload

        for file_item in diff_payload.files:
            changed_paths = {path for path in [file_item.path, file_item.old_path, file_item.new_path] if path}
            if file_path not in changed_paths:
                continue
            for review_unit in self._iter_review_units(file_item.patch):
                matched_by: str | None = None
                changed_candidates = set(review_unit.candidate_line_nos)
                if candidate_line_nos and changed_candidates.intersection(candidate_line_nos):
                    matched_by = "candidate_line_nos"
                elif (
                    start_line is not None
                    and end_line is not None
                    and any(int(start_line) <= line_no <= int(end_line) for line_no in changed_candidates)
                ):
                    matched_by = "anchor_range"
                elif hunk_header and review_unit.patch.splitlines() and review_unit.patch.splitlines()[0] == hunk_header:
                    matched_by = "hunk_header"
                elif changed_line_digest and self._sha1(review_unit.change_snippet) == changed_line_digest:
                    matched_by = "changed_line_digest"
                if matched_by is None:
                    continue
                payload.update(
                    {
                        "classifier_reason": "matched_incremental_diff",
                        "matched_by": matched_by,
                        "matched_file_path": file_item.path,
                        "matched_hunk_header": review_unit.patch.splitlines()[0]
                        if review_unit.patch.splitlines()
                        else None,
                    }
                )
                return "fixed_in_followup_commit", payload

        payload["classifier_reason"] = "no_matching_diff_evidence"
        return "remote_resolved_manual_only", payload

    def _reconcile_thread_snapshots(
        self,
        session: Session,
        *,
        review_request: ReviewRequest,
        key: ReviewRequestKey | None,
        adapter: Any | None,
        threads: dict[str, ThreadSnapshot],
        head_sha: str | None = None,
    ) -> None:
        if not threads:
            return
        tracked_threads = (
            session.query(ThreadSyncState)
            .filter(
                ThreadSyncState.review_request_pk == review_request.id,
                ThreadSyncState.sync_status.in_(["open", "stale", "resolved"]),
            )
            .all()
        )
        refreshed_at = datetime.now(UTC)
        for thread_state in tracked_threads:
            snapshot = threads.get(thread_state.adapter_thread_ref)
            if snapshot is None:
                continue
            previous_head_sha = thread_state.last_seen_head_sha
            thread_state.adapter_comment_ref = snapshot.comment_ref or thread_state.adapter_comment_ref
            thread_state.last_synced_at = refreshed_at
            if snapshot.resolved:
                if thread_state.sync_status != "resolved":
                    thread_decision = self._decision_for_thread_state(session, thread_state)
                    resolution_reason, classifier_payload = self._classify_resolution_reason(
                        session,
                        review_request=review_request,
                        key=key,
                        adapter=adapter,
                        thread_state=thread_state,
                        decision=thread_decision,
                        observed_head_sha=head_sha,
                    )
                    thread_state.sync_status = "resolved"
                    thread_state.resolution_reason = resolution_reason
                    thread_state.last_seen_head_sha = head_sha or thread_state.last_seen_head_sha
                    if thread_decision is not None:
                        finding_resolution_events_total.labels(
                            rule_family=thread_decision.source_family or "unknown",
                            resolution_reason=resolution_reason,
                        ).inc()
                    self._record_finding_lifecycle_event(
                        session,
                        review_request=review_request,
                        thread_state=thread_state,
                        decision=thread_decision,
                        event_type="resolved",
                        event_reason=resolution_reason,
                        observed_head_sha=head_sha,
                        compared_from_sha=previous_head_sha,
                        payload=classifier_payload,
                        event_at=snapshot.updated_at or refreshed_at,
                    )
                    self._mark_fingerprint_resolved(
                        session,
                        review_request.id,
                        thread_state.finding_fingerprint,
                    )
                else:
                    thread_state.last_seen_head_sha = head_sha or thread_state.last_seen_head_sha
                continue
            thread_state.last_seen_head_sha = head_sha or thread_state.last_seen_head_sha
            if thread_state.sync_status == "resolved":
                thread_decision = self._decision_for_thread_state(session, thread_state)
                thread_state.sync_status = "open"
                thread_state.resolution_reason = "remote_reopened"
                self._record_finding_lifecycle_event(
                    session,
                    review_request=review_request,
                    thread_state=thread_state,
                    decision=thread_decision,
                    event_type="reopened",
                    event_reason="remote_reopened",
                    observed_head_sha=head_sha,
                    compared_from_sha=previous_head_sha,
                    payload={"remote_resolved": False},
                    event_at=snapshot.updated_at or refreshed_at,
                )
                self._mark_fingerprint_reopened(
                    session,
                    review_request.id,
                    thread_state.finding_fingerprint,
                )
                continue
            if (
                thread_state.sync_status == "stale"
                and thread_state.resolution_reason != "anchor_changed"
            ):
                thread_state.sync_status = "open"
                thread_state.resolution_reason = None

    def _load_feedback_cache(
        self, session: Session, review_request_pk: str
    ) -> tuple[dict[str, list[str]], dict[str, list[Any]]]:
        """PR 전체 피드백 데이터를 일괄 로드한다 (N+1 방지)."""
        fp_to_threads: dict[str, list[str]] = {}
        for fp, thread_ref in (
            session.query(
                ThreadSyncState.finding_fingerprint,
                ThreadSyncState.adapter_thread_ref,
            )
            .filter(ThreadSyncState.review_request_pk == review_request_pk)
            .all()
        ):
            fp_to_threads.setdefault(fp, []).append(thread_ref)

        thread_to_events: dict[str, list[Any]] = {}
        all_refs = [r for refs in fp_to_threads.values() for r in refs]
        if all_refs:
            for event in (
                session.query(FeedbackEvent)
                .filter(
                    FeedbackEvent.review_request_pk == review_request_pk,
                    FeedbackEvent.adapter_thread_ref.in_(all_refs),
                )
                .all()
            ):
                thread_to_events.setdefault(event.adapter_thread_ref, []).append(event)

        return fp_to_threads, thread_to_events

    def _load_rule_effectiveness_weights(self, session: Session) -> dict[str, float]:
        """규칙별 인간 해소율을 기반으로 스코어 가중치를 계산한다.

        집계 단위는 row가 아니라 고유 finding(``fingerprint``)이다.
        같은 finding이 여러 run으로 반복 surfaced되더라도 1건으로 본다.

        human-resolve(개발자가 직접 resolve)만 긍정 신호로 사용한다.
        auto-resolve(no_longer_eligible)는 retrieval 품질과 무관하므로 제외한다.
        """
        human_resolved_fps: set[str] = {
            fp
            for (fp,) in session.query(ThreadSyncState.finding_fingerprint)
            .filter(
                ThreadSyncState.sync_status == "resolved",
                ThreadSyncState.resolution_reason.in_(
                    ["remote_resolved", "remote_resolved_manual_only"]
                ),
            )
            .all()
        }

        surfaced_fps_by_rule: dict[str, set[str]] = {}
        for fingerprint, row in self.latest_rule_effectiveness_states(session).items():
            if row.state not in _RULE_EFFECTIVENESS_SURFACED_STATES or not row.rule_no:
                continue
            surfaced_fps_by_rule.setdefault(row.rule_no, set()).add(fingerprint)

        weights: dict[str, float] = {}
        for rule_no, fingerprints in surfaced_fps_by_rule.items():
            total = len(fingerprints)
            if total < 5:  # 데이터 부족 시 중립
                continue
            human_res = sum(1 for fp in fingerprints if fp in human_resolved_fps)
            resolve_rate = human_res / total
            if resolve_rate >= 0.5:
                weights[rule_no] = min(1.2, 0.9 + resolve_rate * 0.6)
            else:
                weights[rule_no] = max(0.8, 0.8 + resolve_rate * 0.4)
        return weights

    def latest_rule_effectiveness_states(
        self,
        session: Session,
    ) -> dict[str, RuleEffectivenessFingerprintState]:
        """Return one latest meaningful state per fingerprint for analytics.

        We intentionally scan only meaningful states so a later no-op rerun
        (`eligible`/`candidate`/`stale`) does not hide an already surfaced
        finding, while a true reopen (`published` after `resolved`) still wins
        because it is the latest meaningful row.
        """

        rows = (
            session.query(
                FindingDecision.fingerprint,
                FindingDecision.project_ref,
                FindingDecision.rule_no,
                FindingDecision.source_family,
                FindingDecision.state,
            )
            .filter(FindingDecision.state.in_(_RULE_EFFECTIVENESS_MEANINGFUL_STATES))
            .order_by(FindingDecision.created_at.desc(), FindingDecision.id.desc())
            .all()
        )
        latest_by_fingerprint: dict[str, RuleEffectivenessFingerprintState] = {}
        for fingerprint, project_ref, rule_no, source_family, state in rows:
            if not fingerprint or fingerprint in latest_by_fingerprint:
                continue
            latest_by_fingerprint[fingerprint] = RuleEffectivenessFingerprintState(
                fingerprint=fingerprint,
                project_ref=project_ref or "",
                rule_no=rule_no or "",
                source_family=source_family or "unknown",
                state=state,
            )
        return latest_by_fingerprint

    def finding_outcomes(
        self,
        session: Session,
        *,
        project_ref: str | None = None,
        source_family: str | None = None,
        window: Literal["14d", "28d"] = "28d",
    ) -> dict[str, Any]:
        window_days = 14 if window == "14d" else 28
        boundary = datetime.now(UTC) - timedelta(days=window_days)
        latest_by_fp = {
            fingerprint: row
            for fingerprint, row in self.latest_rule_effectiveness_states(session).items()
            if (project_ref is None or row.project_ref == project_ref)
            and (source_family is None or row.source_family == source_family)
        }
        if not latest_by_fp:
            return {
                "window": window,
                "project_ref": project_ref,
                "source_family": source_family,
                "surfaced_distinct": 0,
                "resolved_distinct": 0,
                "fixed_distinct": 0,
                "manual_resolved_distinct": 0,
                "ignored_distinct": 0,
                "false_positive_distinct": 0,
                "reopened_distinct": 0,
                "surfaced_cohort_distinct": 0,
                "converted_cohort_distinct": 0,
                "fix_confirmation_rate": 0.0,
                "human_resolve_rate": 0.0,
                "false_positive_feedback_rate": 0.0,
                "fix_conversion_rate": 0.0,
            }

        allowed_fingerprints = set(latest_by_fp)
        publication_rows = (
            session.query(FindingDecision.fingerprint, PublicationState.published_at)
            .join(
                FindingDecision,
                PublicationState.finding_decision_id == FindingDecision.id,
            )
            .filter(
                FindingDecision.fingerprint.in_(allowed_fingerprints),
                PublicationState.publish_state.in_(["created", "updated", "skipped"]),
                PublicationState.published_at.isnot(None),
            )
            .all()
        )
        first_surfaced_at: dict[str, datetime] = {}
        for fingerprint, published_at in publication_rows:
            normalized_published_at = self._as_utc(published_at)
            if not fingerprint or normalized_published_at is None:
                continue
            current = first_surfaced_at.get(fingerprint)
            if current is None or normalized_published_at < current:
                first_surfaced_at[fingerprint] = normalized_published_at

        lifecycle_rows = (
            session.query(
                FindingLifecycleEvent.finding_fingerprint,
                FindingLifecycleEvent.event_type,
                FindingLifecycleEvent.event_reason,
                FindingLifecycleEvent.event_at,
            )
            .filter(FindingLifecycleEvent.finding_fingerprint.in_(allowed_fingerprints))
            .order_by(FindingLifecycleEvent.event_at.asc(), FindingLifecycleEvent.id.asc())
            .all()
        )
        first_fixed_at: dict[str, datetime] = {}
        latest_lifecycle_reason: dict[str, str | None] = {}
        latest_lifecycle_type: dict[str, str | None] = {}
        latest_lifecycle_marker: dict[str, tuple[datetime, str]] = {}
        reopened_fingerprints: set[str] = set()
        for fingerprint, event_type, event_reason, event_at in lifecycle_rows:
            if not fingerprint:
                continue
            normalized_event_at = self._as_utc(event_at)
            marker = (normalized_event_at or datetime.min.replace(tzinfo=UTC), event_type or "")
            if latest_lifecycle_marker.get(fingerprint, marker) <= marker:
                latest_lifecycle_marker[fingerprint] = marker
                latest_lifecycle_reason[fingerprint] = event_reason
                latest_lifecycle_type[fingerprint] = event_type
            if (
                event_type == "resolved"
                and event_reason == "fixed_in_followup_commit"
                and normalized_event_at is not None
            ):
                current = first_fixed_at.get(fingerprint)
                if current is None or normalized_event_at < current:
                    first_fixed_at[fingerprint] = normalized_event_at
            if event_type == "reopened":
                reopened_fingerprints.add(fingerprint)

        thread_rows = (
            session.query(ThreadSyncState.adapter_thread_ref, ThreadSyncState.finding_fingerprint)
            .filter(
                ThreadSyncState.finding_fingerprint.in_(allowed_fingerprints),
                ThreadSyncState.adapter_thread_ref.isnot(None),
            )
            .all()
        )
        thread_to_fingerprint = {
            thread_ref: fingerprint
            for thread_ref, fingerprint in thread_rows
            if thread_ref and fingerprint
        }
        latest_feedback_command: dict[str, str | None] = {}
        latest_feedback_marker: dict[str, tuple[datetime, str]] = {}
        if thread_to_fingerprint:
            feedback_rows = (
                session.query(
                    FeedbackEvent.adapter_thread_ref,
                    FeedbackEvent.payload,
                    FeedbackEvent.occurred_at,
                    FeedbackEvent.event_key,
                )
                .filter(
                    FeedbackEvent.adapter_thread_ref.in_(thread_to_fingerprint),
                    FeedbackEvent.actor_type == "human",
                    FeedbackEvent.event_type == "reply",
                )
                .all()
            )
            for thread_ref, payload, occurred_at, event_key in feedback_rows:
                if thread_ref is None:
                    continue
                command = self._latest_feedback_command(str((payload or {}).get("body") or ""))
                if command is None:
                    continue
                fingerprint = thread_to_fingerprint.get(thread_ref)
                if fingerprint is None:
                    continue
                normalized_occurred_at = self._as_utc(occurred_at)
                marker = (
                    normalized_occurred_at or datetime.min.replace(tzinfo=UTC),
                    event_key or "",
                )
                if latest_feedback_marker.get(fingerprint, marker) <= marker:
                    latest_feedback_marker[fingerprint] = marker
                    latest_feedback_command[fingerprint] = command

        cohort_fingerprints = {
            fingerprint
            for fingerprint, surfaced_at in first_surfaced_at.items()
            if surfaced_at >= boundary
        }
        resolved_fingerprints = {
            fingerprint
            for fingerprint in cohort_fingerprints
            if latest_by_fp.get(fingerprint) is not None
            and latest_by_fp[fingerprint].state == "resolved"
        }
        fixed_fingerprints = {
            fingerprint for fingerprint in cohort_fingerprints if fingerprint in first_fixed_at
        }
        manual_resolved_fingerprints = {
            fingerprint
            for fingerprint in resolved_fingerprints
            if latest_lifecycle_reason.get(fingerprint) == "remote_resolved_manual_only"
        }
        current_fixed_resolved_fingerprints = {
            fingerprint
            for fingerprint in resolved_fingerprints
            if latest_lifecycle_reason.get(fingerprint) == "fixed_in_followup_commit"
        }
        ignored_fingerprints = {
            fingerprint
            for fingerprint in cohort_fingerprints
            if latest_feedback_command.get(fingerprint) == "ignore"
        }
        false_positive_fingerprints = {
            fingerprint
            for fingerprint in cohort_fingerprints
            if latest_feedback_command.get(fingerprint) == "false-positive"
        }
        reopened_cohort_fingerprints = reopened_fingerprints & cohort_fingerprints
        converted_cohort_fingerprints = {
            fingerprint
            for fingerprint in cohort_fingerprints
            if fingerprint in first_fixed_at
            and first_fixed_at[fingerprint]
            <= first_surfaced_at[fingerprint] + timedelta(days=28)
        }

        surfaced_distinct = len(cohort_fingerprints)
        resolved_distinct = len(resolved_fingerprints)
        fixed_distinct = len(fixed_fingerprints)
        manual_resolved_distinct = len(manual_resolved_fingerprints)
        false_positive_distinct = len(false_positive_fingerprints)
        result = {
            "window": window,
            "project_ref": project_ref,
            "source_family": source_family,
            "surfaced_distinct": surfaced_distinct,
            "resolved_distinct": resolved_distinct,
            "fixed_distinct": fixed_distinct,
            "manual_resolved_distinct": manual_resolved_distinct,
            "ignored_distinct": len(ignored_fingerprints),
            "false_positive_distinct": false_positive_distinct,
            "reopened_distinct": len(reopened_cohort_fingerprints),
            "surfaced_cohort_distinct": surfaced_distinct if window == "28d" else 0,
            "converted_cohort_distinct": (
                len(converted_cohort_fingerprints) if window == "28d" else 0
            ),
            "fix_confirmation_rate": (
                round(
                    len(current_fixed_resolved_fingerprints) / resolved_distinct,
                    3,
                )
                if window == "14d" and resolved_distinct > 0
                else 0.0
            ),
            "human_resolve_rate": (
                round(manual_resolved_distinct / surfaced_distinct, 3)
                if window == "14d" and surfaced_distinct > 0
                else 0.0
            ),
            "false_positive_feedback_rate": (
                round(false_positive_distinct / surfaced_distinct, 3)
                if window == "14d" and surfaced_distinct > 0
                else 0.0
            ),
            "fix_conversion_rate": (
                round(len(converted_cohort_fingerprints) / surfaced_distinct, 3)
                if window == "28d" and surfaced_distinct > 0
                else 0.0
            ),
        }
        return result

    def wrong_language_feedback_analytics(
        self,
        session: Session,
        *,
        project_ref: str | None = None,
        window: Literal["14d", "28d"] = "28d",
    ) -> dict[str, Any]:
        window_days = 14 if window == "14d" else 28
        boundary = datetime.now(UTC) - timedelta(days=window_days)

        feedback_rows = (
            session.query(
                FeedbackEvent.adapter_thread_ref,
                FeedbackEvent.payload,
                FeedbackEvent.occurred_at,
                FeedbackEvent.event_key,
                FeedbackEvent.project_ref,
            )
            .filter(
                FeedbackEvent.actor_type == "human",
                FeedbackEvent.event_type == "reply",
            )
            .all()
        )

        filtered_feedback: list[tuple[str, dict[str, Any], datetime, str]] = []
        thread_refs: set[str] = set()
        for thread_ref, payload, occurred_at, event_key, feedback_project_ref in feedback_rows:
            if not thread_ref:
                continue
            if project_ref is not None and feedback_project_ref != project_ref:
                continue
            parsed = self._feedback_command_from_payload(payload)
            if parsed is None or parsed.command != "wrong-language":
                continue
            normalized_occurred_at = self._as_utc(occurred_at)
            if normalized_occurred_at is None or normalized_occurred_at < boundary:
                continue
            filtered_feedback.append(
                (
                    thread_ref,
                    dict(payload or {}),
                    normalized_occurred_at,
                    event_key or "",
                )
            )
            thread_refs.add(thread_ref)

        if not filtered_feedback:
            return {
                "window": window,
                "project_ref": project_ref,
                "total_events": 0,
                "distinct_threads": 0,
                "distinct_findings": 0,
                "top_language_pairs": [],
                "top_profiles": [],
                "top_paths": [],
                "triage_candidates": [],
            }

        publication_rows = (
            session.query(
                PublicationState.adapter_thread_ref,
                FindingDecision.fingerprint,
                FindingDecision.file_path,
                FindingEvidence.raw_engine_payload,
                PublicationState.updated_at,
                PublicationState.id,
            )
            .join(FindingDecision, PublicationState.finding_decision_id == FindingDecision.id)
            .join(FindingEvidence, FindingDecision.evidence_id == FindingEvidence.id)
            .filter(PublicationState.adapter_thread_ref.in_(thread_refs))
            .order_by(PublicationState.updated_at.desc(), PublicationState.id.desc())
            .all()
        )
        metadata_by_thread: dict[str, dict[str, Any]] = {}
        for (
            thread_ref,
            fingerprint,
            file_path,
            raw_engine_payload,
            _updated_at,
            _publication_id,
        ) in publication_rows:
            if not thread_ref or thread_ref in metadata_by_thread:
                continue
            payload = dict(raw_engine_payload or {})
            metadata_by_thread[thread_ref] = {
                "fingerprint": fingerprint,
                "file_path": file_path or "",
                "detected_language_id": str(payload.get("language_id") or "unknown"),
                "profile_id": str(payload.get("profile_id") or "").strip() or None,
                "context_id": str(payload.get("context_id") or "").strip() or None,
            }

        pair_counts: dict[tuple[str, str], int] = {}
        profile_counts: dict[tuple[str, str, str | None, str | None], int] = {}
        path_counts: dict[tuple[str, str, str], int] = {}
        fingerprints: set[str] = set()

        for thread_ref, payload, _occurred_at, _event_key in filtered_feedback:
            metadata = metadata_by_thread.get(thread_ref, {})
            detected_language_id = str(metadata.get("detected_language_id") or "unknown")
            expected_language_id = str(payload.get("expected_language_id") or "unknown").strip() or "unknown"
            profile_id = metadata.get("profile_id")
            context_id = metadata.get("context_id")
            file_path = str(metadata.get("file_path") or "")
            fingerprint = str(metadata.get("fingerprint") or "")

            pair_counts[(detected_language_id, expected_language_id)] = (
                pair_counts.get((detected_language_id, expected_language_id), 0) + 1
            )
            profile_key = (detected_language_id, expected_language_id, profile_id, context_id)
            profile_counts[profile_key] = profile_counts.get(profile_key, 0) + 1
            path_key = (
                detected_language_id,
                expected_language_id,
                self._feedback_path_bucket(file_path),
            )
            path_counts[path_key] = path_counts.get(path_key, 0) + 1
            if fingerprint:
                fingerprints.add(fingerprint)

        top_language_pairs = [
            {
                "detected_language_id": detected_language_id,
                "expected_language_id": expected_language_id,
                "count": count,
            }
            for (detected_language_id, expected_language_id), count in sorted(
                pair_counts.items(),
                key=lambda item: (-item[1], item[0][0], item[0][1]),
            )[:12]
        ]
        top_profiles = [
            {
                "detected_language_id": detected_language_id,
                "expected_language_id": expected_language_id,
                "profile_id": profile_id,
                "context_id": context_id,
                "count": count,
            }
            for (detected_language_id, expected_language_id, profile_id, context_id), count in sorted(
                profile_counts.items(),
                key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2] or "", item[0][3] or ""),
            )[:12]
        ]
        top_paths = [
            {
                "detected_language_id": detected_language_id,
                "expected_language_id": expected_language_id,
                "path_pattern": path_pattern,
                "count": count,
            }
            for (detected_language_id, expected_language_id, path_pattern), count in sorted(
                path_counts.items(),
                key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2]),
            )[:12]
        ]
        triage_candidates = self._build_wrong_language_triage_candidates(
            pair_counts=pair_counts,
            profile_counts=profile_counts,
            path_counts=path_counts,
        )

        return {
            "window": window,
            "project_ref": project_ref,
            "total_events": len(filtered_feedback),
            "distinct_threads": len(thread_refs),
            "distinct_findings": len(fingerprints),
            "top_language_pairs": top_language_pairs,
            "top_profiles": top_profiles,
            "top_paths": top_paths,
            "triage_candidates": triage_candidates,
        }

    def _feedback_signal(
        self,
        session: Session,
        review_request_pk: str,
        fingerprint: str,
        *,
        feedback_cache: tuple[dict, dict] | None = None,
    ) -> FeedbackSignal:
        if feedback_cache is not None:
            fp_to_threads, thread_to_events = feedback_cache
            thread_refs = fp_to_threads.get(fingerprint, [])
            events = [e for tr in thread_refs for e in thread_to_events.get(tr, [])]
        else:
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

        if not thread_refs:
            return FeedbackSignal()
        resolved_count = 0
        unresolved_count = 0
        human_reply_count = 0
        latest_command: str | None = None
        latest_expected_language_id: str | None = None
        latest_command_marker: tuple[datetime, str] | None = None

        for event in events:
            if event.event_type == "resolved":
                resolved_count += 1
            elif event.event_type == "unresolved":
                unresolved_count += 1
            elif event.event_type == "reply" and event.actor_type == "human":
                human_reply_count += 1
                parsed_command = self._feedback_command_from_payload(event.payload)
                if parsed_command is not None:
                    marker = (
                        event.occurred_at or datetime.min.replace(tzinfo=UTC),
                        str(getattr(event, "event_key", "") or ""),
                    )
                    if latest_command_marker is None or marker >= latest_command_marker:
                        latest_command = parsed_command.command
                        latest_expected_language_id = parsed_command.expected_language_id
                        latest_command_marker = marker

        return FeedbackSignal(
            resolved_count=resolved_count,
            unresolved_count=unresolved_count,
            human_reply_count=human_reply_count,
            ignore_requested=latest_command == "ignore",
            wrong_language_requested=latest_command == "wrong-language",
            false_positive_requested=latest_command == "false-positive",
            later_requested=latest_command == "later",
            allow_requested=latest_command == "allow",
            expected_language_id=latest_expected_language_id,
        )

    def _feedback_path_bucket(self, file_path: str) -> str:
        normalized = str(file_path or "").replace("\\", "/").strip("/")
        if not normalized:
            return "<unknown>"
        parts = [part for part in normalized.split("/") if part]
        name = Path(normalized).name.lower()
        suffix = Path(normalized).suffix.lower()
        if (
            suffix in _DOCS_EXTENSIONS
            or name in _DOCS_FILENAMES
            or parts[0].lower() in {"docs", "documentation", "wiki"}
        ):
            return "docs"
        if len(parts) == 1:
            return parts[0]
        if parts[0] == ".github":
            return "/".join(parts[: min(2, len(parts))])
        if parts[0] in {"app", "pages", "src", "db", "docs", "configs", "config"}:
            return parts[0]
        return parts[0]

    def _build_wrong_language_triage_candidates(
        self,
        *,
        pair_counts: dict[tuple[str, str], int],
        profile_counts: dict[tuple[str, str, str | None, str | None], int],
        path_counts: dict[tuple[str, str, str], int],
    ) -> list[dict[str, Any]]:
        best_path_by_pair: dict[tuple[str, str], tuple[str, int]] = {}
        for (detected_language_id, expected_language_id, path_pattern), count in path_counts.items():
            pair = (detected_language_id, expected_language_id)
            current = best_path_by_pair.get(pair)
            if current is None or count > current[1] or (
                count == current[1] and path_pattern < current[0]
            ):
                best_path_by_pair[pair] = (path_pattern, count)

        candidates: list[dict[str, Any]] = []
        for (detected_language_id, expected_language_id, profile_id, context_id), count in sorted(
            profile_counts.items(),
            key=lambda item: (-item[1], item[0][0], item[0][1], item[0][2] or "", item[0][3] or ""),
        )[:12]:
            pair = (detected_language_id, expected_language_id)
            path_pattern = best_path_by_pair.get(pair, ("<unknown>", 0))[0]
            candidates.append(
                {
                    "detected_language_id": detected_language_id,
                    "expected_language_id": expected_language_id,
                    "profile_id": profile_id,
                    "context_id": context_id,
                    "path_pattern": path_pattern,
                    "count": count,
                    "priority": self._wrong_language_priority(
                        pair_count=pair_counts.get(pair, count),
                        profile_id=profile_id,
                        context_id=context_id,
                    ),
                    "suggested_action": self._wrong_language_suggested_action(
                        detected_language_id=detected_language_id,
                        expected_language_id=expected_language_id,
                        profile_id=profile_id,
                        context_id=context_id,
                        path_pattern=path_pattern,
                    ),
                }
            )
        return candidates

    def _wrong_language_priority(
        self,
        *,
        pair_count: int,
        profile_id: str | None,
        context_id: str | None,
    ) -> str:
        if pair_count >= 3 or context_id is not None:
            return "high"
        if pair_count >= 2 or profile_id not in {None, "default"}:
            return "medium"
        return "low"

    def _wrong_language_suggested_action(
        self,
        *,
        detected_language_id: str,
        expected_language_id: str,
        profile_id: str | None,
        context_id: str | None,
        path_pattern: str,
    ) -> str:
        if path_pattern == "docs" or detected_language_id == "markdown":
            return (
                "문서 경로를 reviewable 대상에서 더 명확히 제외하고, "
                "유사 확장자/경로 예외 규칙을 detector backlog에 추가하세요."
            )
        if expected_language_id == "markdown":
            return (
                "문서형 경로가 아닌데 `markdown` 기대값이 들어왔습니다. "
                "detector 오분류인지, wrong-language reply 대상 thread가 맞는지 먼저 확인하고 "
                "feedback regression 예제를 함께 보강하세요."
            )
        if path_pattern in _CI_PATH_BUCKETS or context_id in _CI_CONTEXTS:
            return (
                "CI/workflow 경로 우선 분류를 다시 확인하고, "
                "workflow 전용 detector 힌트와 path rule을 보강하세요."
            )
        if path_pattern in {"db", "warehouse"} or context_id == "analytics":
            return (
                "DB/warehouse 경로 힌트를 다시 확인하고, "
                "SQL profile/context detector와 dialect 분기를 우선 재점검하세요."
            )
        if profile_id not in {None, "default"} or context_id is not None:
            return (
                f"`{detected_language_id}` -> `{expected_language_id}` 오분류가 "
                f"`{profile_id or 'default'}` / `{context_id or 'generic'}` 축에 모여 있습니다. "
                "framework/profile detector와 prompt routing을 함께 재검토하세요."
            )
        return (
            f"`{detected_language_id}` -> `{expected_language_id}` 오분류가 반복됩니다. "
            "path/content/shebang 힌트를 우선 재검토하고 wrong-language 샘플을 regression fixture로 추가하세요."
        )

    def _contains_feedback_command(self, body: str, command: str) -> bool:
        return any(parsed.command == command for parsed in self._feedback_commands(body))

    def _latest_feedback_command(self, body: str) -> str | None:
        latest = self._latest_feedback_command_details(body)
        return latest.command if latest is not None else None

    def _feedback_command_from_payload(
        self,
        payload: dict[str, Any] | None,
    ) -> ParsedFeedbackCommand | None:
        payload_dict = payload or {}
        command = str(payload_dict.get("feedback_command") or "").strip()
        if command:
            expected_language_id = str(payload_dict.get("expected_language_id") or "").strip() or None
            return ParsedFeedbackCommand(
                command=command,
                expected_language_id=expected_language_id,
            )
        return self._latest_feedback_command_details(str(payload_dict.get("body") or ""))

    def _latest_feedback_command_details(self, body: str) -> ParsedFeedbackCommand | None:
        latest: ParsedFeedbackCommand | None = None
        for parsed in self._feedback_commands(body):
            latest = parsed
        return latest

    def _feedback_commands(self, body: str) -> list[ParsedFeedbackCommand]:
        pattern = re.compile(
            r"(?im)^\s*(?:@|/)?(?:review-bot|bot)(?::|\s+)\s*"
            r"(?P<command>ignore|false-positive|later|allow|wrong-language)"
            r"(?:\s+(?P<argument>[a-z0-9_.\\/-]+))?(?:\s|$)"
        )
        commands: list[ParsedFeedbackCommand] = []
        for match in pattern.finditer(body):
            command = str(match.group("command"))
            expected_language_id = None
            if command == "wrong-language":
                expected_language_id = str(match.group("argument") or "").strip().lower() or None
            commands.append(
                ParsedFeedbackCommand(
                    command=command,
                    expected_language_id=expected_language_id,
                )
            )
        return commands

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

    def _latest_publications_for_decisions(
        self,
        session: Session,
        decision_ids: list[str],
    ) -> dict[str, PublicationState]:
        if not decision_ids:
            return {}
        publications = (
            session.query(PublicationState)
            .filter(PublicationState.finding_decision_id.in_(decision_ids))
            .order_by(PublicationState.updated_at.desc(), PublicationState.published_at.desc())
            .all()
        )
        latest_by_decision_id: dict[str, PublicationState] = {}
        for publication in publications:
            latest_by_decision_id.setdefault(publication.finding_decision_id, publication)
        return latest_by_decision_id

    def _empty_full_report(self, key: ReviewRequestKey) -> dict[str, Any]:
        return {
            "key": key,
            "review_request_title": None,
            "last_review_run_id": None,
            "last_status": None,
            "last_head_sha": None,
            "report_review_run_id": None,
            "report_status": None,
            "report_head_sha": None,
            "in_flight_review_run_id": None,
            "in_flight_status": None,
            "in_flight_head_sha": None,
            "generated_at": datetime.now(UTC),
            "counts": {section: 0 for section in _FULL_REPORT_SECTION_ORDER},
            **{section: [] for section in _FULL_REPORT_SECTION_ORDER},
        }

    def _filter_full_report_view(
        self,
        report: dict[str, Any],
        *,
        view: Literal["full", "backlog"],
    ) -> dict[str, Any]:
        if view == "full":
            return report
        counts = dict(report["counts"])
        for section in _FULL_REPORT_SECTION_ORDER:
            if section in _BACKLOG_ONLY_SECTION_ORDER:
                continue
            report[section] = []
            counts[section] = 0
        report["counts"] = counts
        return report

    def _classify_full_report_section(
        self,
        *,
        decision: FindingDecision,
        publication: PublicationState | None,
        backlog_only: bool,
        backlog_reason: str | None,
    ) -> str | None:
        """Classify a latest-run decision into a run-oriented report section.

        Returns None when the decision's canonical representation belongs to
        the current-state backlog view (resolved-unchanged / feedback-later);
        callers should skip those and let the backlog helper render them.
        """
        if decision.suppression_reason == "feedback:ignore":
            return "suppressed_feedback_ignore"
        if decision.suppression_reason == "feedback:false_positive":
            return "suppressed_feedback_false_positive"
        if decision.state == "failed_publication":
            return "failed_publication"
        if publication and publication.publish_state in {"created", "updated"}:
            return "published_inline"
        if backlog_only:
            if backlog_reason == "existing_open_thread":
                return "already_open"
            return None
        if decision.state == "suppressed":
            return "suppressed_other"
        if decision.state == "published":
            return "already_open"
        if decision.state == "eligible":
            return "pending_batch"
        return "suppressed_other"

    def _build_full_report_item(
        self,
        *,
        decision: FindingDecision,
        disposition: str,
        existing_thread: ThreadSyncState | None,
        reason: str | None,
    ) -> dict[str, Any]:
        return {
            "fingerprint": decision.fingerprint,
            "file_path": decision.file_path,
            "line_no": decision.line_no,
            "rule_no": decision.rule_no,
            "severity": decision.severity or "medium",
            "title": decision.title,
            "summary": decision.summary,
            "state": decision.state,
            "disposition": disposition,
            "reason": reason,
            "score_final": (
                round(float(decision.score_final), 3)
                if decision.score_final is not None
                else None
            ),
            "thread_ref": existing_thread.adapter_thread_ref if existing_thread else None,
        }

    def _build_backlog_report_item(
        self,
        *,
        section: str,
        thread: ThreadSyncState,
        decision: FindingDecision | None,
        reason: str | None,
    ) -> dict[str, Any]:
        return {
            "fingerprint": thread.finding_fingerprint,
            "file_path": decision.file_path if decision else "",
            "line_no": decision.line_no if decision else None,
            "rule_no": decision.rule_no if decision else "",
            "severity": (decision.severity if decision else None) or "medium",
            "title": decision.title if decision else None,
            "summary": decision.summary if decision else None,
            "state": decision.state if decision else "backlog",
            "disposition": section,
            "reason": reason,
            "score_final": (
                round(float(decision.score_final), 3)
                if decision and decision.score_final is not None
                else None
            ),
            "thread_ref": thread.adapter_thread_ref,
        }

    def _current_backlog_entries(
        self,
        session: Session,
        *,
        review_request_pk: str,
        feedback_cache: tuple[dict, dict] | None,
    ) -> list[BacklogEntry]:
        """Return backlog entries sourced from current ThreadSyncState.

        Dedupes by fingerprint (keeps the most recently updated thread) so
        repeated reruns for the same finding only count once.
        """
        threads = (
            session.query(ThreadSyncState)
            .filter(ThreadSyncState.review_request_pk == review_request_pk)
            .order_by(ThreadSyncState.updated_at.desc())
            .all()
        )
        seen: set[str] = set()
        entries: list[BacklogEntry] = []
        for thread in threads:
            fingerprint = thread.finding_fingerprint
            if not fingerprint or fingerprint in seen:
                continue
            if thread.sync_status not in {"open", "resolved"}:
                continue
            feedback_signal = self._feedback_signal(
                session,
                review_request_pk,
                fingerprint,
                feedback_cache=feedback_cache,
            )
            if feedback_signal.later_requested:
                section = "backlog_feedback_later"
                reason = "feedback:later"
            elif thread.sync_status == "open":
                if thread.resolution_reason == "remote_reopened":
                    # Reopened threads are actionable open findings handled by
                    # the run view (already_open / pending_batch); not backlog.
                    continue
                section = "backlog_existing_open"
                reason = "existing_open_thread"
            else:
                if self.settings.resolved_unchanged_resurface_enabled:
                    continue
                section = "backlog_resolved_unchanged"
                reason = "resolved_unchanged"
            seen.add(fingerprint)
            entries.append(
                BacklogEntry(
                    section=section,
                    thread=thread,
                    reason=reason,
                    feedback_signal=feedback_signal,
                )
            )
        return entries

    def _latest_decision_for_fingerprint(
        self,
        session: Session,
        *,
        review_request_pk: str,
        fingerprint: str,
    ) -> FindingDecision | None:
        return (
            session.query(FindingDecision)
            .filter(
                FindingDecision.review_request_pk == review_request_pk,
                FindingDecision.fingerprint == fingerprint,
            )
            .order_by(FindingDecision.created_at.desc(), FindingDecision.id.desc())
            .first()
        )

    def _full_report_reason(
        self,
        *,
        decision: FindingDecision,
        section: str,
        backlog_reason: str | None,
        publication: PublicationState | None,
    ) -> str | None:
        if section.startswith("backlog_"):
            return backlog_reason
        if section == "already_open":
            return publication.publish_state if publication else "already_open"
        if section.startswith("suppressed_feedback_"):
            return decision.suppression_reason
        if section == "suppressed_other":
            return decision.suppression_reason
        if section == "failed_publication":
            return publication.error_category if publication else decision.publication_error
        return None

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

    def _latest_review_run_for_request(
        self,
        session: Session,
        review_request_pk: str,
        *,
        statuses: tuple[str, ...] | None = None,
    ) -> ReviewRun | None:
        query = session.query(ReviewRun).filter(ReviewRun.review_request_pk == review_request_pk)
        if statuses is not None:
            query = query.filter(ReviewRun.status.in_(statuses))
        return query.order_by(ReviewRun.created_at.desc(), ReviewRun.id.desc()).first()

    def _is_newer_run(
        self,
        candidate: ReviewRun,
        baseline: ReviewRun | None,
    ) -> bool:
        if baseline is None:
            return True
        return self._run_sort_key(candidate) > self._run_sort_key(baseline)

    def _run_sort_key(self, review_run: ReviewRun) -> tuple[datetime, str]:
        created_at = review_run.created_at or datetime.min.replace(tzinfo=UTC)
        return (created_at, review_run.id)

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

    def _as_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _severity_from_score(self, score: float) -> str:
        if score >= 0.9:
            return "high"
        if score >= 0.75:
            return "medium"
        return "low"

    def _render_comment_language(self, decision: FindingDecision) -> str:
        payload = dict(decision.evidence.raw_engine_payload or {}) if decision.evidence else {}
        language_id = str(payload.get("language_id") or "unknown")
        return language_id

    def _render_runtime_metadata(self, decision: FindingDecision) -> list[str]:
        payload = dict(decision.evidence.raw_engine_payload or {}) if decision.evidence else {}
        profile_id = str(payload.get("profile_id") or "default")
        context_id = str(payload.get("context_id") or "").strip() or None
        dialect_id = str(payload.get("dialect_id") or "").strip() or None
        match_source = str(payload.get("language_match_source") or "").strip()
        source_label = {
            "explicit": "명시",
            "classified": "자동 분류",
            "default": "기본값",
            "unmatched": "미분류",
        }.get(match_source)

        detail_parts: list[str] = []
        if source_label and match_source != "classified":
            detail_parts.append(f"언어 판별 `{source_label}`")
        if profile_id != "default":
            detail_parts.append(f"프로필 `{profile_id}`")
        if context_id:
            detail_parts.append(f"컨텍스트 `{context_id}`")
        if dialect_id:
            detail_parts.append(f"다이얼렉트 `{dialect_id}`")

        lines: list[str] = []
        if detail_parts:
            lines.append("_" + " | ".join(detail_parts) + "_")
        lines.append("_오분류면 `@review-bot wrong-language <expected-language>`_")
        return lines

    def _render_comment(self, decision: FindingDecision) -> str:
        language_id = self._render_comment_language(decision)
        lines = [f"[봇 리뷰][{language_id}] {decision.title}", ""]

        # 증거 인용: 실제 코드 근거를 먼저 표시
        if decision.evidence_snippet:
            lines += [self._render_blockquote(decision.evidence_snippet), ""]

        lines.append(decision.summary or "")

        if decision.suggested_fix:
            lines.extend(["", "**권장 수정**", decision.suggested_fix])

        # Auto-fix: GitLab suggestion 블록 (신뢰도 높은 경우)
        if decision.auto_fix_lines:
            suggestion_body = "\n".join(decision.auto_fix_lines)
            lines.extend(["", "```suggestion", suggestion_body, "```"])

        lines.extend(["", *self._render_runtime_metadata(decision)])
        lines.extend(["", "---", "_이 코멘트는 자동 생성됩니다. 문제가 없다면 스레드를 Resolve 해주세요._"])
        return self._truncate_comment("\n".join(lines))

    def _render_reminder_comment(self, decision: FindingDecision) -> str:
        language_id = self._render_comment_language(decision)
        lines = [f"[봇 리뷰][{language_id}] {decision.title}", ""]
        if decision.evidence_snippet:
            lines += [self._render_blockquote(decision.evidence_snippet), ""]
        lines.append("이전 리뷰에서 지적했던 내용이 이번 전체 재검토에서도 계속 확인되었습니다.")
        if decision.summary:
            lines.extend(["", decision.summary])
        if decision.suggested_fix:
            lines.extend(["", "**권장 수정**", decision.suggested_fix])
        lines.extend(["", *self._render_runtime_metadata(decision)])
        lines.extend(["", "---", "_이 코멘트는 자동 생성됩니다. 문제가 없다면 스레드를 Resolve 해주세요._"])
        return self._truncate_comment("\n".join(lines))

    def _truncate_comment(self, body: str) -> str:
        if len(body) <= MAX_COMMENT_BODY:
            return body
        suffix = "\n\n...(내용이 잘렸습니다. 파일을 직접 확인하세요.)"
        return body[: MAX_COMMENT_BODY - len(suffix)] + suffix

    def _render_blockquote(self, value: str) -> str:
        lines = value.splitlines() or [value]
        return "\n".join("> " if not line.strip() else f"> {line}" for line in lines)

    def _truncate_general_note(self, body: str) -> str:
        if len(body) <= MAX_COMMENT_BODY:
            return body
        suffix = "\n\n...(일부 항목이 잘렸습니다. 필요하면 full-report/API로 전체를 확인하세요.)"
        return body[: MAX_COMMENT_BODY - len(suffix)] + suffix

    def _publish_general_note(
        self,
        *,
        adapter: Any,
        key: ReviewRequestKey,
        body: str,
        purpose: str,
    ) -> bool:
        note_body = self._truncate_general_note(
            self._attach_general_note_purpose(body=body, purpose=purpose)
        )
        upsert_general_note = getattr(adapter, "upsert_general_note", None)
        if callable(upsert_general_note):
            result = upsert_general_note(key, body=note_body, purpose=purpose)
            if result.get("ok"):
                return True
        adapter.post_general_note(key, note_body)
        return True

    def _attach_general_note_purpose(self, *, body: str, purpose: str) -> str:
        marker = render_general_note_purpose_marker(purpose)
        if marker in body:
            return body
        return f"{marker}\n{body}"

    def _post_pr_summary(
        self,
        *,
        adapter: Any,
        key: ReviewRequestKey,
        review_run: ReviewRun,
        published_candidates: list[PublicationCandidate],
        batch_no: int,
        backlog_counts: dict[str, int] | None = None,
        suppressed_feedback_counts: dict[str, int] | None = None,
    ) -> None:
        """신규 게시된 finding을 요약해 MR 일반 노트로 게시한다."""
        if not hasattr(adapter, "post_general_note"):
            return
        try:
            by_severity: dict[str, list[str]] = {}
            for cand in published_candidates:
                sev = cand.decision.severity or "medium"
                by_severity.setdefault(sev, []).append(
                    f"- `{cand.decision.file_path}` — {cand.draft.title}"
                )

            severity_order = ["critical", "high", "medium", "low"]
            lines = [f"## 🤖 자동 리뷰 결과 (배치 #{batch_no})", ""]
            for sev in severity_order:
                items = by_severity.get(sev, [])
                if not items:
                    continue
                emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                lines.append(f"### {emoji} {sev.upper()} ({len(items)}건)")
                lines.extend(items)
                lines.append("")
            lines += [
                "---",
                f"총 **{len(published_candidates)}개** 항목이 게시되었습니다.",
            ]
            if backlog_counts:
                backlog_existing = backlog_counts.get("existing_open_thread", 0)
                backlog_resolved = backlog_counts.get("resolved_unchanged", 0)
                backlog_later = backlog_counts.get("feedback:later", 0)
                if backlog_existing > 0:
                    lines.append(
                        f"기존 열린 이슈 {backlog_existing}개는 재게시하지 않고 backlog로 유지했습니다."
                    )
                if backlog_resolved > 0:
                    lines.append(
                        f"이미 Resolve된 동일 항목 {backlog_resolved}개는 inline으로 다시 올리지 않았습니다."
                    )
                if backlog_later > 0:
                    lines.append(f"사용자 피드백(`bot:later`)으로 보류된 항목: {backlog_later}개.")
            if suppressed_feedback_counts:
                ignored = suppressed_feedback_counts.get("feedback:ignore", 0)
                false_positive = suppressed_feedback_counts.get("feedback:false_positive", 0)
                feedback_summary_parts: list[str] = []
                if ignored > 0:
                    feedback_summary_parts.append(f"무시된 항목 {ignored}개")
                if false_positive > 0:
                    feedback_summary_parts.append(f"오탐으로 처리된 항목 {false_positive}개")
                if feedback_summary_parts:
                    lines.append(
                        "사용자 피드백으로 "
                        + ", ".join(feedback_summary_parts)
                        + "가 이번 run에서 suppress되었습니다."
                    )
            lines.append("전체 backlog가 필요하면 `@review-bot full-report`를 코멘트로 요청해 주세요.")
            lines.append("각 코멘트를 확인하고 수정 후 스레드를 **Resolve** 해주세요.")
            adapter.post_general_note(key, self._truncate_general_note("\n".join(lines)))
        except Exception as exc:
            logger.warning("pr_summary_failed error=%s", exc)

    def _render_full_report_note(self, report: dict[str, Any]) -> str:
        lines = ["## 🤖 자동 리뷰 Full Report", ""]
        if report.get("last_review_run_id") is None:
            lines.extend(
                [
                    "아직 이 MR에 대한 리뷰 결과가 없습니다.",
                    "`@review-bot review`로 먼저 리뷰를 실행한 뒤 다시 요청해 주세요.",
                ]
            )
            return "\n".join(lines)
        report_run_id = report.get("report_review_run_id")
        report_status = report.get("report_status")
        report_head_sha = report.get("report_head_sha")
        if report_run_id is None and report.get("last_status") in _REPORTABLE_REVIEW_RUN_STATUSES:
            report_run_id = report.get("last_review_run_id")
            report_status = report_status or report.get("last_status")
            report_head_sha = report_head_sha or report.get("last_head_sha")
        if report_run_id is None:
            lines.extend(
                [
                    "현재 더 새로운 리뷰 run이 진행 중이지만, 완료된 결과는 아직 없습니다.",
                    f"- 최신 run: `{report['last_review_run_id']}`",
                    f"- 상태: `{report.get('last_status') or 'unknown'}`",
                ]
            )
            if report.get("last_head_sha"):
                lines.append(f"- head sha: `{report['last_head_sha']}`")
            lines.extend(
                [
                    "",
                    "run이 끝난 뒤 다시 `@review-bot full-report`를 요청해 주세요.",
                ]
            )
            return self._truncate_general_note("\n".join(lines))

        lines.extend(
            [
                f"- 보고서 기준 run: `{report_run_id}`",
                f"- 보고서 상태: `{report_status or 'unknown'}`",
            ]
        )
        if report_head_sha:
            lines.append(f"- 보고서 head sha: `{report_head_sha}`")
        if report.get("last_review_run_id") != report_run_id:
            lines.append(
                f"- 최신 run: `{report['last_review_run_id']}` (`{report.get('last_status') or 'unknown'}`)"
            )
        if report.get("in_flight_review_run_id"):
            lines.append(
                f"- 진행 중 run: `{report['in_flight_review_run_id']}` (`{report.get('in_flight_status') or 'unknown'}`)"
            )
        if report.get("review_request_title"):
            lines.append(f"- 제목: {report['review_request_title']}")
        if report.get("in_flight_review_run_id"):
            lines.extend(
                [
                    "",
                    "현재 더 새로운 run이 진행 중이므로, 아래 내용은 가장 최근에 완료된 run 기준입니다.",
                ]
            )
        lines.extend(["", "### 요약"])

        counts = report.get("counts") or {}
        for section in _FULL_REPORT_SECTION_ORDER:
            count = int(counts.get(section, 0) or 0)
            if count <= 0:
                continue
            lines.append(f"- {_FULL_REPORT_SECTION_SUMMARY_LABELS[section]}: {count}개")

        for section in _FULL_REPORT_SECTION_ORDER:
            items = report.get(section) or []
            if not items:
                continue
            lines.extend(["", f"### {_FULL_REPORT_SECTION_TITLES[section]} ({len(items)}개)"])
            for item in items[:20]:
                location = item["file_path"]
                if item.get("line_no") is not None:
                    location += f":{item['line_no']}"
                severity = item.get("severity") or "medium"
                title = item.get("title") or item.get("rule_no") or "untitled"
                lines.append(f"- `{location}` [{severity}] {title}")
                if item.get("summary"):
                    lines.append(f"  - {item['summary']}")
                if item.get("reason"):
                    lines.append(f"  - reason: `{item['reason']}`")
            if len(items) > 20:
                lines.append(f"- ... 외 {len(items) - 20}개")

        lines.extend(
            [
                "",
                "필요하면 `@review-bot review`로 최신 diff를 다시 검사할 수 있습니다.",
            ]
        )
        return self._truncate_general_note("\n".join(lines))

    def _render_backlog_note(self, report: dict[str, Any]) -> str:
        lines = ["## 🤖 자동 리뷰 Backlog", ""]
        if report.get("last_review_run_id") is None:
            lines.extend(
                [
                    "아직 이 MR에 대한 리뷰 결과가 없습니다.",
                    "`@review-bot review`로 먼저 리뷰를 실행한 뒤 다시 요청해 주세요.",
                ]
            )
            return "\n".join(lines)

        counts = report.get("counts") or {}
        total_backlog = sum(
            int(counts.get(section, 0) or 0) for section in _BACKLOG_ONLY_SECTION_ORDER
        )
        if total_backlog == 0:
            lines.append("현재 MR에 남아 있는 backlog가 없습니다.")
            return self._truncate_general_note("\n".join(lines))

        lines.append("현재 남아 있는 backlog 현황입니다.")
        if report.get("in_flight_review_run_id"):
            lines.extend(
                [
                    "",
                    f"- 진행 중 run: `{report['in_flight_review_run_id']}` (`{report.get('in_flight_status') or 'unknown'}`)",
                    "- backlog는 현재 스레드 상태 기준으로 집계되었습니다.",
                ]
            )
        lines.extend(["", "### 요약"])
        for section in _BACKLOG_ONLY_SECTION_ORDER:
            count = int(counts.get(section, 0) or 0)
            if count <= 0:
                continue
            lines.append(f"- {_FULL_REPORT_SECTION_SUMMARY_LABELS[section]}: {count}개")

        for section in _BACKLOG_ONLY_SECTION_ORDER:
            items = report.get(section) or []
            if not items:
                continue
            lines.extend(["", f"### {_FULL_REPORT_SECTION_TITLES[section]} ({len(items)}개)"])
            for item in items[:20]:
                location = item.get("file_path") or ""
                if item.get("line_no") is not None:
                    location = f"{location}:{item['line_no']}" if location else f"L{item['line_no']}"
                severity = item.get("severity") or "medium"
                title = item.get("title") or item.get("rule_no") or "untitled"
                display_location = f"`{location}`" if location else ""
                prefix = f"- {display_location} " if display_location else "- "
                lines.append(f"{prefix}[{severity}] {title}")
                if item.get("summary"):
                    lines.append(f"  - {item['summary']}")
                if item.get("reason"):
                    lines.append(f"  - reason: `{item['reason']}`")
            if len(items) > 20:
                lines.append(f"- ... 외 {len(items) - 20}개")

        lines.extend(
            [
                "",
                "필요하면 `@review-bot full-report`로 이번 run 결과까지 함께 볼 수 있습니다.",
            ]
        )
        return self._truncate_general_note("\n".join(lines))

    def _render_help_note(self) -> str:
        lines = [
            "## 🤖 review-bot 사용법",
            "",
            "이 MR에서 다음 명령을 지원합니다.",
            "",
            "- `@review-bot review` — 최신 diff에 대해 리뷰를 실행합니다.",
            "- `@review-bot full-report` — 최신 run 결과와 현재 backlog를 함께 보여 줍니다.",
            "- `@review-bot backlog` — 현재 MR에 남아 있는 backlog만 보여 줍니다.",
            "- `@review-bot help` — 이 도움말을 보여 줍니다.",
            "",
            "스레드 댓글로 `bot:ignore`, `bot:false-positive`, `bot:later`, `bot:allow`,",
            "`@review-bot wrong-language <expected-language>`를 작성하면",
            "해당 finding에 대한 피드백으로 반영됩니다.",
            "",
            "멘션은 줄 시작에 있을 때만 인식됩니다. "
            "알 수 없는 명령은 안전을 위해 무시됩니다.",
        ]
        return self._truncate_general_note("\n".join(lines))

    def _suppressed_feedback_counts(self, session: Session, review_run_id: str) -> dict[str, int]:
        rows = (
            session.query(FindingDecision.suppression_reason, FindingDecision.fingerprint)
            .filter(
                FindingDecision.review_run_id == review_run_id,
                FindingDecision.suppression_reason.in_(
                    ["feedback:ignore", "feedback:false_positive"]
                ),
            )
            .all()
        )
        fingerprints_by_reason: dict[str, set[str]] = {}
        for reason, fingerprint in rows:
            if reason is None or fingerprint is None:
                continue
            fingerprints_by_reason.setdefault(reason, set()).add(fingerprint)
        return {
            reason: len(fingerprints)
            for reason, fingerprints in fingerprints_by_reason.items()
        }

    def _is_cpp_path(self, path: str) -> bool:
        return self.language_registry.resolve(file_path=path).language_id == "cpp"

    def _engine_review_diff(
        self,
        diff: str,
        *,
        top_k: int,
        file_path: str | None,
        file_context: str | None,
        language_id: str | None,
        profile_id: str | None,
        context_id: str | None,
        dialect_id: str | None,
    ) -> dict[str, Any]:
        try:
            return self.engine_client.review_diff(
                diff,
                top_k=top_k,
                file_path=file_path,
                file_context=file_context,
                language_id=language_id,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
            )
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            return self.engine_client.review_diff(
                diff,
                top_k=top_k,
                file_path=file_path,
                file_context=file_context,
            )

    def _fetch_file_context(
        self,
        adapter: Any,
        key: ReviewRequestKey,
        path: str,
        ref: str | None,
    ) -> str | None:
        if not ref:
            return None
        try:
            content = adapter.fetch_file_content(key, path, ref)
            if content:
                return content[:FILE_CONTEXT_MAX_CHARS]
        except Exception as exc:
            logger.debug("fetch_file_context_skipped path=%s error=%s", path, exc)
        return None

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
        feedback_cache: tuple[dict, dict] | None = None,
    ) -> list[PublicationCandidate]:
        candidates: list[PublicationCandidate] = []
        for decision in decisions:
            file_context = decision.evidence.raw_engine_payload.get(_FILE_CONTEXT_KEY)
            similar_code = decision.evidence.raw_engine_payload.get(_SIMILAR_CODE_KEY)
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
                file_context=file_context,
                language_id=decision.evidence.raw_engine_payload.get("language_id"),
                profile_id=decision.evidence.raw_engine_payload.get("profile_id"),
                context_id=decision.evidence.raw_engine_payload.get("context_id"),
                dialect_id=decision.evidence.raw_engine_payload.get("dialect_id"),
                prompt_overlay_refs=decision.evidence.raw_engine_payload.get("prompt_overlay_refs"),
                pr_title=review_request.title,
                pr_source_branch=review_request.source_branch,
                pr_target_branch=review_request.target_branch,
                similar_code=similar_code,
            )
            if not draft.should_publish:
                decision.state = "suppressed"
                decision.suppression_reason = "provider_should_not_publish"
                continue

            decision.title = draft.title
            decision.summary = draft.summary
            decision.suggested_fix = draft.suggested_fix
            decision.evidence_snippet = draft.evidence_snippet
            decision.auto_fix_lines = draft.auto_fix_lines or []
            verify_suppression = self._maybe_verify_draft(
                review_request=review_request,
                decision=decision,
                draft=draft,
            )
            if verify_suppression is not None:
                decision.state = "suppressed"
                decision.suppression_reason = verify_suppression
                continue
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

            publish_feedback = self._feedback_signal(
                session, review_request.id, decision.fingerprint, feedback_cache=feedback_cache
            )
            backlog_only, backlog_reason = self._classify_backlog(
                existing_thread=existing_thread,
                canonical_body_hash=base_body_hash,
                decision=decision,
                feedback_signal=publish_feedback,
                reminder_candidate=reminder_candidate,
            )

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
                        decision.line_no,
                        draft.title.strip(),
                    ),
                    same_line_category_key=self._same_line_category_key(decision),
                    priority_group=self._candidate_priority_group(
                        review_run=review_run,
                        decision=decision,
                        existing_thread=existing_thread,
                        canonical_body_hash=base_body_hash,
                        reminder_candidate=reminder_candidate,
                    ),
                    reminder_candidate=reminder_candidate,
                    backlog_only=backlog_only,
                    backlog_reason=backlog_reason,
                )
            )
        return self._suppress_same_line_category_equivalents(candidates)

    def _same_line_category_key(
        self,
        decision: FindingDecision,
    ) -> tuple[str, int, str] | None:
        if not decision.evidence:
            return None
        category = str(decision.evidence.raw_engine_payload.get("category") or "").strip()
        if not category or decision.line_no is None:
            return None
        return (decision.file_path, int(decision.line_no), category)

    def _suppress_same_line_category_equivalents(
        self,
        candidates: list[PublicationCandidate],
    ) -> list[PublicationCandidate]:
        grouped: dict[tuple[str, int, str], list[PublicationCandidate]] = {}
        for candidate in candidates:
            key = candidate.same_line_category_key
            if key is None or candidate.backlog_only:
                continue
            grouped.setdefault(key, []).append(candidate)

        suppressed_ids: set[int] = set()
        for group in grouped.values():
            if len(group) < 2:
                continue
            if len({candidate.publication_key for candidate in group}) < 2:
                continue

            winner = min(
                group,
                key=lambda candidate: (
                    candidate.priority_group,
                    -float(candidate.decision.score_final or 0.0),
                    candidate.decision.rule_no,
                ),
            )
            for candidate in group:
                if candidate is winner:
                    continue
                candidate.decision.state = "suppressed"
                candidate.decision.suppression_reason = "publish_batch_same_line_category"
                suppressed_ids.add(id(candidate))

        return [candidate for candidate in candidates if id(candidate) not in suppressed_ids]

    def _maybe_verify_draft(
        self,
        *,
        review_request: ReviewRequest,
        decision: FindingDecision,
        draft: FindingDraft,
    ) -> str | None:
        if not self.settings.verify_enabled:
            return None
        if not draft.should_publish or decision.state != "eligible":
            return None
        score_final = float(decision.score_final or 0.0)
        if (
            draft.confidence >= self.settings.verify_confidence_threshold
            and score_final
            >= self.settings.minimum_publish_score + self.settings.verify_score_band
        ):
            return None

        verify_attempts_total.labels(mode="llm_self_check").inc()
        try:
            result = self.provider.verify_draft(
                draft=draft,
                file_path=decision.file_path,
                rule_no=decision.rule_no,
                title=decision.title or decision.rule_no,
                summary=decision.summary or decision.rule_no,
                category=str(decision.evidence.raw_engine_payload.get("category") or ""),
                change_snippet=decision.evidence.change_snippet,
                line_no=decision.line_no,
                candidate_line_nos=tuple(decision.evidence.candidate_line_nos),
                file_context=decision.evidence.raw_engine_payload.get(_FILE_CONTEXT_KEY),
                language_id=decision.evidence.raw_engine_payload.get("language_id"),
                profile_id=decision.evidence.raw_engine_payload.get("profile_id"),
                context_id=decision.evidence.raw_engine_payload.get("context_id"),
                dialect_id=decision.evidence.raw_engine_payload.get("dialect_id"),
                prompt_overlay_refs=decision.evidence.raw_engine_payload.get("prompt_overlay_refs"),
                pr_title=review_request.title,
                pr_source_branch=review_request.source_branch,
                pr_target_branch=review_request.target_branch,
                similar_code=decision.evidence.raw_engine_payload.get(_SIMILAR_CODE_KEY),
            )
        except Exception as exc:
            logger.warning(
                "verify_failed_open fingerprint=%s rule_no=%s error=%s",
                decision.fingerprint,
                decision.rule_no,
                exc,
            )
            return None

        reason = self._normalize_verify_reason(result)
        if reason is None:
            return None
        if reason == "execution_error":
            logger.warning(
                "verify_execution_error_fail_open fingerprint=%s rule_no=%s",
                decision.fingerprint,
                decision.rule_no,
            )
            return None
        verify_dropped_total.labels(mode="llm_self_check", reason=reason).inc()
        return f"verify:{reason}"

    def _normalize_verify_reason(self, result: VerifyDraftResult) -> str | None:
        if result.applies:
            return None
        raw_reason = str(result.reason or "").strip().lower()
        if not raw_reason:
            return "low_confidence"

        normalized_reason = re.sub(r"[^a-z0-9]+", "_", raw_reason).strip("_")
        normalized_reason = {
            "not_real_bug": "not_a_real_bug",
            "no_real_bug": "not_a_real_bug",
            "execution_failed": "execution_error",
            "runtime_error": "execution_error",
        }.get(normalized_reason, normalized_reason)

        if normalized_reason in {
            "not_a_real_bug",
            "low_confidence",
            "pattern_mismatch",
            "execution_error",
        }:
            return normalized_reason
        return "low_confidence"

    def _classify_backlog(
        self,
        *,
        existing_thread: ThreadSyncState | None,
        canonical_body_hash: str,
        decision: FindingDecision,
        feedback_signal: FeedbackSignal,
        reminder_candidate: bool = False,
    ) -> tuple[bool, str | None]:
        if feedback_signal.later_requested:
            return True, "feedback:later"
        if existing_thread is None:
            return False, None
        same_anchor = existing_thread.anchor_signature == decision.anchor_signature
        same_body = existing_thread.body_hash == canonical_body_hash
        if existing_thread.sync_status == "open" and same_anchor and same_body:
            if existing_thread.resolution_reason == "remote_reopened":
                return False, None
            if reminder_candidate:
                return False, None
            return True, "existing_open_thread"
        if (
            existing_thread.sync_status == "resolved"
            and same_anchor
            and same_body
            and not self.settings.resolved_unchanged_resurface_enabled
        ):
            return True, "resolved_unchanged"
        return False, None

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
        if existing_thread.resolution_reason == "remote_reopened":
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
        if not self.settings.repeat_open_thread_reminder_enabled:
            return False
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
        file_counts: dict[str, int] = {}
        ordered_candidates = sorted(
            (
                candidate
                for candidate in candidates
                if candidate.priority_group != 3 and not candidate.backlog_only
            ),
            key=lambda candidate: (
                candidate.priority_group,
                -candidate.decision.score_final,
                candidate.decision.created_at,
                candidate.decision.file_path,
            ),
        )
        grouped_candidates: dict[int, dict[str, list[PublicationCandidate]]] = {}
        file_order_by_group: dict[int, list[str]] = {}
        for candidate in ordered_candidates:
            priority_group = candidate.priority_group
            file_path = candidate.decision.file_path
            group_bucket = grouped_candidates.setdefault(priority_group, {})
            if file_path not in group_bucket:
                group_bucket[file_path] = []
                file_order_by_group.setdefault(priority_group, []).append(file_path)
            group_bucket[file_path].append(candidate)

        # Keep priority-group ordering intact, then interleave by file so one file does not
        # monopolize the batch when several files surface similarly strong findings.
        for priority_group in sorted(grouped_candidates):
            active_files = list(file_order_by_group.get(priority_group, []))
            while active_files and len(selected) < self.settings.batch_size:
                progressed = False
                next_active_files: list[str] = []
                for file_path in active_files:
                    queue = grouped_candidates[priority_group][file_path]
                    while queue:
                        candidate = queue.pop(0)
                        decision = candidate.decision
                        file_title = (decision.file_path, decision.rule_no)
                        if file_title in seen_file_titles:
                            continue
                        file_counts.setdefault(decision.file_path, 0)
                        if file_counts[decision.file_path] >= self.settings.file_comment_cap:
                            queue.clear()
                            break
                        title_counts[decision.rule_no] = title_counts.get(decision.rule_no, 0)
                        if title_counts[decision.rule_no] >= self.settings.rule_family_cap:
                            continue
                        selected.append(candidate)
                        seen_file_titles.add(file_title)
                        title_counts[decision.rule_no] += 1
                        file_counts[decision.file_path] += 1
                        progressed = True
                        break
                    if (
                        queue
                        and file_counts.get(file_path, 0) < self.settings.file_comment_cap
                        and len(selected) < self.settings.batch_size
                    ):
                        next_active_files.append(file_path)
                    if len(selected) >= self.settings.batch_size:
                        break
                if not progressed:
                    break
                active_files = next_active_files
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
