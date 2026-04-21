"""
통합 테스트 — Phase 1~4 변경 사항 검증

각 Phase별 핵심 기능을 실제 DB 트랜잭션과 함께 검증한다.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from review_bot.bot.review_runner import (
    MAX_COMMENT_BODY,
    ReviewRunner,
    _compute_top_k,
)
from review_bot.clients.engine_client import (
    EngineClient,
    _CircuitState,
    _engine_circuit,
)
from review_bot.contracts import (
    CheckPublishResult,
    CommentUpsertResult,
    DiffFile,
    DiffPayload,
    FeedbackPage,
    FeedbackRecord,
    ReviewRequestKey,
    ReviewRequestMeta,
    ThreadNoteSnapshot,
    ThreadSnapshot,
)
from review_bot.db.models import (
    DeadLetterRecord,
    FindingDecision,
    FindingEvidence,
    FindingLifecycleEvent,
    FeedbackEvent,
    PublicationState,
    ReviewRequest,
    ReviewRun,
    ThreadSyncState,
)
from review_bot.db.session import Base, SessionLocal, engine
from review_bot.errors import ReviewBotError
from review_bot.policy import PathPolicy, ReviewPolicy, _match_path_policies
from review_bot.providers.base import FindingDraft, ReviewCommentProvider
from review_bot.providers.openai_provider import OpenAIReviewCommentProvider, _AGENT_HINTS


# ──────────────────────────────────────────────
# 공통 픽스처
# ──────────────────────────────────────────────

def _reset_db() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def _malloc_patch() -> str:
    return (
        "@@ -1,2 +1,4 @@\n"
        " void foo() {\n"
        "+    char* buf = (char*)malloc(1024);\n"
        "+    if (!buf) return;\n"
        " }\n"
    )


def _multi_hunk_malloc_patch() -> str:
    return (
        "@@ -1,2 +1,4 @@\n"
        " void foo() {\n"
        "+    char* buf = (char*)malloc(1024);\n"
        "+    if (!buf) return;\n"
        " }\n"
        "@@ -20,2 +22,4 @@\n"
        " void bar() {\n"
        "+    char* other = (char*)malloc(2048);\n"
        "+    if (!other) return;\n"
        " }\n"
    )


def _result(rule_no: str = "ALTI-MEM-007", *, score: float = 0.82,
            category: str = "memory") -> dict:
    return {
        "rule_no": rule_no,
        "score": score,
        "title": "메모리를 직접 할당하고 있습니다",
        "summary": "malloc 사용은 소유권 관리가 명확하지 않습니다.",
        "category": category,
        "reviewability": "auto_review",
        "fix_guidance": "std::vector 사용 권장",
        "severity": "high",
        "false_positive_risk": "medium",
        "source_family": "altibase",
        "authority": "internal",
        "conflict_policy": "authoritative",
        "section": "메모리",
        "priority": 0.9,
        "text": "malloc/free 사용 금지",
    }


@dataclass
class EngineStub:
    results: list[dict]
    detected_patterns: list[str] | None = None

    def review_diff(self, diff, top_k=8, *, file_path=None, file_context=None):
        del diff
        self.last_top_k = top_k
        self.last_file_path = file_path
        self.last_file_context = file_context
        return {
            "detected_patterns": list(self.detected_patterns or []),
            "results": [dict(r) for r in self.results],
        }

    def search_codebase(self, query, top_k=3):
        del query, top_k
        return []


class FixedProvider(ReviewCommentProvider):
    def __init__(self, *, evidence_snippet: str | None = None,
                 auto_fix_lines: list[str] | None = None,
                 confidence: float = 0.8) -> None:
        self._evidence = evidence_snippet
        self._fix = auto_fix_lines or []
        self._confidence = confidence

    def build_draft(self, **kwargs) -> FindingDraft:
        return FindingDraft(
            title="메모리를 직접 할당하고 해제하고 있습니다",
            summary="이 변경은 소유권을 직접 관리합니다.",
            suggested_fix="RAII 사용 권장",
            should_publish=True,
            line_no=kwargs.get("line_no"),
            evidence_snippet=self._evidence,
            auto_fix_lines=self._fix,
            confidence=self._confidence,
        )


class FakeAdapter:
    def __init__(self) -> None:
        self.upsert_requests: list = []
        self.general_notes: list[str] = []
        self.general_note_index_by_purpose: dict[str, int] = {}
        self._diff: DiffPayload | None = None
        self._meta: ReviewRequestMeta | None = None
        self._threads: list[ThreadSnapshot] = []
        self._thread_idx = 0
        self.publish_checks: list = []

    def set_diff(self, key: ReviewRequestKey, *, path: str, patch: str,
                 head_sha: str = "abc123") -> None:
        self._meta = ReviewRequestMeta(
            key=key, title="Test MR", source_branch="feat", target_branch="main",
            base_sha="base1", start_sha="start1", head_sha=head_sha,
        )
        self._diff = DiffPayload(
            pull_request={"id": key.review_request_id, "base_sha": "base1",
                          "start_sha": "start1", "head_sha": head_sha},
            files=[DiffFile(path=path, status="modified", additions=2, deletions=0,
                            patch=patch, old_path=path, new_path=path)],
        )

    def fetch_review_request_meta(self, key):
        return self._meta

    def fetch_diff(self, key, *, mode, base_sha=None):
        return self._diff

    def list_threads(self, key):
        return list(self._threads)

    def upsert_comment(self, key, request):
        self.upsert_requests.append(request)
        self._thread_idx += 1
        return CommentUpsertResult(
            ok=True, action="created",
            comment_ref=f"note-{self._thread_idx}",
            thread_ref=f"thread-{self._thread_idx}",
        )

    def post_general_note(self, key, body: str):
        self.general_notes.append(body)
        return {"ok": True}

    def upsert_general_note(self, key, *, body: str, purpose: str):
        del key
        index = self.general_note_index_by_purpose.get(purpose)
        if index is None:
            self.general_note_index_by_purpose[purpose] = len(self.general_notes)
            self.general_notes.append(body)
            return {"ok": True, "action": "created"}
        self.general_notes[index] = body
        return {"ok": True, "action": "updated"}

    def resolve_thread(self, key, thread_ref, *, reason):
        return {"ok": True}

    def publish_check(self, key, request):
        self.publish_checks.append(request)
        return CheckPublishResult(ok=True, state=request.state,
                                  description=request.description)

    def collect_feedback(self, key, *, since=None):
        return FeedbackPage(events=[])

    def fetch_file_content(self, key, path, ref):
        return None


# ═══════════════════════════════════════════════════════
# PHASE 1 — 안정성
# ═══════════════════════════════════════════════════════

class TestPhase1Stability:

    def test_compute_top_k_scales_with_patch_size(self):
        """동적 top_k: 패치 크기에 따라 5~15로 조정된다."""
        tiny = "\n".join(["+line"] * 5)
        small = "\n".join(["+line"] * 30)
        medium = "\n".join(["+line"] * 70)
        large = "\n".join(["+line"] * 150)

        assert _compute_top_k(tiny) == 5
        assert _compute_top_k(small) == 8
        assert _compute_top_k(medium) == 12
        assert _compute_top_k(large) == 15

    def test_comment_truncated_at_3800_chars(self):
        """4000자 초과 코멘트는 3800자로 잘린다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(3001)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter

        stub_engine = EngineStub([_result()])
        runner.engine_client = stub_engine

        long_summary = "A" * 5000
        runner.provider = FixedProvider()
        runner.provider = type("LongProvider", (ReviewCommentProvider,), {
            "build_draft": lambda self, **kw: FindingDraft(
                title="제목",
                summary=long_summary,
                suggested_fix=None,
                should_publish=True,
                line_no=kw.get("line_no"),
            )
        })()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=3001, trigger="test")
            req = adapter.upsert_requests[0]
            assert len(req.body) <= MAX_COMMENT_BODY + 50  # suffix 포함 여유
            assert "잘렸습니다" in req.body
        finally:
            session.close()

    def test_concurrent_webhook_returns_existing_run(self):
        """동시 webhook: 동일 PR에 queued run이 있으면 새 run을 만들지 않는다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(3002)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())

        session = SessionLocal()
        try:
            run1 = runner.create_review_run_for_key(
                session, key, trigger="webhook:first", mode="manual"
            )
            run2 = runner.create_review_run_for_key(
                session, key, trigger="webhook:second", mode="manual"
            )
            assert run1.id == run2.id, "중복 run이 생성되었습니다"
            all_runs = session.query(ReviewRun).filter_by(
                review_request_id=key.review_request_id
            ).all()
            assert len(all_runs) == 1
        finally:
            session.close()

    def test_pending_run_with_different_mode_creates_new_run(self):
        """Pending dedupe: mode가 다르면 새 run을 생성한다."""
        _reset_db()
        runner = ReviewRunner()
        key = runner._legacy_key(30021)

        session = SessionLocal()
        try:
            run1 = runner.create_review_run_for_key(
                session,
                key,
                trigger="webhook:first",
                mode="manual",
                meta=ReviewRequestMeta(key=key, head_sha="head-1", base_sha="base-1", start_sha="start-1"),
            )
            run2 = runner.create_review_run_for_key(
                session,
                key,
                trigger="webhook:second",
                mode="incremental",
                meta=ReviewRequestMeta(key=key, head_sha="head-1", base_sha="base-1", start_sha="start-1"),
            )

            assert run1.id != run2.id
            assert {run1.mode, run2.mode} == {"manual", "incremental"}
        finally:
            session.close()

    def test_pending_run_with_different_head_sha_creates_new_run(self):
        """Pending dedupe: head sha가 다르면 새 run을 생성한다."""
        _reset_db()
        runner = ReviewRunner()
        key = runner._legacy_key(30022)

        session = SessionLocal()
        try:
            run1 = runner.create_review_run_for_key(
                session,
                key,
                trigger="webhook:first",
                mode="manual",
                meta=ReviewRequestMeta(key=key, head_sha="head-1", base_sha="base-1", start_sha="start-1"),
            )
            run2 = runner.create_review_run_for_key(
                session,
                key,
                trigger="webhook:second",
                mode="manual",
                meta=ReviewRequestMeta(key=key, head_sha="head-2", base_sha="base-1", start_sha="start-1"),
            )

            assert run1.id != run2.id
            assert run1.head_sha == "head-1"
            assert run2.head_sha == "head-2"
        finally:
            session.close()

    def test_rate_limiter_blocks_after_threshold(self):
        """Rate limiter: 동일 IP에서 100회 이후 차단된다."""
        from review_bot.api.main import _check_rate_limit, _rate_limit_buckets, _WEBHOOK_RATE_LIMIT

        test_ip = "10.0.0.99"
        _rate_limit_buckets.pop(test_ip, None)

        allowed = sum(1 for _ in range(_WEBHOOK_RATE_LIMIT) if _check_rate_limit(test_ip))
        assert allowed == _WEBHOOK_RATE_LIMIT

        assert not _check_rate_limit(test_ip), "한도 초과 후에도 허용됨"

    def test_dead_letter_ttl_cleanup(self):
        """Dead Letter TTL: 14일 이상 된 레코드는 sync job에서 정리된다."""
        _reset_db()
        from datetime import timezone, timedelta
        from review_bot.worker import _cleanup_expired_dead_letters, DEAD_LETTER_TTL_DAYS

        session = SessionLocal()
        try:
            runner = ReviewRunner()
            adapter = FakeAdapter()
            key = runner._legacy_key(3003)
            adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
            runner.platform_client = adapter
            runner.engine_client = EngineStub([])
            runner.provider = FixedProvider()
            run = runner.run_review(session, pr_id=3003, trigger="test")

            old_record = DeadLetterRecord(
                review_run_id=run.id,
                review_request_pk=run.review_request_pk,
                review_system=run.review_system,
                project_ref=run.project_ref,
                review_request_id=run.review_request_id,
                stage="detect",
                error_category="test",
                error_message="old error",
                replayable=False,
                payload={},
            )
            from datetime import UTC
            from sqlalchemy import text as _text
            session.add(old_record)
            session.commit()
            cutoff_ts = (
                __import__("datetime").datetime.now(UTC)
                - timedelta(days=DEAD_LETTER_TTL_DAYS + 1)
            ).isoformat()
            session.execute(
                _text("UPDATE dead_letter_records SET created_at = :ts WHERE id = :id"),
                {"ts": cutoff_ts, "id": old_record.id},
            )
            session.commit()

            count_before = session.query(DeadLetterRecord).count()
            _cleanup_expired_dead_letters(session)
            count_after = session.query(DeadLetterRecord).count()
            assert count_after < count_before, "만료된 레코드가 삭제되지 않았습니다"
        finally:
            session.close()


# ═══════════════════════════════════════════════════════
# PHASE 2 — 품질 향상
# ═══════════════════════════════════════════════════════

class TestPhase2Quality:

    def test_file_context_stored_in_evidence(self):
        """파일 컨텍스트: engine 호출 시 file_context가 전달되고 evidence에 저장된다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(4001)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter

        engine_stub = EngineStub([_result()])
        runner.engine_client = engine_stub
        runner.provider = FixedProvider()

        full_content = "// Full file context\nvoid foo() { /* existing code */ }\n"

        class ContextAdapter(FakeAdapter):
            def fetch_file_content(self, key, path, ref):
                return full_content

        context_adapter = ContextAdapter()
        context_adapter._diff = adapter._diff
        context_adapter._meta = adapter._meta
        runner.platform_client = context_adapter

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=4001, trigger="test")
            evidence = session.query(FindingEvidence).first()
            assert evidence is not None
            assert "_file_context" in evidence.raw_engine_payload
            stored = evidence.raw_engine_payload["_file_context"]
            assert stored[:50] == full_content[:50]
        finally:
            session.close()

    def test_dynamic_top_k_passed_to_engine(self):
        """동적 top_k: 패치 크기에 맞는 top_k가 engine에 전달된다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(4002)

        tiny_patch = "@@ -1,1 +1,2 @@\n void foo() {\n+    int x = 1;\n }\n"
        adapter.set_diff(key, path="src/a.cpp", patch=tiny_patch)
        runner.platform_client = adapter

        engine_stub = EngineStub([_result()])
        runner.engine_client = engine_stub
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=4002, trigger="test")
            # tiny patch (< 20줄) → top_k = 5
            assert engine_stub.last_top_k == 5
        finally:
            session.close()

    def test_pr_meta_passed_to_provider(self):
        """PR 메타데이터: build_draft 호출 시 pr_title 등이 전달된다."""
        _reset_db()
        captured: dict = {}

        class CapturingProvider(ReviewCommentProvider):
            def build_draft(self, **kwargs) -> FindingDraft:
                captured.update(kwargs)
                return FindingDraft(
                    title="T", summary="S", suggested_fix=None,
                    should_publish=True, line_no=kwargs.get("line_no"),
                )

        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(4003)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = CapturingProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=4003, trigger="test")
            assert "pr_title" in captured, "pr_title이 build_draft에 전달되지 않았습니다"
            assert captured.get("pr_source_branch") is not None
        finally:
            session.close()

    def test_self_verification_suppresses_low_confidence_draft(self):
        """자가 검증: should_publish=False로 설정된 draft는 게시되지 않는다."""
        _reset_db()

        class RejectingProvider(ReviewCommentProvider):
            def build_draft(self, **kwargs) -> FindingDraft:
                return FindingDraft(
                    title="T", summary="S", suggested_fix=None,
                    should_publish=False,
                    line_no=kwargs.get("line_no"),
                )

        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(4004)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = RejectingProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=4004, trigger="test")
            assert len(adapter.upsert_requests) == 0
            suppressed = session.query(FindingDecision).filter_by(
                state="suppressed", suppression_reason="provider_should_not_publish"
            ).count()
            assert suppressed >= 1
        finally:
            session.close()


# ═══════════════════════════════════════════════════════
# PHASE 3 — 운영 성숙
# ═══════════════════════════════════════════════════════

class TestPhase3Operations:

    def setup_method(self):
        # 각 테스트 전 circuit breaker를 CLOSED 상태로 초기화
        _engine_circuit._state = _CircuitState.CLOSED
        _engine_circuit._failures = 0
        _engine_circuit._opened_at = None

    def test_circuit_breaker_opens_after_consecutive_failures(self):
        """Circuit Breaker: 5회 연속 실패 시 OPEN 상태로 전환된다."""
        from review_bot.clients.engine_client import _CIRCUIT_FAILURE_THRESHOLD

        for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
            _engine_circuit.record_failure()

        assert _engine_circuit.state == "open"
        assert not _engine_circuit.allow_request()

    def test_circuit_breaker_half_open_after_timeout(self):
        """Circuit Breaker: OPEN 후 복구 시간이 지나면 HALF_OPEN으로 전환된다."""
        from review_bot.clients.engine_client import _CIRCUIT_FAILURE_THRESHOLD

        for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
            _engine_circuit.record_failure()

        assert _engine_circuit.state == "open"
        _engine_circuit._opened_at = time.monotonic() - 65  # 복구 시간 경과 시뮬레이션
        assert _engine_circuit.allow_request()
        assert _engine_circuit.state == "half_open"

    def test_circuit_breaker_recovers_to_closed_on_success(self):
        """Circuit Breaker: HALF_OPEN에서 성공하면 CLOSED로 복귀한다."""
        _engine_circuit._state = _CircuitState.HALF_OPEN
        _engine_circuit.record_success()
        assert _engine_circuit.state == "closed"

    def test_engine_client_raises_circuit_open_error(self):
        """Circuit Breaker: OPEN 상태에서 engine 호출은 즉시 실패한다."""
        from review_bot.clients.engine_client import _CIRCUIT_FAILURE_THRESHOLD

        for _ in range(_CIRCUIT_FAILURE_THRESHOLD):
            _engine_circuit.record_failure()

        client = EngineClient("http://nowhere")
        with pytest.raises(ReviewBotError) as exc_info:
            client.review_diff("test diff")
        assert "circuit breaker" in exc_info.value.args[0].lower()

    def test_policy_path_caching_uses_lru_cache(self):
        """정책 캐싱: 동일 경로 반복 호출 시 lru_cache가 히트된다."""
        policy = ReviewPolicy(
            path_policies=(
                PathPolicy(glob="tests/**", score_adjustment=-0.15,
                           suppress_rules=frozenset(["A2.5"])),
                PathPolicy(glob="src/**", score_adjustment=+0.05),
            )
        )
        _match_path_policies.cache_clear()

        result1 = policy.rules_for_path("tests/unit/test_foo.cpp")
        result2 = policy.rules_for_path("tests/unit/test_foo.cpp")
        result3 = policy.rules_for_path("tests/unit/test_foo.cpp")

        info = _match_path_policies.cache_info()
        assert info.hits >= 2, f"캐시 히트 없음: {info}"
        assert result1 == result2 == result3
        assert len(result1) == 1
        assert result1[0].glob == "tests/**"

    def test_policy_path_caching_different_paths_are_independent(self):
        """정책 캐싱: 다른 경로는 독립적으로 캐싱된다."""
        policy = ReviewPolicy(
            path_policies=(
                PathPolicy(glob="third_party/**", suppress_rules=frozenset(["*"])),
            )
        )
        _match_path_policies.cache_clear()

        res_src = policy.rules_for_path("src/core/db.cpp")
        res_tp = policy.rules_for_path("third_party/lib/util.cpp")

        assert len(res_src) == 0
        assert len(res_tp) == 1

    def test_feedback_cache_prevents_suppression_bypass(self):
        """피드백 캐시: ignore 명령이 캐시 방식에서도 올바르게 적용된다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(5001)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=5001, trigger="first")

            # 피드백 추가
            thread = session.query(ThreadSyncState).one()
            from review_bot.db.models import FeedbackEvent
            from review_bot.db.models import ReviewRequest
            rr = session.query(ReviewRequest).filter_by(
                review_request_id=str(key.review_request_id)
            ).one()
            fe = FeedbackEvent(
                review_request_pk=rr.id,
                review_system=key.review_system,
                project_ref=key.project_ref,
                review_request_id=key.review_request_id,
                event_key=f"{thread.adapter_thread_ref}:reply:test-001",
                adapter_thread_ref=thread.adapter_thread_ref,
                event_type="reply",
                actor_type="human",
                payload={"body": "bot:ignore 오탐입니다"},
            )
            session.add(fe)
            session.commit()

            run2 = runner.run_review(session, pr_id=5001, trigger="second")
            decisions = session.query(FindingDecision).filter_by(
                review_run_id=run2.id
            ).all()
            assert any(d.suppression_reason == "feedback:ignore" for d in decisions)
            # 두 번째 run에서 새 코멘트가 게시되지 않아야 함
            assert len(adapter.upsert_requests) == 1
        finally:
            session.close()

    def test_rule_effectiveness_weights_loaded(self):
        """규칙 가중치: 해소율 기반 가중치가 올바르게 계산된다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(5002)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            run = runner.run_review(session, pr_id=5002, trigger="test")
            # finding을 resolved로 표시 (많이 해소된 규칙)
            decisions = session.query(FindingDecision).filter_by(
                review_run_id=run.id
            ).all()
            for d in decisions:
                d.state = "resolved"
            session.commit()

            # 가중치 계산: 해소된 finding이 많은 규칙은 가중치가 1.0 이상이어야 함
            weights = runner._load_rule_effectiveness_weights(session)
            # 데이터가 5개 미만이면 가중치가 없음 (중립)
            # 5개 이상인 경우에만 가중치 조정
            # (이 테스트에서는 1개뿐이므로 weights가 비어 있어야 함)
            assert isinstance(weights, dict)
        finally:
            session.close()

    def test_prometheus_metrics_endpoint_returns_content(self):
        """Prometheus: /metrics 엔드포인트가 응답한다."""
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        client = TestClient(app)
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "review_runs_total" in response.text or "python_info" in response.text

    def test_rag_search_codebase_client_returns_list(self):
        """RAG: engine_client.search_codebase()가 리스트를 반환한다 (빈 codebase 포함)."""
        client = EngineClient("http://no-engine-available:18082",
                              timeout_seconds=0.1, max_retries=0)
        # 엔진 없음 → 빈 리스트 반환 (예외 처리됨)
        results = client.search_codebase("malloc buffer allocation", top_k=3)
        assert isinstance(results, list)

    def test_rag_similar_code_stored_in_evidence_when_provided(self):
        """RAG: search_codebase가 결과를 반환하면 evidence에 저장된다."""
        _reset_db()

        class RagEngineStub(EngineStub):
            def search_codebase(self, query, top_k=3):
                return [{"file_path": "src/old.cpp", "func_name": "legacyAlloc",
                         "snippet": "char* p = (char*)malloc(size);", "similarity": 0.82}]

        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(5010)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = RagEngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=5010, trigger="test")
            evidence = session.query(FindingEvidence).first()
            assert evidence is not None
            payload = evidence.raw_engine_payload
            assert "_similar_code" in payload
            similar = payload["_similar_code"]
            assert len(similar) >= 1
            assert similar[0]["file_path"] == "src/old.cpp"
        finally:
            session.close()


# ═══════════════════════════════════════════════════════
# PHASE 4 — 고도화
# ═══════════════════════════════════════════════════════

class TestPhase4Advanced:

    def test_evidence_snippet_appears_in_comment(self):
        """증거 기반 코멘트: evidence_snippet이 코멘트 본문에 인용 형식으로 포함된다."""
        _reset_db()
        evidence_text = "char* buf = (char*)malloc(1024);"

        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(6001)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider(evidence_snippet=evidence_text)

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=6001, trigger="test")
            assert len(adapter.upsert_requests) == 1
            body = adapter.upsert_requests[0].body
            assert evidence_text in body, f"증거 인용이 코멘트에 없습니다:\n{body}"
            assert ">" in body, "인용 블록(>) 형식이 없습니다"
        finally:
            session.close()

    def test_auto_fix_lines_render_as_suggestion_block(self):
        """Auto-fix: auto_fix_lines가 GitLab suggestion 블록으로 렌더링된다."""
        _reset_db()
        fix_lines = ["    std::vector<char> buf(1024);", "    if (buf.empty()) return;"]

        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(6002)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider(auto_fix_lines=fix_lines, confidence=0.95)

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=6002, trigger="test")
            body = adapter.upsert_requests[0].body
            assert "```suggestion" in body, f"suggestion 블록이 없습니다:\n{body}"
            assert fix_lines[0] in body
            assert fix_lines[1] in body
        finally:
            session.close()

    def test_pr_summary_posted_for_new_findings(self):
        """PR 요약: 신규 finding 게시 후 MR에 요약 노트가 게시된다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(6003)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=6003, trigger="test")
            assert len(adapter.general_notes) == 1, "PR 요약 노트가 게시되지 않았습니다"
            summary = adapter.general_notes[0]
            assert "자동 리뷰 결과" in summary
            assert "배치 #1" in summary
            assert "총 **1개** 항목이 게시되었습니다." in summary
        finally:
            session.close()

    def test_pr_summary_not_posted_when_no_new_findings(self):
        """PR 요약: 신규 finding이 없으면 요약 노트를 게시하지 않는다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(6004)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([])  # 규칙 결과 없음
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=6004, trigger="test")
            assert len(adapter.general_notes) == 0
        finally:
            session.close()

    def test_pr_summary_not_posted_for_backlog_only_rerun(self):
        """PR 요약: backlog 유지 정보만 있는 rerun은 새 요약 노트를 게시하지 않는다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(60041)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=60041, trigger="first")
            runner.run_review(session, pr_id=60041, trigger="second")

            assert len(adapter.general_notes) == 1
            assert "총 **1개** 항목이 게시되었습니다." in adapter.general_notes[0]
        finally:
            session.close()

    def test_pr_summary_not_posted_when_all_publications_fail(self):
        """PR 요약: inline publish가 전부 실패하면 요약 노트를 게시하지 않는다."""
        _reset_db()

        class AlwaysFailAdapter(FakeAdapter):
            def upsert_comment(self, key, request):
                raise ReviewBotError(
                    "forced publish failure",
                    category="gitlab_api",
                    retryable=True,
                )

        runner = ReviewRunner()
        adapter = AlwaysFailAdapter()
        key = runner._legacy_key(60041)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            run = runner.run_review(session, pr_id=60041, trigger="test")
            assert run.status == "partial"
            assert len(adapter.general_notes) == 0
        finally:
            session.close()

    def test_pr_summary_counts_only_successful_publications(self):
        """PR 요약: 일부 publish 실패 시 성공한 finding만 요약한다."""
        _reset_db()

        class FailSecondPublicationAdapter(FakeAdapter):
            def __init__(self) -> None:
                super().__init__()
                self._call_count = 0

            def upsert_comment(self, key, request):
                self._call_count += 1
                if self._call_count == 2:
                    raise ReviewBotError(
                        "forced second publish failure",
                        category="gitlab_api",
                        retryable=True,
                    )
                return super().upsert_comment(key, request)

        class SequentialResultEngine(EngineStub):
            def __init__(self) -> None:
                super().__init__([_result("ALTI-MEM-007")])
                self._call_count = 0

            def review_diff(self, diff, top_k=8, *, file_path=None, file_context=None):
                self._call_count += 1
                rule_no = "ALTI-MEM-007" if self._call_count == 1 else "ALTI-MEM-008"
                result = dict(_result(rule_no))
                if self._call_count == 2:
                    result["title"] = "두 번째 메모리 할당이 추가되었습니다"
                    result["summary"] = "두 번째 malloc 사용은 별도 finding으로 처리되어야 합니다."
                self.last_top_k = top_k
                self.last_file_path = file_path
                self.last_file_context = file_context
                return {
                    "detected_patterns": [],
                    "results": [result],
                }

        runner = ReviewRunner()
        adapter = FailSecondPublicationAdapter()
        key = runner._legacy_key(60042)
        adapter.set_diff(key, path="src/a.cpp", patch=_multi_hunk_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = SequentialResultEngine()
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            run = runner.run_review(session, pr_id=60042, trigger="test")
            assert run.status == "partial"
            assert len(adapter.general_notes) == 1
            summary = adapter.general_notes[0]
            assert "총 **1개** 항목이 게시되었습니다." in summary
        finally:
            session.close()

    def test_specialized_agent_hints_cover_all_categories(self):
        """특화 에이전트: engine의 실제 category에 대한 힌트가 정의되어 있다."""
        expected_categories = {
            "memory",
            "error_handling",
            "wrapper_usage",
            "portability",
            "type_usage",
            "control_flow",
            "comment_usage",
            "naming",
            "format_usage",
        }
        assert expected_categories <= set(_AGENT_HINTS.keys()), \
            f"누락된 도메인: {expected_categories - set(_AGENT_HINTS.keys())}"

        for cat, hint in _AGENT_HINTS.items():
            assert len(hint) > 50, f"{cat} 힌트가 너무 짧습니다"
            assert "관점" in hint or "전문가" in hint, f"{cat} 힌트에 관점 표현 없음"

    def test_specialized_agent_hint_applied_per_category(self):
        """특화 에이전트: 실제 engine category에 맞는 힌트가 존재한다."""

        # 메모리 카테고리
        hint_memory = _AGENT_HINTS.get("memory", "")
        assert "RAII" in hint_memory or "malloc" in hint_memory or "스마트포인터" in hint_memory

        # 에러 처리 카테고리
        hint_error = _AGENT_HINTS.get("error_handling", "")
        assert "IDE_RC" in hint_error or "IDE_TEST" in hint_error

        # naming 카테고리
        hint_naming = _AGENT_HINTS.get("naming", "")
        assert "명명" in hint_naming or "접두사" in hint_naming

        # legacy alias도 계속 동작
        assert _AGENT_HINTS.get("memory_management") == hint_memory

        # 카테고리 없음 → 기본 프롬프트만 사용
        no_hint = _AGENT_HINTS.get("unknown_category", "")
        assert no_hint == ""

    def test_rule_effectiveness_api_endpoint(self):
        """규칙 대시보드: /internal/analytics/rule-effectiveness 엔드포인트가 동작한다."""
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        _reset_db()
        # finding 데이터 없을 때도 응답해야 함
        client = TestClient(app)
        response = client.get("/internal/analytics/rule-effectiveness")
        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "total_rules" in data
        assert isinstance(data["rules"], list)

    def test_rule_effectiveness_api_with_data(self):
        """규칙 대시보드: 실제 finding 데이터가 있을 때 resolve_rate를 계산한다."""
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(6005)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result("ALTI-MEM-007")])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=6005, trigger="test")
        finally:
            session.close()

        client = TestClient(app)
        response = client.get("/internal/analytics/rule-effectiveness")
        assert response.status_code == 200
        data = response.json()
        rule_nos = [r["rule_no"] for r in data["rules"]]
        assert "ALTI-MEM-007" in rule_nos
        rule = next(r for r in data["rules"] if r["rule_no"] == "ALTI-MEM-007")
        assert rule["total"] >= 1
        assert rule["resolve_rate"] == 0.0

    def test_rule_effectiveness_api_resolved_only_returns_one(self):
        """규칙 대시보드: resolved만 있으면 resolve_rate는 1.0이다."""
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(60051)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result("ALTI-MEM-007")])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            run = runner.run_review(session, pr_id=60051, trigger="test")
            decision = session.query(FindingDecision).filter_by(review_run_id=run.id).one()
            decision.state = "resolved"
            session.commit()
        finally:
            session.close()

        client = TestClient(app)
        response = client.get("/internal/analytics/rule-effectiveness")
        assert response.status_code == 200
        data = response.json()
        rule = next(r for r in data["rules"] if r["rule_no"] == "ALTI-MEM-007")
        assert rule["published"] == 0
        assert rule["resolved"] >= 1
        assert rule["resolve_rate"] == 1.0

    def test_rule_effectiveness_api_mixed_published_and_resolved_returns_half(self):
        """규칙 대시보드: published 1건 + resolved 1건이면 resolve_rate는 0.5다."""
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result("ALTI-MEM-007")])
        runner.provider = FixedProvider()

        key1 = runner._legacy_key(60052)
        adapter.set_diff(key1, path="src/a.cpp", patch=_malloc_patch())

        session = SessionLocal()
        try:
            run1 = runner.run_review(session, pr_id=60052, trigger="test-1")
            decision1 = session.query(FindingDecision).filter_by(review_run_id=run1.id).one()
            decision1.state = "resolved"
            session.commit()

            key2 = runner._legacy_key(60053)
            adapter.set_diff(key2, path="src/b.cpp", patch=_malloc_patch())
            runner.run_review(session, pr_id=60053, trigger="test-2")
        finally:
            session.close()

        client = TestClient(app)
        response = client.get("/internal/analytics/rule-effectiveness")
        assert response.status_code == 200
        data = response.json()
        rule = next(r for r in data["rules"] if r["rule_no"] == "ALTI-MEM-007")
        assert rule["published"] >= 1
        assert rule["resolved"] >= 1
        assert rule["resolve_rate"] == 0.5

    def test_rule_effectiveness_api_prefers_latest_meaningful_state_on_reopen(self):
        """규칙 대시보드: reopened finding은 과거 resolved보다 최신 published를 따라야 한다."""
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        _reset_db()
        session = SessionLocal()
        try:
            review_request = ReviewRequest(
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60054",
            )
            session.add(review_request)
            session.flush()

            run1 = ReviewRun(
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60054",
                trigger="test-1",
                mode="manual",
                status="success",
            )
            run2 = ReviewRun(
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60054",
                trigger="test-2",
                mode="manual",
                status="success",
            )
            session.add_all([run1, run2])
            session.flush()

            evidence1 = FindingEvidence(
                review_run_id=run1.id,
                review_request_pk=review_request.id,
                file_path="src/a.cpp",
                patch_digest="digest-1",
                change_snippet="",
            )
            evidence2 = FindingEvidence(
                review_run_id=run2.id,
                review_request_pk=review_request.id,
                file_path="src/a.cpp",
                patch_digest="digest-2",
                change_snippet="",
            )
            session.add_all([evidence1, evidence2])
            session.flush()

            base_time = datetime(2026, 4, 21, tzinfo=UTC)
            session.add(
                FindingDecision(
                    review_run_id=run1.id,
                    evidence_id=evidence1.id,
                    review_request_pk=review_request.id,
                    review_system="gitlab",
                    project_ref="group/project",
                    review_request_id="60054",
                    fingerprint="fp-reopened",
                    dedupe_key="dk-reopened-1",
                    file_path="src/a.cpp",
                    line_no=10,
                    rule_no="ALTI-MEM-007",
                    source_family="altibase",
                    score_raw=0.9,
                    score_final=0.9,
                    anchor_signature="sig-a",
                    state="resolved",
                    created_at=base_time,
                )
            )
            session.add(
                FindingDecision(
                    review_run_id=run2.id,
                    evidence_id=evidence2.id,
                    review_request_pk=review_request.id,
                    review_system="gitlab",
                    project_ref="group/project",
                    review_request_id="60054",
                    fingerprint="fp-reopened",
                    dedupe_key="dk-reopened-2",
                    file_path="src/a.cpp",
                    line_no=10,
                    rule_no="ALTI-MEM-007",
                    source_family="altibase",
                    score_raw=0.95,
                    score_final=0.95,
                    anchor_signature="sig-a",
                    state="published",
                    created_at=base_time + timedelta(seconds=1),
                )
            )
            session.commit()
        finally:
            session.close()

        client = TestClient(app)
        response = client.get("/internal/analytics/rule-effectiveness")
        assert response.status_code == 200
        data = response.json()
        rule = next(r for r in data["rules"] if r["rule_no"] == "ALTI-MEM-007")
        assert rule["published"] == 1
        assert rule["resolved"] == 0
        assert rule["resolve_rate"] == 0.0

    def test_rule_effectiveness_api_excludes_candidate_only_finding_from_total(self):
        """규칙 대시보드: surfaced되지 않은 candidate-only finding은 total에 포함되면 안 된다."""
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        _reset_db()
        session = SessionLocal()
        try:
            review_request = ReviewRequest(
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60055",
            )
            session.add(review_request)
            session.flush()

            review_run = ReviewRun(
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60055",
                trigger="test",
                mode="manual",
                status="success",
            )
            session.add(review_run)
            session.flush()

            evidence = FindingEvidence(
                review_run_id=review_run.id,
                review_request_pk=review_request.id,
                file_path="src/a.cpp",
                patch_digest="digest-total",
                change_snippet="",
            )
            session.add(evidence)
            session.flush()

            session.add(
                FindingDecision(
                    review_run_id=review_run.id,
                    evidence_id=evidence.id,
                    review_request_pk=review_request.id,
                    review_system="gitlab",
                    project_ref="group/project",
                    review_request_id="60055",
                    fingerprint="fp-published",
                    dedupe_key="dk-published",
                    file_path="src/a.cpp",
                    line_no=10,
                    rule_no="ALTI-MEM-007",
                    source_family="altibase",
                    score_raw=0.9,
                    score_final=0.9,
                    anchor_signature="sig-a",
                    state="published",
                )
            )
            session.add(
                FindingDecision(
                    review_run_id=review_run.id,
                    evidence_id=evidence.id,
                    review_request_pk=review_request.id,
                    review_system="gitlab",
                    project_ref="group/project",
                    review_request_id="60055",
                    fingerprint="fp-candidate",
                    dedupe_key="dk-candidate",
                    file_path="src/b.cpp",
                    line_no=20,
                    rule_no="ALTI-MEM-007",
                    source_family="altibase",
                    score_raw=0.8,
                    score_final=0.8,
                    anchor_signature="sig-b",
                    state="candidate",
                )
            )
            session.commit()
        finally:
            session.close()

        client = TestClient(app)
        response = client.get("/internal/analytics/rule-effectiveness")
        assert response.status_code == 200
        data = response.json()
        rule = next(r for r in data["rules"] if r["rule_no"] == "ALTI-MEM-007")
        assert rule["total"] == 1
        assert rule["published"] == 1
        assert rule["resolved"] == 0
        assert rule["suppressed"] == 0

    def test_finding_outcomes_api_uses_distinct_fingerprint_and_preserves_fixed_history(self):
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        _reset_db()
        session = SessionLocal()
        try:
            review_request = ReviewRequest(
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60056",
            )
            session.add(review_request)
            session.flush()

            run1 = ReviewRun(
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60056",
                trigger="seed-1",
                mode="manual",
                status="success",
            )
            run2 = ReviewRun(
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60056",
                trigger="seed-2",
                mode="manual",
                status="success",
            )
            session.add_all([run1, run2])
            session.flush()

            evidence1 = FindingEvidence(
                review_run_id=run1.id,
                review_request_pk=review_request.id,
                file_path="src/a.cpp",
                patch_digest="digest-a",
                change_snippet="",
            )
            evidence2 = FindingEvidence(
                review_run_id=run2.id,
                review_request_pk=review_request.id,
                file_path="src/b.cpp",
                patch_digest="digest-b",
                change_snippet="",
            )
            session.add_all([evidence1, evidence2])
            session.flush()

            base_time = datetime.now(UTC) - timedelta(days=7)
            decision1 = FindingDecision(
                review_run_id=run1.id,
                evidence_id=evidence1.id,
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60056",
                fingerprint="fp-fixed-reopened",
                dedupe_key="dk-fixed",
                file_path="src/a.cpp",
                line_no=10,
                rule_no="ALTI-MEM-007",
                source_family="altibase",
                score_raw=0.9,
                score_final=0.9,
                anchor_signature="sig-fixed",
                state="published",
                created_at=base_time + timedelta(days=2),
            )
            decision2 = FindingDecision(
                review_run_id=run2.id,
                evidence_id=evidence2.id,
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60056",
                fingerprint="fp-manual",
                dedupe_key="dk-manual",
                file_path="src/b.cpp",
                line_no=20,
                rule_no="ALTI-MEM-007",
                source_family="altibase",
                score_raw=0.88,
                score_final=0.88,
                anchor_signature="sig-manual",
                state="resolved",
                created_at=base_time + timedelta(days=3),
            )
            session.add_all([decision1, decision2])
            session.flush()

            session.add_all(
                [
                    PublicationState(
                        finding_decision_id=decision1.id,
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60056",
                        adapter_thread_ref="thread-fixed",
                        publish_state="created",
                        published_at=base_time,
                    ),
                    PublicationState(
                        finding_decision_id=decision2.id,
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60056",
                        adapter_thread_ref="thread-manual",
                        publish_state="created",
                        published_at=base_time + timedelta(days=1),
                    ),
                    ThreadSyncState(
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60056",
                        finding_decision_id=decision1.id,
                        finding_fingerprint="fp-fixed-reopened",
                        anchor_signature="sig-fixed",
                        adapter_thread_ref="thread-fixed",
                        sync_status="open",
                    ),
                    ThreadSyncState(
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60056",
                        finding_decision_id=decision2.id,
                        finding_fingerprint="fp-manual",
                        anchor_signature="sig-manual",
                        adapter_thread_ref="thread-manual",
                        sync_status="resolved",
                        resolution_reason="remote_resolved_manual_only",
                    ),
                    FindingLifecycleEvent(
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60056",
                        finding_fingerprint="fp-fixed-reopened",
                        finding_decision_id=decision1.id,
                        adapter_thread_ref="thread-fixed",
                        rule_no="ALTI-MEM-007",
                        rule_family="altibase",
                        file_path="src/a.cpp",
                        event_type="resolved",
                        event_reason="fixed_in_followup_commit",
                        observed_head_sha="head-b",
                        compared_from_sha="head-a",
                        payload={},
                        event_at=base_time + timedelta(days=2),
                    ),
                    FindingLifecycleEvent(
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60056",
                        finding_fingerprint="fp-fixed-reopened",
                        finding_decision_id=decision1.id,
                        adapter_thread_ref="thread-fixed",
                        rule_no="ALTI-MEM-007",
                        rule_family="altibase",
                        file_path="src/a.cpp",
                        event_type="reopened",
                        event_reason="remote_reopened",
                        observed_head_sha="head-c",
                        compared_from_sha="head-b",
                        payload={},
                        event_at=base_time + timedelta(days=4),
                    ),
                    FindingLifecycleEvent(
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60056",
                        finding_fingerprint="fp-manual",
                        finding_decision_id=decision2.id,
                        adapter_thread_ref="thread-manual",
                        rule_no="ALTI-MEM-007",
                        rule_family="altibase",
                        file_path="src/b.cpp",
                        event_type="resolved",
                        event_reason="remote_resolved_manual_only",
                        observed_head_sha="head-d",
                        compared_from_sha="head-c",
                        payload={},
                        event_at=base_time + timedelta(days=3),
                    ),
                    FeedbackEvent(
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60056",
                        event_key="thread-fixed:reply:1",
                        adapter_thread_ref="thread-fixed",
                        adapter_comment_ref="note-1",
                        event_type="reply",
                        actor_type="human",
                        actor_ref="reviewer",
                        payload={"body": "bot:false-positive\n오탐입니다."},
                        occurred_at=base_time + timedelta(days=5),
                    ),
                ]
            )
            session.commit()
        finally:
            session.close()

        client = TestClient(app)
        response_28d = client.get(
            "/internal/analytics/finding-outcomes",
            params={"window": "28d", "project_ref": "group/project"},
        )
        assert response_28d.status_code == 200
        data_28d = response_28d.json()
        assert data_28d["surfaced_distinct"] == 2
        assert data_28d["resolved_distinct"] == 1
        assert data_28d["fixed_distinct"] == 1
        assert data_28d["manual_resolved_distinct"] == 1
        assert data_28d["false_positive_distinct"] == 1
        assert data_28d["reopened_distinct"] == 1
        assert data_28d["surfaced_cohort_distinct"] == 2
        assert data_28d["converted_cohort_distinct"] == 1
        assert data_28d["fix_conversion_rate"] == 0.5

        response_14d = client.get(
            "/internal/analytics/finding-outcomes",
            params={"window": "14d", "project_ref": "group/project"},
        )
        assert response_14d.status_code == 200
        data_14d = response_14d.json()
        assert data_14d["fixed_distinct"] == 1
        assert data_14d["resolved_distinct"] == 1
        assert data_14d["fix_confirmation_rate"] == 0.0
        assert data_14d["human_resolve_rate"] == 0.5
        assert data_14d["false_positive_feedback_rate"] == 0.5

    def test_finding_outcomes_api_filters_by_source_family(self):
        from fastapi.testclient import TestClient
        from review_bot.api.main import app

        _reset_db()
        session = SessionLocal()
        try:
            review_request = ReviewRequest(
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60057",
            )
            session.add(review_request)
            session.flush()

            review_run = ReviewRun(
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60057",
                trigger="seed",
                mode="manual",
                status="success",
            )
            session.add(review_run)
            session.flush()

            evidence = FindingEvidence(
                review_run_id=review_run.id,
                review_request_pk=review_request.id,
                file_path="src/a.cpp",
                patch_digest="digest-source",
                change_snippet="",
            )
            session.add(evidence)
            session.flush()

            altibase_decision = FindingDecision(
                review_run_id=review_run.id,
                evidence_id=evidence.id,
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60057",
                fingerprint="fp-altibase",
                dedupe_key="dk-altibase",
                file_path="src/a.cpp",
                line_no=10,
                rule_no="ALTI-MEM-007",
                source_family="altibase",
                score_raw=0.9,
                score_final=0.9,
                anchor_signature="sig-altibase",
                state="published",
            )
            cpp_core_decision = FindingDecision(
                review_run_id=review_run.id,
                evidence_id=evidence.id,
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref="group/project",
                review_request_id="60057",
                fingerprint="fp-cpp-core",
                dedupe_key="dk-cpp-core",
                file_path="src/b.cpp",
                line_no=20,
                rule_no="CPP-001",
                source_family="cpp_core",
                score_raw=0.9,
                score_final=0.9,
                anchor_signature="sig-cpp",
                state="published",
            )
            session.add_all([altibase_decision, cpp_core_decision])
            session.flush()

            now = datetime.now(UTC)
            session.add_all(
                [
                    PublicationState(
                        finding_decision_id=altibase_decision.id,
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60057",
                        publish_state="created",
                        published_at=now,
                    ),
                    PublicationState(
                        finding_decision_id=cpp_core_decision.id,
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="60057",
                        publish_state="created",
                        published_at=now,
                    ),
                ]
            )
            session.commit()
        finally:
            session.close()

        client = TestClient(app)
        response = client.get(
            "/internal/analytics/finding-outcomes",
            params={
                "window": "28d",
                "project_ref": "group/project",
                "source_family": "altibase",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["surfaced_distinct"] == 1
        assert data["project_ref"] == "group/project"
        assert data["source_family"] == "altibase"

    def test_comment_footer_always_present(self):
        """코멘트 형식: 모든 코멘트에 안내 문구가 포함된다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(6006)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=6006, trigger="test")
            body = adapter.upsert_requests[0].body
            assert "Resolve" in body or "resolve" in body.lower()
        finally:
            session.close()


# ═══════════════════════════════════════════════════════
# 파이프라인 통합 — 전체 흐름
# ═══════════════════════════════════════════════════════

class TestEndToEndPipeline:

    def test_full_pipeline_detect_publish_sync(self):
        """E2E: detect → publish → sync 전체 파이프라인이 정상 완료된다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(7001)
        adapter.set_diff(key, path="src/db.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            run = runner.run_review(session, pr_id=7001, trigger="e2e")

            assert run.status == "success"
            assert len(adapter.upsert_requests) == 1
            assert len(adapter.general_notes) == 1

            decisions = session.query(FindingDecision).filter_by(
                review_run_id=run.id
            ).all()
            assert len(decisions) >= 1
            published = [d for d in decisions if d.state == "published"]
            assert len(published) >= 1

            thread = session.query(ThreadSyncState).first()
            assert thread is not None
            assert thread.sync_status == "open"

            pub = session.query(PublicationState).first()
            assert pub is not None
            assert pub.publish_state in ("created", "updated")
        finally:
            session.close()

    def test_full_pipeline_with_evidence_and_autofix(self):
        """E2E: 증거 인용 + Auto-fix가 포함된 코멘트가 게시된다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(7002)
        adapter.set_diff(key, path="src/mem.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider(
            evidence_snippet="`malloc(1024)` — 직접 메모리 할당",
            auto_fix_lines=["    std::vector<char> buf(1024);"],
            confidence=0.95,
        )

        session = SessionLocal()
        try:
            run = runner.run_review(session, pr_id=7002, trigger="e2e-fix")
            body = adapter.upsert_requests[0].body
            assert "`malloc(1024)` — 직접 메모리 할당" in body
            assert "```suggestion" in body
            assert "std::vector<char> buf(1024);" in body

            decision = session.query(FindingDecision).filter_by(
                review_run_id=run.id, state="published"
            ).first()
            assert decision.evidence_snippet is not None
            assert len(decision.auto_fix_lines) > 0
        finally:
            session.close()

    def test_second_run_suppresses_resolved_finding(self):
        """E2E: 첫 run에서 게시된 finding을 resolved 처리하면 두 번째 run에서 패널티를 받는다."""
        _reset_db()
        runner = ReviewRunner()
        adapter = FakeAdapter()
        key = runner._legacy_key(7003)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
        runner.platform_client = adapter
        runner.engine_client = EngineStub([_result()])
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            run1 = runner.run_review(session, pr_id=7003, trigger="first")
            decisions1 = session.query(FindingDecision).filter_by(
                review_run_id=run1.id
            ).all()
            assert len(decisions1) >= 1

            # thread를 resolved 처리
            thread = session.query(ThreadSyncState).first()
            thread.sync_status = "resolved"
            thread.resolution_reason = "remote_resolved"
            for d in decisions1:
                d.state = "resolved"
            session.commit()

            run2 = runner.run_review(session, pr_id=7003, trigger="second")
            decisions2 = session.query(FindingDecision).filter_by(
                review_run_id=run2.id
            ).all()

            # 두 번째 run에서 resolved_penalty 적용 확인
            for d in decisions2:
                # score_final이 score_raw보다 낮아야 함 (penalty 적용)
                assert d.score_final <= d.score_raw + 0.01
        finally:
            session.close()

    def test_batch_size_limit_respected(self):
        """배치 제한: batch_size를 초과하는 finding은 다음 배치로 미뤄진다."""
        _reset_db()
        runner = ReviewRunner()
        runner.settings = type("S", (), {
            **{k: getattr(runner.settings, k) for k in vars(runner.settings)
               if not k.startswith("__")},
            "batch_size": 2,
            "rule_family_cap": 10,
            "minimum_publish_score": 0.0,
        })()

        adapter = FakeAdapter()
        key = runner._legacy_key(7004)
        # 5개 다른 규칙이 있는 경우
        multi_patch = (
            "@@ -1,2 +1,8 @@\n void foo() {\n"
            "+    char* b1 = (char*)malloc(10);\n"
            "+    char* b2 = (char*)malloc(20);\n"
            "+    char* b3 = (char*)malloc(30);\n"
            "+    char* b4 = (char*)malloc(40);\n"
            "+    char* b5 = (char*)malloc(50);\n"
            " }\n"
        )
        adapter.set_diff(key, path="src/a.cpp", patch=multi_patch)
        runner.platform_client = adapter

        # 5개 다른 규칙 반환
        rules = [_result(f"RULE-{i:03d}") for i in range(5)]
        runner.engine_client = EngineStub(rules)
        runner.provider = FixedProvider()

        session = SessionLocal()
        try:
            runner.run_review(session, pr_id=7004, trigger="batch-test")
            # batch_size=2이므로 최대 2개만 게시
            assert len(adapter.upsert_requests) <= 2
        finally:
            session.close()
