from __future__ import annotations

from dataclasses import dataclass, field, replace as dataclass_replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from review_bot.bot import review_runner as review_runner_module
from review_bot.analytics.wrong_language import (
    classify_wrong_language_cause,
    classify_wrong_language_provenance,
    wrong_language_actionability,
)
from review_bot.bot.review_runner import MAX_COMMENT_BODY, ReviewRunner
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
    FeedbackEvent,
    FindingDecision,
    FindingEvidence,
    FindingLifecycleEvent,
    PublicationState,
    ReviewRun,
    ThreadSyncState,
)
from review_bot.db.session import Base, SessionLocal, engine
from review_bot.errors import ReviewBotError
from review_bot.metrics import feedback_commands_total, verify_attempts_total, verify_dropped_total
from review_bot.policy import PathPolicy, ReviewPolicy
from review_bot.providers.base import FindingDraft, ReviewCommentProvider, VerifyDraftResult
from review_bot.providers.fallback_provider import FallbackReviewCommentProvider
from review_bot.quality.review_unit_split_audit import load_review_unit_split_cases


def test_review_runner_publishes_inline_comment_and_persists_thread_state() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(101)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=101, trigger="test")

        published = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id, state="published")
            .all()
        )
        thread_state = session.query(ThreadSyncState).one()
        publications = session.query(PublicationState).all()

        assert review_run.status == "success"
        assert len(published) == 1
        assert len(publications) == 1
        assert len(adapter.upsert_requests) == 1
        assert thread_state.sync_status == "open"
        assert thread_state.adapter_thread_ref == "thread-1"

        state = runner.build_state(session, 101)
        assert state["last_status"] == "success"
        assert state["published_batch_count"] == 1
        assert state["open_thread_count"] == 1
        assert state["open_finding_count"] == 1
    finally:
        session.close()


def test_review_runner_keeps_distinct_findings_per_hunk() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(202)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_multi_hunk_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=202, trigger="test-hunks")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_request_id="202", rule_no="R.10")
            .order_by(FindingDecision.line_no.asc())
            .all()
        )

        assert len(findings) == 2
        assert findings[0].fingerprint != findings[1].fingerprint
        assert findings[0].line_no != findings[1].line_no
    finally:
        session.close()


def test_review_runner_yaml_syntax_aware_split_uses_safe_boundary_for_anchor_and_fingerprint() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(203)  # noqa: SLF001
    adapter.set_diff(key, path="deploy/review-audit.yaml", patch=_yaml_k8s_long_container_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("YAML.K8S.7", category="configuration")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=203, trigger="test-yaml-split")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_request_id="203", rule_no="YAML.K8S.7")
            .order_by(FindingDecision.line_no.asc())
            .all()
        )

        assert len(findings) == 2
        assert [finding.line_no for finding in findings] == [1, 80]
        assert findings[0].fingerprint != findings[1].fingerprint
        assert [finding.anchor_payload["start_line"] for finding in findings] == [1, 80]
    finally:
        session.close()


def test_review_runner_typescript_syntax_aware_split_uses_safe_boundary_for_anchor_and_fingerprint() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(204)  # noqa: SLF001
    adapter.set_diff(key, path="ui/ReviewAuditPanel.tsx", patch=_typescript_react_long_component_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("TS.7", category="security")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=204, trigger="test-typescript-split")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_request_id="204", rule_no="TS.7")
            .order_by(FindingDecision.line_no.asc())
            .all()
        )

        assert len(findings) == 2
        assert [finding.line_no for finding in findings] == [1, 78]
        assert findings[0].fingerprint != findings[1].fingerprint
        assert [finding.anchor_payload["start_line"] for finding in findings] == [1, 78]
    finally:
        session.close()


def test_review_runner_python_syntax_aware_split_uses_safe_boundary_for_anchor_and_fingerprint() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(205)  # noqa: SLF001
    adapter.set_diff(key, path="app/api/audit.py", patch=_python_fastapi_long_handler_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("PY.7", category="correctness")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=205, trigger="test-python-split")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_request_id="205", rule_no="PY.7")
            .order_by(FindingDecision.line_no.asc())
            .all()
        )

        assert len(findings) == 2
        assert [finding.line_no for finding in findings] == [1, 80]
        assert findings[0].fingerprint != findings[1].fingerprint
        assert [finding.anchor_payload["start_line"] for finding in findings] == [1, 80]
    finally:
        session.close()


def test_review_runner_persists_provider_runtime_metadata_on_run_and_finding() -> None:
    _reset_db()

    class NamedProvider(FixedProvider):
        provider_name = "openai"

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(303)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = NamedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=303, trigger="provider-runtime")
        stored_run = session.get(ReviewRun, review_run.id)
        evidence = session.query(FindingEvidence).filter_by(review_run_id=review_run.id).one()
        state = runner.build_state(session, pr_id=303)

        assert stored_run is not None
        assert stored_run.provider_runtime == {
            "configured_provider": "openai",
            "effective_provider": "openai",
            "fallback_used": False,
            "fallback_reason": None,
        }
        assert evidence.raw_engine_payload["provider_runtime"] == stored_run.provider_runtime
        assert state["provider_runtime"] == stored_run.provider_runtime
    finally:
        session.close()


def test_review_runner_persists_fallback_provider_runtime_metadata() -> None:
    _reset_db()

    class BuildFailingProvider(FixedProvider):
        provider_name = "openai"

        def build_draft(self, **kwargs):  # type: ignore[override]
            del kwargs
            raise RuntimeError("openai unavailable")

    class NamedFallbackProvider(FixedProvider):
        provider_name = "stub"

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(304)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FallbackReviewCommentProvider(
        primary=BuildFailingProvider(),
        fallback=NamedFallbackProvider(),
    )

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=304, trigger="provider-fallback")
        stored_run = session.get(ReviewRun, review_run.id)
        evidence = session.query(FindingEvidence).filter_by(review_run_id=review_run.id).one()
        state = runner.build_state(session, pr_id=304)

        assert stored_run is not None
        assert stored_run.provider_runtime == {
            "configured_provider": "openai",
            "effective_provider": "stub",
            "fallback_used": True,
            "fallback_reason": "build_draft_error:RuntimeError",
        }
        assert evidence.raw_engine_payload["provider_runtime"] == stored_run.provider_runtime
        assert state["provider_runtime"] == stored_run.provider_runtime
    finally:
        session.close()


def test_pr_summary_includes_live_provider_runtime_provenance() -> None:
    _reset_db()

    class NamedProvider(FixedProvider):
        provider_name = "openai"

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(305)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = NamedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=305, trigger="provider-summary-live")

        assert len(adapter.general_notes) == 1
        assert (
            "이번 run provider: configured `openai`, effective `openai` "
            "(live provider path)."
        ) in adapter.general_notes[0]
    finally:
        session.close()


def test_publish_logs_and_summary_include_fallback_provider_runtime_provenance() -> None:
    _reset_db()

    class BuildFailingProvider(FixedProvider):
        provider_name = "openai"

        def build_draft(self, **kwargs):  # type: ignore[override]
            del kwargs
            raise RuntimeError("openai unavailable")

    class NamedFallbackProvider(FixedProvider):
        provider_name = "stub"

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(306)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FallbackReviewCommentProvider(
        primary=BuildFailingProvider(),
        fallback=NamedFallbackProvider(),
    )

    session = SessionLocal()
    try:
        with patch.object(review_runner_module.logger, "info") as mock_info:
            runner.run_review(session, pr_id=306, trigger="provider-summary-fallback")

        expected_summary = (
            "configured `openai`, effective `stub` (stub fallback path), "
            "reason `build_draft_error:RuntimeError`"
        )
        assert len(adapter.general_notes) == 1
        assert f"이번 run provider: {expected_summary}." in adapter.general_notes[0]

        review_run_events = [
            call.kwargs["extra"]["review_run_event"]
            for call in mock_info.call_args_list
            if call.args and call.args[0] == "review_run_event"
        ]
        candidates_built = next(
            event for event in review_run_events if event["event"] == "publish_candidates_built"
        )
        publish_completed = next(
            event for event in review_run_events if event["event"] == "publish_completed"
        )

        for event in (candidates_built, publish_completed):
            assert event["provider_runtime"] == {
                "configured_provider": "openai",
                "effective_provider": "stub",
                "fallback_used": True,
                "fallback_reason": "build_draft_error:RuntimeError",
            }
            assert event["provider_runtime_summary"] == expected_summary
    finally:
        session.close()


def test_full_rerun_does_not_reply_again_to_unchanged_open_thread_by_default() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(404)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider(summary_suffix="same")

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=404, trigger="first")
        runner.run_review(session, pr_id=404, trigger="second")

        publications = (
            session.query(PublicationState)
            .filter_by(review_request_id="404")
            .order_by(PublicationState.batch_no.asc(), PublicationState.updated_at.asc())
            .all()
        )
        threads = adapter.list_threads(key)
        state = runner.build_state(session, 404)

        assert len(adapter.upsert_requests) == 1
        assert [item.publish_state for item in publications] == ["created"]
        assert len(threads) == 1
        assert len(threads[0].notes) == 1
        assert state["published_batch_count"] == 1
        assert state["open_finding_count"] == 1
    finally:
        session.close()


def test_review_runner_replies_to_existing_thread_when_body_changes_but_anchor_is_same() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(505)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    provider = FixedProvider(summary_suffix="v1")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = provider

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=505, trigger="first")
        provider.summary_suffix = "v2"
        runner.run_review(session, pr_id=505, trigger="second")

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        threads = adapter.list_threads(key)
        assert len(threads) == 1
        assert len(threads[0].notes) == 2
        assert session.query(ThreadSyncState).filter_by(review_request_id="505").count() == 1
    finally:
        session.close()


def test_review_runner_prioritizes_existing_thread_update_before_new_finding_when_batch_is_full() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.settings = dataclass_replace(runner.settings, batch_size=1)
    adapter = FakeAdapter()
    key = runner._legacy_key(555)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-a")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory", score=0.8)])
    provider = ScenarioProvider(
        {
            ("src/a.cpp", "R.10"): FindingDraft(
                title="메모리를 직접 할당하고 해제하고 있습니다",
                summary="첫 번째 게시입니다.",
                suggested_fix="RAII 또는 프로젝트 표준 wrapper로 옮겨 주세요.",
            ),
            ("src/b.cpp", "ES.77"): FindingDraft(
                title="루프 흐름이 `continue`에 의존하고 있습니다",
                summary="새로운 제어 흐름 finding입니다.",
                suggested_fix="조건 분기를 명시적으로 정리해 주세요.",
            ),
        }
    )
    runner.provider = provider

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=555, trigger="first")

        adapter.set_files_diff(
            key,
            files=[
                {"path": "src/a.cpp", "patch": _malloc_patch()},
                {"path": "src/b.cpp", "patch": _continue_patch()},
            ],
            head_sha="head-b",
        )
        provider.mapping[("src/a.cpp", "R.10")] = FindingDraft(
            title="메모리를 직접 할당하고 해제하고 있습니다",
            summary="기존 thread를 먼저 갱신해야 합니다.",
            suggested_fix="RAII 또는 프로젝트 표준 wrapper로 옮겨 주세요.",
        )
        runner.engine_client = SequentialEngineStub(
            [
                [_result("R.10", category="memory", score=0.75)],
                [_result("ES.77", category="control_flow", score=0.99)],
            ]
        )

        review_run = runner.create_review_run_for_key(
            session,
            key,
            trigger="gitlab:update",
            mode="incremental",
        )
        runner.execute_review_run(session, review_run.id)

        findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .order_by(FindingDecision.file_path.asc())
            .all()
        )

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert [item.file_path for item in findings if item.state == "published"] == ["src/a.cpp"]
        assert [item.file_path for item in findings if item.state == "eligible"] == ["src/b.cpp"]
        assert len(adapter.list_threads(key)) == 1
    finally:
        session.close()


def test_review_runner_does_not_spend_batch_slot_on_unchanged_open_thread() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.settings = dataclass_replace(runner.settings, batch_size=1)
    adapter = FakeAdapter()
    key = runner._legacy_key(556)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-a")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory", score=0.8)])
    provider = ScenarioProvider(
        {
            ("src/a.cpp", "R.10"): FindingDraft(
                title="메모리를 직접 할당하고 해제하고 있습니다",
                summary="변화가 없는 기존 thread입니다.",
                suggested_fix="RAII 또는 프로젝트 표준 wrapper로 옮겨 주세요.",
            ),
            ("src/b.cpp", "ES.77"): FindingDraft(
                title="루프 흐름이 `continue`에 의존하고 있습니다",
                summary="새 finding을 우선 게시해야 합니다.",
                suggested_fix="조건 분기를 명시적으로 정리해 주세요.",
            ),
        }
    )
    runner.provider = provider

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=556, trigger="first")

        adapter.set_files_diff(
            key,
            files=[
                {"path": "src/a.cpp", "patch": _malloc_patch()},
                {"path": "src/b.cpp", "patch": _continue_patch()},
            ],
            head_sha="head-b",
        )
        runner.engine_client = SequentialEngineStub(
            [
                [_result("R.10", category="memory", score=0.8)],
                [_result("ES.77", category="control_flow", score=0.99)],
            ]
        )

        review_run = runner.create_review_run_for_key(
            session,
            key,
            trigger="gitlab:update",
            mode="incremental",
        )
        runner.execute_review_run(session, review_run.id)

        findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .order_by(FindingDecision.file_path.asc())
            .all()
        )
        publications = (
            session.query(PublicationState)
            .filter_by(review_request_id="556")
            .order_by(PublicationState.batch_no.asc(), PublicationState.updated_at.asc())
            .all()
        )

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref is None
        assert [item.file_path for item in findings if item.state == "published"] == ["src/a.cpp", "src/b.cpp"]
        assert [item.publish_state for item in publications] == ["created", "created"]
        assert len(adapter.list_threads(key)) == 2
    finally:
        session.close()


def test_review_runner_interleaves_files_before_second_comment_on_same_file() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.settings = dataclass_replace(runner.settings, batch_size=2, file_comment_cap=2)
    adapter = FakeAdapter()
    key = runner._legacy_key(557)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[
            {"path": "src/a.cpp", "patch": _malloc_patch()},
            {"path": "src/b.cpp", "patch": _continue_patch()},
        ],
        head_sha="head-density",
    )
    runner.platform_client = adapter
    runner.engine_client = SequentialEngineStub(
        [
            [
                _result("R.10", category="memory", score=0.99),
                _result("ES.77", category="control_flow", score=0.98),
            ],
            [_result("NAME.TEST.001", category="naming", score=0.80)],
        ]
    )
    runner.provider = ScenarioProvider(
        {
            ("src/a.cpp", "R.10"): FindingDraft(
                title="직접 메모리 관리가 보입니다",
                summary="첫 번째 파일의 핵심 finding입니다.",
                suggested_fix="RAII로 교체하세요.",
            ),
            ("src/a.cpp", "ES.77"): FindingDraft(
                title="흐름 제어가 분산되어 있습니다",
                summary="같은 파일의 두 번째 finding입니다.",
                suggested_fix="분기 구조를 단순화하세요.",
            ),
            ("src/b.cpp", "NAME.TEST.001"): FindingDraft(
                title="이름이 역할을 충분히 드러내지 않습니다",
                summary="다른 파일 finding입니다.",
                suggested_fix="역할이 드러나는 이름으로 바꾸세요.",
            ),
        }
    )

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=557, trigger="density")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_request_id="557")
            .order_by(FindingDecision.file_path.asc(), FindingDecision.rule_no.asc())
            .all()
        )

        assert [request.anchor.file_path for request in adapter.upsert_requests] == [
            "src/a.cpp",
            "src/b.cpp",
        ]
        assert [item.file_path for item in findings if item.state == "published"] == [
            "src/a.cpp",
            "src/b.cpp",
        ]
        assert [item.file_path for item in findings if item.state == "eligible"] == ["src/a.cpp"]
    finally:
        session.close()


def test_review_runner_resolves_stale_thread_when_finding_is_no_longer_auto_publishable() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(606)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    engine = EngineStub([_result("R.10", category="memory")])
    runner.platform_client = adapter
    runner.engine_client = engine
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=606, trigger="first")
        engine.results = [_result("R.10", category="memory", reviewability="manual_only")]
        review_run = runner.run_review(session, pr_id=606, trigger="second")

        thread_state = session.query(ThreadSyncState).one()
        old_published = (
            session.query(FindingDecision)
            .filter_by(review_request_id="606", state="resolved")
            .all()
        )
        current_suppressed = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id, state="suppressed")
            .all()
        )

        assert adapter.resolved_threads == ["thread-1"]
        assert thread_state.sync_status == "resolved"
        assert old_published
        assert current_suppressed
        assert current_suppressed[0].suppression_reason == "reviewability:manual_only"
    finally:
        session.close()


def test_incremental_sync_does_not_resolve_threads_for_untouched_files() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(616)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-a")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=616, trigger="first")

        adapter.set_diff(key, path="src/b.cpp", patch=_continue_patch(), head_sha="head-b")
        runner.engine_client = EngineStub([])
        review_run = runner.create_review_run_for_key(
            session,
            key,
            trigger="gitlab:update",
            mode="incremental",
        )
        runner.execute_review_run(session, review_run.id)

        thread_state = session.query(ThreadSyncState).one()
        published = (
            session.query(FindingDecision)
            .filter_by(review_request_id="616", state="published")
            .all()
        )

        assert adapter.resolved_threads == []
        assert thread_state.sync_status == "open"
        assert published
    finally:
        session.close()


def test_review_runner_collects_feedback_events_from_resolved_threads_and_human_replies() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(707)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=707, trigger="first")
        adapter.add_human_reply(key, "thread-1", "사람이 남긴 후속 코멘트")
        adapter.mark_resolved(key, "thread-1", resolved=True)

        runner.run_review(session, pr_id=707, trigger="second")

        feedback = (
            session.query(FeedbackEvent)
            .filter_by(review_request_id="707")
            .order_by(FeedbackEvent.event_type.asc())
            .all()
        )

        assert {event.event_type for event in feedback} >= {"reply", "resolved", "unresolved"}
        assert any(event.actor_type == "human" for event in feedback)
    finally:
        session.close()


def test_feedback_command_metric_counts_unique_event_key_once() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7071)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    baseline = _counter_value(feedback_commands_total, command="later")
    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7071, trigger="first")
        adapter.add_human_reply(key, "thread-1", "bot:later\n다음 주에 처리하겠습니다.")

        runner.run_review(session, pr_id=7071, trigger="second")
        runner.run_review(session, pr_id=7071, trigger="third")

        assert _counter_value(feedback_commands_total, command="later") - baseline == 1
    finally:
        session.close()


def test_verify_reject_suppresses_candidate_and_records_metrics() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.settings = dataclass_replace(
        runner.settings,
        verify_enabled=True,
        verify_confidence_threshold=0.85,
        verify_score_band=0.1,
    )
    adapter = FakeAdapter()
    key = runner._legacy_key(7072)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory", score=0.7)])
    runner.provider = VerifyScenarioProvider(
        verify_result=VerifyDraftResult(applies=False, reason="not_a_real_bug")
    )

    attempts_before = _counter_value(verify_attempts_total, mode="llm_self_check")
    dropped_before = _counter_value(
        verify_dropped_total,
        mode="llm_self_check",
        reason="not_a_real_bug",
    )
    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=7072, trigger="verify-suppress")
        decision = session.query(FindingDecision).filter_by(review_run_id=review_run.id).one()

        assert decision.state == "suppressed"
        assert decision.suppression_reason == "verify:not_a_real_bug"
        assert len(adapter.upsert_requests) == 0
        assert _counter_value(verify_attempts_total, mode="llm_self_check") - attempts_before == 1
        assert (
            _counter_value(
                verify_dropped_total,
                mode="llm_self_check",
                reason="not_a_real_bug",
            )
            - dropped_before
            == 1
        )
    finally:
        session.close()


def test_verify_execution_error_fails_open_and_keeps_publish() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.settings = dataclass_replace(
        runner.settings,
        verify_enabled=True,
        verify_confidence_threshold=0.85,
        verify_score_band=0.1,
    )
    adapter = FakeAdapter()
    key = runner._legacy_key(7073)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory", score=0.7)])
    runner.provider = VerifyScenarioProvider(verify_error=RuntimeError("verify execution failed"))

    attempts_before = _counter_value(verify_attempts_total, mode="llm_self_check")
    dropped_before = _counter_value(
        verify_dropped_total,
        mode="llm_self_check",
        reason="low_confidence",
    )
    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=7073, trigger="verify-fail-open")
        decision = session.query(FindingDecision).filter_by(review_run_id=review_run.id).one()

        assert decision.state == "published"
        assert decision.suppression_reason is None
        assert len(adapter.upsert_requests) == 1
        assert _counter_value(verify_attempts_total, mode="llm_self_check") - attempts_before == 1
        assert (
            _counter_value(
                verify_dropped_total,
                mode="llm_self_check",
                reason="low_confidence",
            )
            - dropped_before
            == 0
        )
    finally:
        session.close()


def test_verify_execution_error_reason_alias_fails_open_and_keeps_publish() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.settings = dataclass_replace(
        runner.settings,
        verify_enabled=True,
        verify_confidence_threshold=0.85,
        verify_score_band=0.1,
    )
    adapter = FakeAdapter()
    key = runner._legacy_key(70731)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory", score=0.7)])
    runner.provider = VerifyScenarioProvider(
        verify_result=VerifyDraftResult(applies=False, reason="execution error")
    )

    attempts_before = _counter_value(verify_attempts_total, mode="llm_self_check")
    dropped_before = _counter_value(
        verify_dropped_total,
        mode="llm_self_check",
        reason="execution_error",
    )
    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=70731, trigger="verify-fail-open-alias")
        decision = session.query(FindingDecision).filter_by(review_run_id=review_run.id).one()

        assert decision.state == "published"
        assert decision.suppression_reason is None
        assert len(adapter.upsert_requests) == 1
        assert _counter_value(verify_attempts_total, mode="llm_self_check") - attempts_before == 1
        assert (
            _counter_value(
                verify_dropped_total,
                mode="llm_self_check",
                reason="execution_error",
            )
            - dropped_before
            == 0
        )
    finally:
        session.close()


def test_normalize_verify_reason_accepts_common_aliases() -> None:
    runner = ReviewRunner()

    assert (
        runner._normalize_verify_reason(  # noqa: SLF001
            VerifyDraftResult(applies=False, reason="not a real bug")
        )
        == "not_a_real_bug"
    )
    assert (
        runner._normalize_verify_reason(  # noqa: SLF001
            VerifyDraftResult(applies=False, reason="Pattern mismatch")
        )
        == "pattern_mismatch"
    )
    assert (
        runner._normalize_verify_reason(  # noqa: SLF001
            VerifyDraftResult(applies=False, reason="execution error")
        )
        == "execution_error"
    )
    assert (
        runner._normalize_verify_reason(  # noqa: SLF001
            VerifyDraftResult(applies=False, reason="something else")
        )
        == "low_confidence"
    )


def test_fallback_provider_verify_failure_does_not_disable_primary_build_draft() -> None:
    provider = FallbackReviewCommentProvider(
        primary=VerifyScenarioProvider(
            title="primary-title",
            verify_error=RuntimeError("verify execution failed"),
        ),
        fallback=FixedProvider(title="fallback-title"),
    )

    verify_result = provider.verify_draft(
        draft=FindingDraft(
            title="draft-title",
            summary="draft-summary",
            suggested_fix=None,
        ),
        file_path="src/a.cpp",
        rule_no="R.10",
        title="memory finding",
        summary="memory summary",
    )
    draft = provider.build_draft(
        file_path="src/a.cpp",
        rule_no="R.10",
        title="memory finding",
        summary="memory summary",
    )

    assert verify_result.applies is True
    assert draft.title == "primary-title"
    assert draft.summary == "이 변경은 소유권을 직접 관리합니다."


def test_fallback_provider_build_failure_disables_primary_and_uses_fallback() -> None:
    class BuildFailingProvider(FixedProvider):
        def build_draft(self, **kwargs):  # type: ignore[override]
            del kwargs
            raise RuntimeError("openai unavailable")

    provider = FallbackReviewCommentProvider(
        primary=BuildFailingProvider(title="primary-title"),
        fallback=FixedProvider(title="fallback-title"),
    )

    draft = provider.build_draft(
        file_path="src/a.cpp",
        rule_no="R.10",
        title="memory finding",
        summary="memory summary",
    )

    assert provider.primary_build_available is False
    assert draft.title == "fallback-title"
    assert draft.summary == "이 변경은 소유권을 직접 관리합니다."


def test_review_runner_waits_for_expected_head_on_gitlab_note_trigger(monkeypatch) -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = ReviewRequestKey(
        review_system="gitlab",
        project_ref="group/project-a",
        review_request_id="7991",
    )
    expected_head_sha = "new-head"
    stale_head_sha = "stale-head"
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha=stale_head_sha)
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    key_tuple = _key_tuple(key)
    base_meta = adapter.meta_by_key[key_tuple]
    base_diff = adapter.diff_by_key[key_tuple]
    meta_calls = {"count": 0}
    diff_calls = {"count": 0}

    def fetch_review_request_meta(test_key: ReviewRequestKey) -> ReviewRequestMeta:
        assert test_key == key
        meta_calls["count"] += 1
        head_sha = expected_head_sha if meta_calls["count"] >= 2 else stale_head_sha
        return ReviewRequestMeta(
            key=key,
            title=base_meta.title,
            source_branch=base_meta.source_branch,
            target_branch=base_meta.target_branch,
            base_sha=base_meta.base_sha,
            start_sha=base_meta.start_sha,
            head_sha=head_sha,
        )

    def fetch_diff(test_key: ReviewRequestKey, *, mode: str, base_sha: str | None = None) -> DiffPayload:
        assert test_key == key
        assert mode == "manual"
        assert base_sha is None
        diff_calls["count"] += 1
        head_sha = expected_head_sha if diff_calls["count"] >= 2 else stale_head_sha
        return DiffPayload(
            pull_request={
                **base_diff.pull_request,
                "head_sha": head_sha,
            },
            files=list(base_diff.files),
        )

    monkeypatch.setattr(adapter, "fetch_review_request_meta", fetch_review_request_meta)
    monkeypatch.setattr(adapter, "fetch_diff", fetch_diff)
    monkeypatch.setattr("review_bot.bot.review_runner.time.sleep", lambda _: None)

    session = SessionLocal()
    try:
        review_run = runner.create_review_run_for_key(
            session,
            key,
            trigger="gitlab:note_mention",
            mode="manual",
            meta=ReviewRequestMeta(
                key=key,
                title="MR 7991",
                source_branch="feature",
                target_branch="main",
                head_sha=expected_head_sha,
            ),
        )

        runner.execute_review_run(session, review_run.id)

        refreshed = session.get(ReviewRun, review_run.id)
        assert refreshed is not None
        assert refreshed.status == "success"
        assert refreshed.head_sha == expected_head_sha
        assert meta_calls["count"] >= 2
        assert diff_calls["count"] >= 2
    finally:
        session.close()


def test_resolution_classifier_marks_fixed_in_followup_commit_and_records_lifecycle() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7074)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-a")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7074, trigger="first")

        adapter.mark_resolved(key, "thread-1", resolved=True)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-b")
        adapter.set_incremental_diff(
            key,
            base_sha="head-a",
            files=[{"path": "src/a.cpp", "patch": _malloc_patch()}],
            head_sha="head-b",
        )
        runner.engine_client = EngineStub(
            [_result("R.10", category="memory", reviewability="manual_only")]
        )

        runner.run_review(session, pr_id=7074, trigger="resolved-with-fix")

        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="7074").one()
        lifecycle_event = (
            session.query(FindingLifecycleEvent)
            .filter_by(review_request_id="7074", event_type="resolved")
            .order_by(FindingLifecycleEvent.event_at.desc())
            .first()
        )

        assert thread_state.sync_status == "resolved"
        assert thread_state.resolution_reason == "fixed_in_followup_commit"
        assert lifecycle_event is not None
        assert lifecycle_event.event_reason == "fixed_in_followup_commit"
        assert lifecycle_event.compared_from_sha == "head-a"
        assert lifecycle_event.observed_head_sha == "head-b"
    finally:
        session.close()


def test_resolution_classifier_marks_remote_resolved_manual_only_when_diff_does_not_match() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7075)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-a")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7075, trigger="first")

        adapter.mark_resolved(key, "thread-1", resolved=True)
        adapter.set_diff(key, path="src/a.cpp", patch=_continue_patch(), head_sha="head-b")
        adapter.set_incremental_diff(
            key,
            base_sha="head-a",
            files=[{"path": "src/a.cpp", "patch": _continue_patch()}],
            head_sha="head-b",
        )
        runner.engine_client = EngineStub(
            [_result("R.10", category="memory", reviewability="manual_only")]
        )

        runner.run_review(session, pr_id=7075, trigger="resolved-manual")

        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="7075").one()
        lifecycle_event = (
            session.query(FindingLifecycleEvent)
            .filter_by(review_request_id="7075", event_type="resolved")
            .order_by(FindingLifecycleEvent.event_at.desc())
            .first()
        )

        assert thread_state.sync_status == "resolved"
        assert thread_state.resolution_reason == "remote_resolved_manual_only"
        assert lifecycle_event is not None
        assert lifecycle_event.event_reason == "remote_resolved_manual_only"
    finally:
        session.close()


def test_review_runner_recovers_stale_thread_after_resolve_failure_when_remote_thread_is_still_open() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(708)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=708, trigger="first")

        adapter.fail_resolve_refs.add("thread-1")
        runner.engine_client = EngineStub(
            [_result("R.10", category="memory", reviewability="manual_only")]
        )
        runner.run_review(session, pr_id=708, trigger="resolve-fails")

        stale_state = session.query(ThreadSyncState).filter_by(review_request_id="708").one()
        assert stale_state.sync_status == "stale"
        assert stale_state.resolution_reason == "resolve_failed"

        adapter.fail_resolve_refs.clear()
        runner.engine_client = EngineStub([_result("R.10", category="memory")])
        runner.run_review(session, pr_id=708, trigger="recovered")

        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="708").one()

        # stale 복구 후에는 reconcile이 스레드를 open으로 되돌리지만,
        # unchanged open thread 정책에 따라 새 reply를 달지 않는다.
        assert len(adapter.upsert_requests) == 1
        assert thread_state.sync_status == "open"
        assert thread_state.resolution_reason is None
        assert len(adapter.list_threads(key)) == 1
        assert len(adapter.list_threads(key)[0].notes) == 1
    finally:
        session.close()


def test_review_runner_persists_manual_reopen_without_posting_redundant_bot_reply() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(709)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=709, trigger="first")

        adapter.mark_resolved(key, "thread-1", resolved=True)
        runner.engine_client = EngineStub(
            [_result("R.10", category="memory", reviewability="manual_only")]
        )
        runner.run_review(session, pr_id=709, trigger="resolved")

        adapter.mark_resolved(key, "thread-1", resolved=False)
        runner.engine_client = EngineStub([_result("R.10", category="memory")])
        runner.run_review(session, pr_id=709, trigger="manual-reopen")

        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="709").one()

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert thread_state.sync_status == "open"
        assert adapter.list_threads(key)[0].resolved is False
        assert len(adapter.list_threads(key)[0].notes) == 2
    finally:
        session.close()


def test_reopen_records_immutable_lifecycle_event_without_erasing_fixed_history() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7091)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-a")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7091, trigger="first")

        adapter.mark_resolved(key, "thread-1", resolved=True)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-b")
        adapter.set_incremental_diff(
            key,
            base_sha="head-a",
            files=[{"path": "src/a.cpp", "patch": _malloc_patch()}],
            head_sha="head-b",
        )
        runner.engine_client = EngineStub(
            [_result("R.10", category="memory", reviewability="manual_only")]
        )
        runner.run_review(session, pr_id=7091, trigger="resolved")

        adapter.mark_resolved(key, "thread-1", resolved=False)
        adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-c")
        runner.engine_client = EngineStub([_result("R.10", category="memory")])
        runner.run_review(session, pr_id=7091, trigger="reopened")

        lifecycle_events = (
            session.query(FindingLifecycleEvent)
            .filter_by(review_request_id="7091")
            .order_by(FindingLifecycleEvent.event_at.asc())
            .all()
        )
        event_pairs = [(event.event_type, event.event_reason) for event in lifecycle_events]

        assert ("resolved", "fixed_in_followup_commit") in event_pairs
        assert ("reopened", "remote_reopened") in event_pairs
    finally:
        session.close()


def test_review_runner_records_repeated_resolve_and_unresolve_feedback_transitions() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(710)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=710, trigger="first")

        adapter.mark_resolved(key, "thread-1", resolved=True)
        runner.engine_client = EngineStub(
            [_result("R.10", category="memory", reviewability="manual_only")]
        )
        runner.run_review(session, pr_id=710, trigger="resolved")

        adapter.mark_resolved(key, "thread-1", resolved=False)
        runner.engine_client = EngineStub([_result("R.10", category="memory")])
        runner.run_review(session, pr_id=710, trigger="reopened")

        feedback = (
            session.query(FeedbackEvent)
            .filter_by(review_request_id="710")
            .order_by(FeedbackEvent.ingested_at.asc(), FeedbackEvent.event_key.asc())
            .all()
        )

        unresolved_events = [event for event in feedback if event.event_type == "unresolved"]
        resolved_events = [event for event in feedback if event.event_type == "resolved"]

        assert len(unresolved_events) == 3
        assert len(resolved_events) == 1
        assert len({event.event_key for event in unresolved_events}) == 3
    finally:
        session.close()


def test_resolved_unchanged_finding_stays_backlog_only_by_default() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(717)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=717, trigger="first")
        adapter.mark_resolved(key, "thread-1", resolved=True)

        review_run = runner.run_review(session, pr_id=717, trigger="full-reconcile")
        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="717").one()

        assert review_run.status == "success"
        assert len(adapter.upsert_requests) == 1
        assert thread_state.sync_status == "resolved"
        assert adapter.list_threads(key)[0].resolved is True
    finally:
        session.close()


def test_opt_in_resurface_can_reopen_resolved_unchanged_thread() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.settings = dataclass_replace(runner.settings, resolved_unchanged_resurface_enabled=True)
    adapter = FakeAdapter()
    key = runner._legacy_key(7170)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7170, trigger="first")
        adapter.mark_resolved(key, "thread-1", resolved=True)

        review_run = runner.run_review(session, pr_id=7170, trigger="full-reconcile")
        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="7170").one()

        assert review_run.status == "success"
        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert adapter.upsert_requests[1].reopen_if_resolved is True
        assert thread_state.sync_status == "open"
        assert adapter.list_threads(key)[0].resolved is False
    finally:
        session.close()


def test_review_runner_suppresses_finding_when_human_feedback_requests_ignore() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(718)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=718, trigger="first")
        adapter.add_human_reply(key, "thread-1", "bot:ignore\n이 코멘트는 노이즈입니다.")

        review_run = runner.run_review(session, pr_id=718, trigger="second")
        current_findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .all()
        )

        assert len(adapter.upsert_requests) == 1
        assert current_findings[0].state == "suppressed"
        assert current_findings[0].suppression_reason == "feedback:ignore"
    finally:
        session.close()


def test_review_runner_does_not_treat_plain_text_mentions_as_feedback_commands() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(719)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=719, trigger="first")
        adapter.add_human_reply(
            key,
            "thread-1",
            "문서 예시로 `bot:ignore` 문자열만 설명합니다. 실제 명령은 아닙니다.",
        )

        review_run = runner.run_review(session, pr_id=719, trigger="second")
        current_findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .all()
        )

        assert current_findings[0].state == "published"
        assert current_findings[0].suppression_reason is None
        assert len(adapter.upsert_requests) == 1
    finally:
        session.close()


def test_review_runner_skips_unreviewable_markdown_files() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7191)  # noqa: SLF001
    adapter.set_diff(key, path="docs/README.md", patch="@@ -1 +1 @@\n-Old\n+New\n")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=7191, trigger="first")

        assert review_run.status == "success"
        assert adapter.upsert_requests == []
        assert session.query(FindingEvidence).filter_by(review_run_id=review_run.id).count() == 0
    finally:
        session.close()


def test_review_comment_includes_detected_language_metadata() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7192)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7192, trigger="first")

        body = adapter.upsert_requests[0].body
        assert body.startswith("[봇 리뷰][cpp] ")
        assert "_오분류면 `@review-bot wrong-language <expected-language>`_" in body
        assert "프로필 `default`" not in body
    finally:
        session.close()


def test_wrong_language_feedback_suppresses_future_candidate() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7193)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7193, trigger="first")
        adapter.add_human_reply(
            key,
            "thread-1",
            "@review-bot wrong-language markdown\n이 파일은 문서 리뷰 기준으로 봐야 합니다.",
        )

        review_run = runner.run_review(session, pr_id=7193, trigger="second")
        current_findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .all()
        )
        feedback_event = (
            session.query(FeedbackEvent)
            .filter_by(adapter_thread_ref="thread-1", event_type="reply")
            .one()
        )

        assert len(adapter.upsert_requests) == 1
        assert current_findings[0].state == "suppressed"
        assert current_findings[0].suppression_reason == "feedback:wrong_language"
        assert feedback_event.payload["feedback_command"] == "wrong-language"
        assert feedback_event.payload["expected_language_id"] == "markdown"
    finally:
        session.close()


def test_review_runner_propagates_language_payload_per_file() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7194)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[
            {
                "path": ".github/workflows/build.yml",
                "patch": "@@ -1 +1 @@\n-permissions: read-all\n+permissions: write-all\n",
            },
            {
                "path": "warehouse/postgres/report.sql",
                "patch": "@@ -1 +1 @@\n-select 1;\n+execute format('select * from reports order by %s', sort_col);\n",
            },
            {
                "path": "docs/README.md",
                "patch": "@@ -1 +1 @@\n-Old\n+New\n",
            },
        ],
        head_sha="head-mixed",
    )
    adapter.set_file_content(
        key,
        ".github/workflows/build.yml",
        "head-mixed",
        "permissions: write-all\njobs:\n  build:\n    steps:\n      - uses: actions/checkout@main\n",
    )
    adapter.set_file_content(
        key,
        "warehouse/postgres/report.sql",
        "head-mixed",
        "execute format('select * from reports order by %s', sort_col);\n",
    )
    runner.platform_client = adapter
    engine = EngineCaptureStub()
    runner.engine_client = engine
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=7194, trigger="first")
        calls_by_path = {str(call["file_path"]): call for call in engine.review_calls}

        assert review_run.status == "success"
        assert sorted(calls_by_path) == [
            ".github/workflows/build.yml",
            "warehouse/postgres/report.sql",
        ]
        assert calls_by_path[".github/workflows/build.yml"]["language_id"] == "yaml"
        assert calls_by_path[".github/workflows/build.yml"]["profile_id"] == "github_actions"
        assert calls_by_path[".github/workflows/build.yml"]["context_id"] == "github_actions"
        assert calls_by_path[".github/workflows/build.yml"]["dialect_id"] is None
        assert "uses: actions/checkout@main" in str(
            calls_by_path[".github/workflows/build.yml"]["file_context"]
        )
        assert calls_by_path["warehouse/postgres/report.sql"]["language_id"] == "sql"
        assert calls_by_path["warehouse/postgres/report.sql"]["profile_id"] == "analytics_warehouse"
        assert calls_by_path["warehouse/postgres/report.sql"]["context_id"] == "analytics"
        assert calls_by_path["warehouse/postgres/report.sql"]["dialect_id"] == "postgresql"
        assert "execute format" in str(calls_by_path["warehouse/postgres/report.sql"]["file_context"])
    finally:
        session.close()


def test_review_runner_passes_project_ref_to_codebase_search() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7195)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    engine = EngineCaptureStub(
        results_by_path={"src/a.cpp": [_result("R.10", category="memory")]}
    )
    runner.engine_client = engine
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=7195, trigger="project-scope")

        assert review_run.status == "success"
        assert engine.search_calls
        assert engine.search_calls[0]["project_ref"] == key.project_ref
        assert engine.search_calls[0]["top_k"] == 2
    finally:
        session.close()


def test_review_runner_passes_language_metadata_to_provider_and_comment_body() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7196)  # noqa: SLF001
    adapter.set_diff(
        key,
        path="warehouse/postgres/report.sql",
        patch="@@ -1 +1 @@\n-select 1;\n+execute format('select * from reports order by %s', sort_col);\n",
        head_sha="head-sql",
    )
    adapter.set_file_content(
        key,
        "warehouse/postgres/report.sql",
        "head-sql",
        "execute format('select * from reports order by %s', sort_col);\n",
    )
    runner.platform_client = adapter
    runner.engine_client = EngineCaptureStub(
        results_by_path={
            "warehouse/postgres/report.sql": [_result("SQL.PG.2", category="security")]
        }
    )
    provider = CaptureProvider()
    runner.provider = provider

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7196, trigger="first")

        assert len(provider.build_calls) == 1
        build_call = provider.build_calls[0]
        body = adapter.upsert_requests[0].body

        assert build_call["language_id"] == "sql"
        assert build_call["profile_id"] == "analytics_warehouse"
        assert build_call["context_id"] == "analytics"
        assert build_call["dialect_id"] == "postgresql"
        assert "execute format" in str(build_call["file_context"])
        assert body.startswith("[봇 리뷰][sql] ")
        assert "프로필 `analytics_warehouse`" in body
        assert "컨텍스트 `analytics`" in body
        assert "다이얼렉트 `postgresql`" in body
    finally:
        session.close()


def test_review_runner_detects_framework_and_config_profiles_per_file() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7196)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[
            {
                "path": "app/api/users/route.ts",
                "patch": "@@ -1 +1,4 @@\n-export async function POST() { return Response.json({ ok: true }); }\n+export async function POST(request: Request) {\n+  const payload = await request.json();\n+  return Response.json(payload);\n+}\n",
            },
            {
                "path": "config/app/settings.yaml",
                "patch": "@@ -1 +1 @@\n-service:\n+service:\n+  api_key: prod-secret-token\n",
            },
            {
                "path": "db/migrations/postgres/V5__cleanup.sql",
                "patch": "@@ -1 +1,4 @@\n-select 1;\n+drop table legacy_users;\n+alter table accounts drop column legacy_flag;\n+alter table orders alter column status set not null;\n+create index idx_orders_created_at on orders(created_at);\n",
            },
        ],
        head_sha="head-framework",
    )
    adapter.set_file_content(
        key,
        "app/api/users/route.ts",
        "head-framework",
        "export async function POST(request: Request) {\n  const payload = await request.json();\n  return Response.json(payload);\n}\n",
    )
    adapter.set_file_content(
        key,
        "config/app/settings.yaml",
        "head-framework",
        "service:\n  api_key: prod-secret-token\n",
    )
    adapter.set_file_content(
        key,
        "db/migrations/postgres/V5__cleanup.sql",
        "head-framework",
        "drop table legacy_users;\nalter table accounts drop column legacy_flag;\nalter table orders alter column status set not null;\ncreate index idx_orders_created_at on orders(created_at);\n",
    )
    runner.platform_client = adapter
    engine = EngineCaptureStub()
    runner.engine_client = engine
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=7196, trigger="first")
        calls_by_path = {str(call["file_path"]): call for call in engine.review_calls}

        assert review_run.status == "success"
        assert calls_by_path["app/api/users/route.ts"]["language_id"] == "typescript"
        assert calls_by_path["app/api/users/route.ts"]["profile_id"] == "nextjs_frontend"
        assert calls_by_path["app/api/users/route.ts"]["context_id"] == "app_router"
        assert calls_by_path["config/app/settings.yaml"]["language_id"] == "yaml"
        assert calls_by_path["config/app/settings.yaml"]["profile_id"] == "product_config"
        assert calls_by_path["config/app/settings.yaml"]["context_id"] == "product_config"
        assert calls_by_path["db/migrations/postgres/V5__cleanup.sql"]["language_id"] == "sql"
        assert calls_by_path["db/migrations/postgres/V5__cleanup.sql"]["profile_id"] == "migration_sql"
        assert calls_by_path["db/migrations/postgres/V5__cleanup.sql"]["dialect_id"] == "postgresql"
    finally:
        session.close()


def test_review_runner_passes_cuda_language_metadata() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(71961)  # noqa: SLF001
    adapter.set_diff(
        key,
        path="kernels/vector_add.cu",
        patch=(
            "@@ -1,5 +1,9 @@\n"
            " __global__ void accumulate(float* dst, const float* src, int n) {\n"
            "+    extern __shared__ float scratch[];\n"
            "     int idx = blockIdx.x * blockDim.x + threadIdx.x;\n"
            "+    if (threadIdx.x == 0) {\n"
            "+        __syncthreads();\n"
            "+    }\n"
            "     if (idx < n) {\n"
            "-        dst[idx] = src[idx];\n"
            "+        atomicAdd(&dst[0], src[idx]);\n"
            "     }\n"
            " }\n"
        ),
        head_sha="head-cuda",
    )
    adapter.set_file_content(
        key,
        "kernels/vector_add.cu",
        "head-cuda",
        (
            "__global__ void accumulate(float* dst, const float* src, int n) {\n"
            "    extern __shared__ float scratch[];\n"
            "    int idx = blockIdx.x * blockDim.x + threadIdx.x;\n"
            "    if (threadIdx.x == 0) {\n"
            "        __syncthreads();\n"
            "    }\n"
            "    if (idx < n) {\n"
            "        atomicAdd(&dst[0], src[idx]);\n"
            "    }\n"
            "}\n"
        ),
    )
    runner.platform_client = adapter
    runner.engine_client = EngineCaptureStub(
        results_by_path={
            "kernels/vector_add.cu": [_result("CUDA.3", category="correctness")]
        }
    )
    provider = CaptureProvider()
    runner.provider = provider

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=71961, trigger="first")

        assert len(provider.build_calls) == 1
        build_call = provider.build_calls[0]
        body = adapter.upsert_requests[0].body

        assert build_call["language_id"] == "cuda"
        assert build_call["profile_id"] == "default"
        assert build_call["context_id"] is None
        assert build_call["dialect_id"] is None
        assert "atomicAdd" in str(build_call["file_context"])
        assert body.startswith("[봇 리뷰][cuda] ")
        assert "_오분류면 `@review-bot wrong-language <expected-language>`_" in body
        assert "프로필 `default`" not in body
    finally:
        session.close()


def test_review_runner_detects_cuda_followup_profiles() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(71962)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[
            {
                "path": "kernels/cuda_async_default_stream.cu",
                "patch": (
                    "@@ -1,5 +1,9 @@\n"
                    " void overlap_copy(float* host_dst, const float* device_src, size_t bytes, int iters) {\n"
                    "   for (int i = 0; i < iters; ++i) {\n"
                    "+    cudaStream_t stream;\n"
                    "+    cudaStreamCreate(&stream);\n"
                    "+    cudaMemcpyAsync(host_dst, device_src, bytes, cudaMemcpyDeviceToHost, 0);\n"
                    "+    cudaLaunchHostFunc(stream, on_done, host_dst);\n"
                    "+    cudaStreamDestroy(stream);\n"
                    "   }\n"
                    " }\n"
                ),
            },
            {
                "path": "kernels/cuda_pipeline_async_stage_drift.cu",
                "patch": (
                    "@@ -12,5 +12,19 @@\n"
                    "   for (int tile = 0; tile < tiles; ++tile) {\n"
                    "     int stage = tile % 2;\n"
                    "     float* shared_tile = smem + stage * block.size();\n"
                    "+    if (threadIdx.x == 0) {\n"
                    "+      pipe.producer_acquire();\n"
                    "+    }\n"
                    "+    cuda::memcpy_async(block, shared_tile, in + tile * block.size(), cuda::aligned_size_t<4>(sizeof(float) * block.size()), pipe);\n"
                    "+    consume_stage(out, shared_tile, block.size());\n"
                    "+    if (threadIdx.x == 0) {\n"
                    "+      pipe.producer_commit();\n"
                    "+      pipe.consumer_wait();\n"
                    "+    }\n"
                    "+    if (threadIdx.x < 16) {\n"
                    "+      ready.arrive_and_wait();\n"
                    "+    }\n"
                    "+    pipe.consumer_release();\n"
                    "   }\n"
                    " }\n"
                ),
            },
            {
                "path": "kernels/cuda_thread_block_cluster_dsm.cu",
                "patch": (
                    "@@ -5,7 +5,17 @@\n"
                    " __global__ void cluster_histogram(int* bins, const int* input, int count) {\n"
                    "   extern __shared__ int smem[];\n"
                    "   auto cluster = cg::this_cluster();\n"
                    "+  if (cluster.block_rank() == 0) {\n"
                    "+    cluster.sync();\n"
                    "+  }\n"
                    "+  int* remote_hist = cluster.map_shared_rank(smem, (cluster.block_rank() + 1) % cluster.num_blocks());\n"
                    "+  atomicAdd(remote_hist + (threadIdx.x % 32), 1);\n"
                    "+  cluster.sync();\n"
                    " }\n"
                    " \n"
                    " void launch_cluster_histogram(int* bins, const int* input, int count) {\n"
                    "+  cluster_histogram<<<blocks, threads, 128 * sizeof(int)>>>(bins, input, count);\n"
                    " }\n"
                ),
            },
            {
                "path": "kernels/cuda_tma_tensor_map_contract.cu",
                "patch": (
                    "@@ -8,5 +8,22 @@\n"
                    " __global__ void load_tile_tma(CUtensorMap* tensor_map, float* out) {\n"
                    "   __shared__ alignas(128) CUtensorMap smem_tmap;\n"
                    "   __shared__ alignas(1024) int4 smem_tile[8][8];\n"
                    "   __shared__ cuda::barrier<cuda::thread_scope_block> bar;\n"
                    "+  if (threadIdx.x == 0) {\n"
                    "+    smem_tmap = *tensor_map;\n"
                    "+    ptx::tensormap_replace_global_address(ptx::space_shared, &smem_tmap, out);\n"
                    "+    ptx::cp_async_bulk_tensor(\n"
                    "+      ptx::space_shared,\n"
                    "+      ptx::space_global,\n"
                    "+      &smem_tile,\n"
                    "+      tensor_map,\n"
                    "+      coords,\n"
                    "+      cuda::device::barrier_native_handle(bar));\n"
                    "+    cuda::device::barrier_arrive_tx(bar, 1, sizeof(smem_tile));\n"
                    "+  }\n"
                    "+  consume_tile(smem_tile, out);\n"
                    " }\n"
                ),
            },
            {
                "path": "kernels/cuda_wgmma_async_group_drift.cu",
                "patch": (
                    "@@ -6,5 +6,14 @@\n"
                    " __global__ void warpgroup_gemm(const uint64_t* desc_a, const uint64_t* desc_b, half* out) {\n"
                    "   __shared__ float accum[64];\n"
                    "   int lane = threadIdx.x % warpSize;\n"
                    "+  int warpgroup = threadIdx.x / 128;\n"
                    "+  if (warpgroup == 0) {\n"
                    "+    asm volatile(\"wgmma.mma_async.sync.aligned.m64n128k16.f32.f16.f16\");\n"
                    "+  }\n"
                    "+  if (lane == 0) {\n"
                    "+    asm volatile(\"wgmma.commit_group.sync.aligned;\");\n"
                    "+  }\n"
                    "+  epilogue_store(out, accum);\n"
                    "+  if (lane == 0) {\n"
                    "+    asm volatile(\"wgmma.wait_group.sync.aligned 0;\");\n"
                    "+  }\n"
                    " }\n"
                ),
            },
            {
                "path": "distributed/cuda_multigpu_nccl.cu",
                "patch": (
                    "@@ -1,5 +1,12 @@\n"
                    " void run_collective(float* device0, float* device1, size_t elements, cudaStream_t* streams, ncclComm_t* comms, int gpu_count) {\n"
                    "+  for (int device = 0; device < gpu_count; ++device) {\n"
                    "+    cudaSetDevice(device);\n"
                    "+  }\n"
                    "+  cudaDeviceEnablePeerAccess(1, 0);\n"
                    "+  cudaMemcpyPeerAsync(device1, 1, device0, 0, elements * sizeof(float), streams[0]);\n"
                    "+  ncclGroupStart();\n"
                    "+  ncclAllReduce((const void*)device0, device0, elements, ncclFloat, ncclSum, comms[0], streams[0]);\n"
                    "+  ncclGroupEnd();\n"
                    " }\n"
                ),
            },
            {
                "path": "kernels/cuda_tensor_core_wmma.cu",
                "patch": (
                    "@@ -6,5 +6,11 @@\n"
                    "     wmma::fragment<wmma::matrix_b, 16, 16, 16, half, wmma::col_major> b_frag;\n"
                    "     wmma::fragment<wmma::accumulator, 16, 16, 16, float> acc_frag;\n"
                    "+    if (lane == 0) {\n"
                    "+        wmma::load_matrix_sync(a_frag, a, lda);\n"
                    "+    }\n"
                    "+    asm volatile(\"mma.sync.aligned.m16n8k16.row.col.f32.f16.f16.f32\");\n"
                    "     wmma::load_matrix_sync(b_frag, b, ldb);\n"
                    "     wmma::fill_fragment(acc_frag, 0.0f);\n"
                    "     wmma::mma_sync(acc_frag, a_frag, b_frag, acc_frag);\n"
                    "+    out[threadIdx.x] = __float2half_rn(acc_frag.x[0]);\n"
                    " }\n"
                ),
            },
            {
                "path": "kernels/cuda_cooperative_groups_grid_sync.cu",
                "patch": (
                    "@@ -3,5 +3,14 @@\n"
                    " namespace cg = cooperative_groups;\n"
                    " \n"
                    " __global__ void persistent_reduce(float* dst) {\n"
                    "+  cg::thread_block block = cg::this_thread_block();\n"
                    "+  if (threadIdx.x < 16) {\n"
                    "+    auto tile = cg::tiled_partition<16>(block);\n"
                    "+    tile.sync();\n"
                    "+  }\n"
                    "+  auto grid = cg::this_grid();\n"
                    "+  grid.sync();\n"
                    "+  if (threadIdx.x == 0) {\n"
                    "+    cg::sync(block);\n"
                    "+  }\n"
                    "   dst[threadIdx.x] = static_cast<float>(threadIdx.x);\n"
                    " }\n"
                ),
            },
        ],
        head_sha="head-cuda-profiles",
    )
    adapter.set_file_content(
        key,
        "kernels/cuda_async_default_stream.cu",
        "head-cuda-profiles",
        (
            "void overlap_copy(float* host_dst, const float* device_src, size_t bytes, int iters) {\n"
            "  for (int i = 0; i < iters; ++i) {\n"
            "    cudaStream_t stream;\n"
            "    cudaStreamCreate(&stream);\n"
            "    cudaMemcpyAsync(host_dst, device_src, bytes, cudaMemcpyDeviceToHost, 0);\n"
            "    cudaLaunchHostFunc(stream, on_done, host_dst);\n"
            "    cudaStreamDestroy(stream);\n"
            "  }\n"
            "}\n"
        ),
    )
    adapter.set_file_content(
        key,
        "kernels/cuda_pipeline_async_stage_drift.cu",
        "head-cuda-profiles",
        (
            "#include <cuda/barrier>\n"
            "#include <cuda/pipeline>\n"
            "#include <cooperative_groups.h>\n"
            "namespace cg = cooperative_groups;\n"
            "__device__ void consume_stage(float* out, const float* tile, int count) {\n"
            "  if (threadIdx.x < count) {\n"
            "    out[threadIdx.x] += tile[threadIdx.x];\n"
            "  }\n"
            "}\n"
            "__global__ void stage_tiles(float* out, const float* in, int tiles) {\n"
            "  extern __shared__ float smem[];\n"
            "  __shared__ cuda::pipeline_shared_state<cuda::thread_scope_block, 2> pipe_state;\n"
            "  __shared__ cuda::barrier<cuda::thread_scope_block> ready;\n"
            "  auto block = cg::this_thread_block();\n"
            "  auto pipe = cuda::make_pipeline(block, &pipe_state);\n"
            "  if (block.thread_rank() == 0) {\n"
            "    init(&ready, block.size());\n"
            "  }\n"
            "  block.sync();\n"
            "  for (int tile = 0; tile < tiles; ++tile) {\n"
            "    int stage = tile % 2;\n"
            "    float* shared_tile = smem + stage * block.size();\n"
            "    if (threadIdx.x == 0) {\n"
            "      pipe.producer_acquire();\n"
            "    }\n"
            "    cuda::memcpy_async(block, shared_tile, in + tile * block.size(), cuda::aligned_size_t<4>(sizeof(float) * block.size()), pipe);\n"
            "    consume_stage(out, shared_tile, block.size());\n"
            "    if (threadIdx.x == 0) {\n"
            "      pipe.producer_commit();\n"
            "      pipe.consumer_wait();\n"
            "    }\n"
            "    if (threadIdx.x < 16) {\n"
            "      ready.arrive_and_wait();\n"
            "    }\n"
            "    pipe.consumer_release();\n"
            "  }\n"
            "}\n"
        ),
    )
    adapter.set_file_content(
        key,
        "kernels/cuda_thread_block_cluster_dsm.cu",
        "head-cuda-profiles",
        (
            "#include <cooperative_groups.h>\n"
            "namespace cg = cooperative_groups;\n"
            "__global__ void cluster_histogram(int* bins, const int* input, int count) {\n"
            "  extern __shared__ int smem[];\n"
            "  auto cluster = cg::this_cluster();\n"
            "  if (cluster.block_rank() == 0) {\n"
            "    cluster.sync();\n"
            "  }\n"
            "  int* remote_hist = cluster.map_shared_rank(smem, (cluster.block_rank() + 1) % cluster.num_blocks());\n"
            "  atomicAdd(remote_hist + (threadIdx.x % 32), 1);\n"
            "  cluster.sync();\n"
            "}\n"
            "void launch_cluster_histogram(int* bins, const int* input, int count) {\n"
            "  dim3 blocks(6, 1, 1);\n"
            "  dim3 threads(128, 1, 1);\n"
            "  cluster_histogram<<<blocks, threads, 128 * sizeof(int)>>>(bins, input, count);\n"
            "}\n"
        ),
    )
    adapter.set_file_content(
        key,
        "kernels/cuda_tma_tensor_map_contract.cu",
        "head-cuda-profiles",
        (
            "#include <cuda.h>\n"
            "#include <cuda/barrier>\n"
            "#include <cuda/ptx>\n"
            "namespace ptx = cuda::ptx;\n"
            "__device__ void consume_tile(const int4 tile[8][8], float* out) {\n"
            "  out[threadIdx.x % 8] += static_cast<float>(tile[threadIdx.x % 8][0].x);\n"
            "}\n"
            "__global__ void load_tile_tma(CUtensorMap* tensor_map, float* out) {\n"
            "  __shared__ alignas(128) CUtensorMap smem_tmap;\n"
            "  __shared__ alignas(1024) int4 smem_tile[8][8];\n"
            "  __shared__ cuda::barrier<cuda::thread_scope_block> bar;\n"
            "  if (threadIdx.x == 0) {\n"
            "    smem_tmap = *tensor_map;\n"
            "    ptx::tensormap_replace_global_address(ptx::space_shared, &smem_tmap, out);\n"
            "    ptx::cp_async_bulk_tensor(\n"
            "      ptx::space_shared,\n"
            "      ptx::space_global,\n"
            "      &smem_tile,\n"
            "      tensor_map,\n"
            "      coords,\n"
            "      cuda::device::barrier_native_handle(bar));\n"
            "    cuda::device::barrier_arrive_tx(bar, 1, sizeof(smem_tile));\n"
            "  }\n"
            "  consume_tile(smem_tile, out);\n"
            "}\n"
        ),
    )
    adapter.set_file_content(
        key,
        "kernels/cuda_wgmma_async_group_drift.cu",
        "head-cuda-profiles",
        (
            "__device__ void epilogue_store(half* out, const float* accum) {\n"
            "  out[threadIdx.x] = __float2half_rn(accum[threadIdx.x % 64]);\n"
            "}\n"
            "__global__ void warpgroup_gemm(const uint64_t* desc_a, const uint64_t* desc_b, half* out) {\n"
            "  __shared__ float accum[64];\n"
            "  int lane = threadIdx.x % warpSize;\n"
            "  int warpgroup = threadIdx.x / 128;\n"
            "  if (warpgroup == 0) {\n"
            "    asm volatile(\"wgmma.mma_async.sync.aligned.m64n128k16.f32.f16.f16\");\n"
            "  }\n"
            "  if (lane == 0) {\n"
            "    asm volatile(\"wgmma.commit_group.sync.aligned;\");\n"
            "  }\n"
            "  epilogue_store(out, accum);\n"
            "  if (lane == 0) {\n"
            "    asm volatile(\"wgmma.wait_group.sync.aligned 0;\");\n"
            "  }\n"
            "}\n"
        ),
    )
    adapter.set_file_content(
        key,
        "distributed/cuda_multigpu_nccl.cu",
        "head-cuda-profiles",
        (
            "void run_collective(float* device0, float* device1, size_t elements, cudaStream_t* streams, ncclComm_t* comms, int gpu_count) {\n"
            "  for (int device = 0; device < gpu_count; ++device) {\n"
            "    cudaSetDevice(device);\n"
            "  }\n"
            "  cudaDeviceEnablePeerAccess(1, 0);\n"
            "  cudaMemcpyPeerAsync(device1, 1, device0, 0, elements * sizeof(float), streams[0]);\n"
            "  ncclGroupStart();\n"
            "  ncclAllReduce((const void*)device0, device0, elements, ncclFloat, ncclSum, comms[0], streams[0]);\n"
            "  ncclGroupEnd();\n"
            "}\n"
        ),
    )
    adapter.set_file_content(
        key,
        "kernels/cuda_tensor_core_wmma.cu",
        "head-cuda-profiles",
        (
            "#include <mma.h>\n"
            "__global__ void tensor_core_gemm(const half* a, const half* b, half* out, int lda, int ldb) {\n"
            "  int lane = threadIdx.x % warpSize;\n"
            "  wmma::fragment<wmma::accumulator, 16, 16, 16, float> acc_frag;\n"
            "  if (lane == 0) {\n"
            "    wmma::load_matrix_sync(a_frag, a, lda);\n"
            "  }\n"
            "  asm volatile(\"mma.sync.aligned.m16n8k16.row.col.f32.f16.f16.f32\");\n"
            "  wmma::mma_sync(acc_frag, a_frag, b_frag, acc_frag);\n"
            "  out[threadIdx.x] = __float2half_rn(acc_frag.x[0]);\n"
            "}\n"
        ),
    )
    adapter.set_file_content(
        key,
        "kernels/cuda_cooperative_groups_grid_sync.cu",
        "head-cuda-profiles",
        (
            "#include <cooperative_groups.h>\n"
            "namespace cg = cooperative_groups;\n"
            "void persistent_reduce(float* dst) {\n"
            "  cg::thread_block block = cg::this_thread_block();\n"
            "  if (threadIdx.x < 16) {\n"
            "    auto tile = cg::tiled_partition<16>(block);\n"
            "    tile.sync();\n"
            "  }\n"
            "  auto grid = cg::this_grid();\n"
            "  grid.sync();\n"
            "  if (threadIdx.x == 0) {\n"
            "    cg::sync(block);\n"
            "  }\n"
            "}\n"
        ),
    )
    runner.platform_client = adapter
    engine = EngineCaptureStub()
    runner.engine_client = engine
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=71962, trigger="first")
        calls_by_path = {str(call["file_path"]): call for call in engine.review_calls}

        assert review_run.status == "success"
        assert calls_by_path["kernels/cuda_async_default_stream.cu"]["language_id"] == "cuda"
        assert calls_by_path["kernels/cuda_async_default_stream.cu"]["profile_id"] == "cuda_async_runtime"
        assert calls_by_path["kernels/cuda_pipeline_async_stage_drift.cu"]["language_id"] == "cuda"
        assert calls_by_path["kernels/cuda_pipeline_async_stage_drift.cu"]["profile_id"] == "cuda_pipeline_async"
        assert calls_by_path["kernels/cuda_thread_block_cluster_dsm.cu"]["language_id"] == "cuda"
        assert (
            calls_by_path["kernels/cuda_thread_block_cluster_dsm.cu"]["profile_id"]
            == "cuda_thread_block_cluster"
        )
        assert calls_by_path["kernels/cuda_tma_tensor_map_contract.cu"]["language_id"] == "cuda"
        assert calls_by_path["kernels/cuda_tma_tensor_map_contract.cu"]["profile_id"] == "cuda_tma"
        assert calls_by_path["kernels/cuda_wgmma_async_group_drift.cu"]["language_id"] == "cuda"
        assert calls_by_path["kernels/cuda_wgmma_async_group_drift.cu"]["profile_id"] == "cuda_wgmma"
        assert calls_by_path["distributed/cuda_multigpu_nccl.cu"]["language_id"] == "cuda"
        assert calls_by_path["distributed/cuda_multigpu_nccl.cu"]["profile_id"] == "cuda_multigpu"
        assert calls_by_path["kernels/cuda_tensor_core_wmma.cu"]["language_id"] == "cuda"
        assert calls_by_path["kernels/cuda_tensor_core_wmma.cu"]["profile_id"] == "cuda_tensor_core"
        assert calls_by_path["kernels/cuda_cooperative_groups_grid_sync.cu"]["language_id"] == "cuda"
        assert calls_by_path["kernels/cuda_cooperative_groups_grid_sync.cu"]["profile_id"] == "cuda_cooperative_groups"
    finally:
        session.close()


def test_wrong_language_feedback_analytics_reports_detected_vs_expected_language() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(7197)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=7197, trigger="first")
        adapter.add_human_reply(
            key,
            "thread-1",
            "@review-bot wrong-language markdown\n이 파일은 문서로 취급해야 합니다.",
        )
        runner.run_review(session, pr_id=7197, trigger="second")

        report = runner.wrong_language_feedback_analytics(session, window="28d")

        assert report["total_events"] == 1
        assert report["distinct_threads"] == 1
        assert report["distinct_findings"] == 1
        assert report["smoke_events"] == 0
        assert report["production_events"] == 1
        assert report["unknown_provenance_events"] == 0
        assert report["top_language_pairs"][0] == {
            "detected_language_id": "cpp",
            "expected_language_id": "markdown",
            "count": 1,
        }
        assert report["top_profiles"][0]["profile_id"] == "default"
        assert report["top_paths"][0]["path_pattern"] == "src"
        assert report["triage_candidates"][0] == {
            "detected_language_id": "cpp",
            "expected_language_id": "markdown",
            "profile_id": "default",
            "context_id": None,
            "path_pattern": "src",
            "count": 1,
            "priority": "low",
            "provenance": "production",
            "triage_cause": "wrong_thread_target",
            "actionability": "inspect_thread",
            "suggested_action": (
                "감지 언어가 파일 경로/context와 더 잘 맞습니다. detector 수정 전에 "
                "wrong-language reply 대상 thread와 기대 언어가 맞는지 먼저 확인하세요."
            ),
        }
    finally:
        session.close()


def test_wrong_language_classifier_marks_smoke_and_actionable_detector_miss() -> None:
    smoke_provenance = classify_wrong_language_provenance(
        "root/review-system-multilang-smoke",
        "@review-bot wrong-language markdown\ntelemetry 점검",
    )
    smoke_cause = classify_wrong_language_cause(
        detected_language_id="yaml",
        expected_language_id="markdown",
        profile_id="gitlab_ci",
        context_id="gitlab_ci",
        file_path=".gitlab-ci.yml",
        provenance=smoke_provenance,
    )
    docs_cause = classify_wrong_language_cause(
        detected_language_id="cpp",
        expected_language_id="markdown",
        profile_id="default",
        context_id=None,
        file_path="README.md",
        provenance="production",
    )

    assert smoke_provenance == "smoke"
    assert smoke_cause == "synthetic_smoke"
    assert wrong_language_actionability(smoke_cause) == "ignore_for_detector_backlog"
    assert docs_cause == "detector_miss"
    assert wrong_language_actionability(docs_cause) == "fix_detector"


def test_feedback_path_bucket_normalizes_root_markdown_paths_to_docs() -> None:
    runner = ReviewRunner()

    assert runner._feedback_path_bucket("README.md") == "docs"  # noqa: SLF001
    assert runner._feedback_path_bucket("guide/overview.mdx") == "docs"  # noqa: SLF001
    assert runner._feedback_path_bucket("docs/architecture/overview.md") == "docs"  # noqa: SLF001


def test_wrong_language_suggested_action_prefers_docs_only_for_docs_like_paths() -> None:
    runner = ReviewRunner()

    assert (
        runner._wrong_language_suggested_action(  # noqa: SLF001
            detected_language_id="markdown",
            expected_language_id="yaml",
            profile_id="default",
            context_id=None,
            path_pattern="docs",
        )
        == "문서 경로를 reviewable 대상에서 더 명확히 제외하고, 유사 확장자/경로 예외 규칙을 detector backlog에 추가하세요."
    )
    assert (
        runner._wrong_language_suggested_action(  # noqa: SLF001
            detected_language_id="yaml",
            expected_language_id="markdown",
            profile_id="gitlab_ci",
            context_id="gitlab_ci",
            path_pattern=".gitlab-ci.yml",
        )
        == "문서형 경로가 아닌데 `markdown` 기대값이 들어왔습니다. detector 오분류인지, wrong-language reply 대상 thread가 맞는지 먼저 확인하고 feedback regression 예제를 함께 보강하세요."
    )


def test_build_state_and_full_report_use_latest_created_run() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(8010)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-a")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider(summary_suffix="first")

    session = SessionLocal()
    try:
        first_run = runner.run_review(session, pr_id=8010, trigger="first")

        adapter.set_diff(key, path="src/b.cpp", patch=_continue_patch(), head_sha="head-b")
        runner.engine_client = EngineStub([_result("ES.77", category="control_flow")])
        runner.provider = FixedProvider(
            title="두 번째 run finding",
            summary="두 번째 run에서 생성된 finding입니다.",
        )
        second_run = runner.run_review(session, pr_id=8010, trigger="second")

        first_run = session.get(type(first_run), first_run.id)
        second_run = session.get(type(second_run), second_run.id)
        assert first_run is not None
        assert second_run is not None

        first_run.completed_at = (second_run.completed_at or datetime.now(UTC)) + timedelta(minutes=5)
        session.commit()

        state = runner.build_state(session, key=key)
        report = runner.build_full_report(session, key=key)

        assert state["last_review_run_id"] == second_run.id
        assert state["last_head_sha"] == "head-b"
        assert report["last_review_run_id"] == second_run.id
        assert report["last_head_sha"] == "head-b"
        assert [item["file_path"] for item in report["published_inline"]] == ["src/b.cpp"]
    finally:
        session.close()


def test_review_runner_records_dead_letter_for_failed_publication() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter(fail_inline=True)
    key = runner._legacy_key(726)  # noqa: SLF001
    adapter.set_diff(key, path="src/flow.cpp", patch=_continue_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ES.77", category="control_flow")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=726, trigger="inline-failure")
        dead_letters = session.query(DeadLetterRecord).filter_by(review_run_id=review_run.id).all()
        state = runner.build_state(session, 726)

        assert review_run.status == "partial"
        assert len(dead_letters) == 1
        assert dead_letters[0].stage == "publish"
        assert dead_letters[0].error_category == "inline_anchor"
        assert state["dead_letter_count"] == 1
    finally:
        session.close()


def test_review_runner_does_not_fallback_to_general_note_when_inline_publish_fails() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter(fail_inline=True)
    key = runner._legacy_key(727)  # noqa: SLF001
    adapter.set_diff(key, path="src/flow.cpp", patch=_continue_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ES.77", category="control_flow")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=727, trigger="inline-failure")
        findings = session.query(FindingDecision).filter_by(review_request_id="727").all()

        assert review_run.status == "partial"
        assert adapter.list_threads(key) == []
        assert findings
        assert all(item.state == "failed_publication" for item in findings)
        assert all("inline discussion" in (item.publication_error or "") for item in findings)
    finally:
        session.close()


def test_review_runner_suppresses_gitlab_invalid_line_code_without_marking_run_partial() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter(
        fail_inline=True,
        fail_inline_message=(
            "Unable to create inline discussion for src/a.cpp:10: "
            'GitLab POST failed with 400: {"message":"400 Bad request - '
            'Note {:line_code=>[\\"can\'t be blank\\", \\"must be a valid line code\\"]}"}'
        ),
    )
    key = runner._legacy_key(728)  # noqa: SLF001
    adapter.set_diff(key, path="src/flow.cpp", patch=_continue_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ES.77", category="control_flow")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=728, trigger="inline-invalid-line-code")
        findings = session.query(FindingDecision).filter_by(review_request_id="728").all()
        dead_letters = session.query(DeadLetterRecord).filter_by(review_run_id=review_run.id).all()

        assert review_run.status == "success"
        assert adapter.list_threads(key) == []
        assert findings
        assert all(item.state == "suppressed" for item in findings)
        assert all(item.suppression_reason == "inline_anchor_unavailable" for item in findings)
        assert dead_letters == []
    finally:
        session.close()


def test_review_runner_applies_path_policy_suppression() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.policy = ReviewPolicy(
        path_policies=(
            PathPolicy(
                glob="src/id/**",
                suppress_rules=frozenset({"R.10"}),
            ),
        )
    )
    adapter = FakeAdapter()
    key = runner._legacy_key(777)  # noqa: SLF001
    adapter.set_diff(key, path="src/id/ids/idsTde.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=777, trigger="path-policy")
        findings = session.query(FindingDecision).filter_by(review_run_id=review_run.id).all()

        assert review_run.status == "success"
        assert len(findings) == 1
        assert findings[0].state == "suppressed"
        assert findings[0].suppression_reason == "policy:path_rule_suppressed"
        assert adapter.upsert_requests == []
    finally:
        session.close()


def test_review_runner_detects_manual_only_findings_but_suppresses_publish() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(808)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub(
        [_result("R.10", category="memory", reviewability="manual_only")]
    )
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=808, trigger="manual-only")
        findings = session.query(FindingDecision).filter_by(review_request_id="808").all()

        assert review_run.status == "success"
        assert len(findings) == 1
        assert findings[0].state == "suppressed"
        assert findings[0].suppression_reason == "reviewability:manual_only"
        assert adapter.upsert_requests == []
    finally:
        session.close()


def test_review_runner_suppresses_user_facing_duplicate_comments_in_same_batch() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(909)  # noqa: SLF001
    adapter.set_diff(key, path="src/flow.cpp", patch=_continue_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub(
        [
            _result("ES.77", category="control_flow"),
            _result("ES.78", category="control_flow"),
        ]
    )
    runner.provider = FixedProvider(
        title="루프 흐름이 `continue`에 의존하고 있습니다",
        summary="같은 사용자 메시지로 수렴하는 경우입니다.",
    )

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=909, trigger="dedupe")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .order_by(FindingDecision.rule_no.asc())
            .all()
        )

        assert review_run.status == "success"
        assert len(adapter.upsert_requests) == 1
        assert [finding.state for finding in findings] == ["published", "suppressed"]
        assert findings[1].suppression_reason == "publish_batch_duplicate"
    finally:
        session.close()


def test_review_runner_ignores_provider_line_no_for_anchor_and_batch_dedupe() -> None:
    _reset_db()

    class OffsetLineProvider(ReviewCommentProvider):
        def __init__(self) -> None:
            self.returned_line_nos: dict[str, int] = {}

        def build_draft(self, **kwargs) -> FindingDraft:
            rule_no = kwargs["rule_no"]
            provider_line_no = (kwargs.get("line_no") or 0) + (
                100 if rule_no == "ES.77" else 200
            )
            self.returned_line_nos[rule_no] = provider_line_no
            return FindingDraft(
                title="루프 흐름이 `continue`에 의존하고 있습니다",
                summary="같은 사용자 메시지로 수렴하는 경우입니다.",
                suggested_fix="조건 분기를 명시적으로 정리해 주세요.",
                should_publish=True,
                line_no=provider_line_no,
            )

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(910)  # noqa: SLF001
    adapter.set_diff(key, path="src/flow.cpp", patch=_continue_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub(
        [
            _result("ES.77", category="control_flow"),
            _result("ES.78", category="control_flow"),
        ]
    )
    provider = OffsetLineProvider()
    runner.provider = provider

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=910, trigger="provider-line")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .order_by(FindingDecision.rule_no.asc())
            .all()
        )

        assert review_run.status == "success"
        assert len(adapter.upsert_requests) == 1
        assert [finding.state for finding in findings] == ["published", "suppressed"]
        assert findings[1].suppression_reason == "publish_batch_duplicate"
        assert adapter.upsert_requests[0].anchor.start_line == findings[0].line_no
        assert (
            adapter.upsert_requests[0].anchor.start_line
            != provider.returned_line_nos["ES.77"]
        )
    finally:
        session.close()


def test_review_runner_suppresses_same_line_same_category_variants_before_batch_selection() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(911)  # noqa: SLF001
    adapter.set_diff(key, path="src/flow.cpp", patch=_continue_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub(
        [
            _result("ES.77", category="control_flow", score=0.92),
            _result("ES.78", category="control_flow", score=0.81),
        ]
    )
    runner.provider = ScenarioProvider(
        {
            ("src/flow.cpp", "ES.77"): FindingDraft(
                title="루프 탈출 조건이 분산되어 있습니다",
                summary="첫 번째 제어 흐름 설명입니다.",
                suggested_fix="조건을 앞쪽에서 정리해 주세요.",
            ),
            ("src/flow.cpp", "ES.78"): FindingDraft(
                title="`continue` 중심 흐름이 읽기 어렵습니다",
                summary="같은 줄의 변형 phrasing입니다.",
                suggested_fix="조건 분기를 더 직접적으로 표현해 주세요.",
            ),
        }
    )

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=911, trigger="same-line-category")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .order_by(FindingDecision.rule_no.asc())
            .all()
        )

        assert review_run.status == "success"
        assert len(adapter.upsert_requests) == 1
        assert [finding.state for finding in findings] == ["published", "suppressed"]
        assert findings[0].rule_no == "ES.77"
        assert findings[1].suppression_reason == "publish_batch_same_line_category"
    finally:
        session.close()


def test_review_runner_blockquotes_multiline_evidence_snippet() -> None:
    _reset_db()

    class EvidenceProvider(ReviewCommentProvider):
        def build_draft(self, **kwargs) -> FindingDraft:
            return FindingDraft(
                title="멀티라인 증거 예시",
                summary="증거 인용 렌더링을 검증합니다.",
                suggested_fix="증거 줄이 모두 quote 되어야 합니다.",
                should_publish=True,
                line_no=kwargs.get("line_no"),
                evidence_snippet="if (!ready) {\n    return;\n}",
            )

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(912)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = EvidenceProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=912, trigger="blockquote")

        body = adapter.upsert_requests[0].body
        assert "> if (!ready) {" in body
        assert ">     return;" in body
        assert "> }" in body
    finally:
        session.close()


@dataclass
class EngineStub:
    results: list[dict[str, object]]
    detected_patterns: list[str] | None = None

    def review_diff(
        self,
        diff: str,
        top_k: int = 8,
        *,
        file_path: str | None = None,
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
    ) -> dict[str, object]:
        del diff, top_k, file_path, file_context, language_id, profile_id, context_id, dialect_id
        return {
            "detected_patterns": list(self.detected_patterns or []),
            "results": [dict(result) for result in self.results],
        }

    def search_codebase(self, query: str, top_k: int = 3) -> list[dict]:
        del query, top_k
        return []


@dataclass
class SequentialEngineStub:
    responses: list[list[dict[str, object]]]
    detected_patterns: list[str] | None = None

    def __post_init__(self) -> None:
        self._index = 0

    def review_diff(
        self,
        diff: str,
        top_k: int = 8,
        *,
        file_path: str | None = None,
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
    ) -> dict[str, object]:
        del diff, top_k, file_path, file_context, language_id, profile_id, context_id, dialect_id
        response_index = min(self._index, len(self.responses) - 1)
        self._index += 1
        return {
            "detected_patterns": list(self.detected_patterns or []),
            "results": [dict(result) for result in self.responses[response_index]],
        }

    def search_codebase(self, query: str, top_k: int = 3) -> list[dict]:
        del query, top_k
        return []


class FixedProvider(ReviewCommentProvider):
    def __init__(
        self,
        *,
        title: str = "메모리를 직접 할당하고 해제하고 있습니다",
        summary: str = "이 변경은 소유권을 직접 관리합니다.",
        summary_suffix: str = "",
    ) -> None:
        self.title = title
        self.summary = summary
        self.summary_suffix = summary_suffix

    def build_draft(self, **kwargs) -> FindingDraft:
        line_no = kwargs.get("line_no")
        title = self.title
        summary = self.summary
        if self.summary_suffix:
            summary = f"{summary} [{self.summary_suffix}]"
        return FindingDraft(
            title=title,
            summary=summary,
            suggested_fix="RAII 또는 프로젝트 표준 wrapper로 옮겨 주세요.",
            should_publish=True,
            line_no=line_no,
        )


@dataclass
class EngineCaptureStub:
    results_by_path: dict[str, list[dict[str, object]]] = field(default_factory=dict)
    detected_patterns: list[str] | None = None
    review_calls: list[dict[str, object]] = field(default_factory=list)
    search_calls: list[dict[str, object]] = field(default_factory=list)

    def review_diff(
        self,
        diff: str,
        top_k: int = 8,
        *,
        file_path: str | None = None,
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
    ) -> dict[str, object]:
        self.review_calls.append(
            {
                "diff": diff,
                "top_k": top_k,
                "file_path": file_path,
                "file_context": file_context,
                "language_id": language_id,
                "profile_id": profile_id,
                "context_id": context_id,
                "dialect_id": dialect_id,
            }
        )
        return {
            "detected_patterns": list(self.detected_patterns or []),
            "results": [dict(result) for result in self.results_by_path.get(str(file_path), [])],
        }

    def search_codebase(
        self,
        query: str,
        top_k: int = 3,
        *,
        project_ref: str | None = None,
    ) -> list[dict]:
        self.search_calls.append(
            {
                "query": query,
                "top_k": top_k,
                "project_ref": project_ref,
            }
        )
        return []


class ScenarioProvider(ReviewCommentProvider):
    def __init__(self, mapping: dict[tuple[str, str], FindingDraft]) -> None:
        self.mapping = mapping

    def build_draft(self, **kwargs) -> FindingDraft:
        key = (kwargs["file_path"], kwargs["rule_no"])
        draft = self.mapping[key]
        return FindingDraft(
            title=draft.title,
            summary=draft.summary,
            suggested_fix=draft.suggested_fix,
            severity=draft.severity,
            confidence=draft.confidence,
            should_publish=draft.should_publish,
            line_no=kwargs.get("line_no"),
        )


class CaptureProvider(ReviewCommentProvider):
    def __init__(self) -> None:
        self.build_calls: list[dict[str, object]] = []

    def build_draft(self, **kwargs) -> FindingDraft:
        self.build_calls.append(dict(kwargs))
        return FindingDraft(
            title="언어 메타데이터 캡처",
            summary="provider로 언어 메타데이터가 전달되었습니다.",
            suggested_fix="전파 검증용 코멘트입니다.",
            should_publish=True,
            line_no=kwargs.get("line_no"),
        )


class VerifyScenarioProvider(FixedProvider):
    def __init__(
        self,
        *,
        verify_result: VerifyDraftResult | None = None,
        verify_error: Exception | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.verify_result = verify_result or VerifyDraftResult()
        self.verify_error = verify_error

    def verify_draft(self, **kwargs) -> VerifyDraftResult:
        del kwargs
        if self.verify_error is not None:
            raise self.verify_error
        return self.verify_result


class FakeAdapter:
    def __init__(
        self,
        *,
        fail_inline: bool = False,
        fail_inline_message: str | None = None,
    ) -> None:
        self.fail_inline = fail_inline
        self.fail_inline_message = fail_inline_message
        self.meta_by_key: dict[tuple[str, str, str], ReviewRequestMeta] = {}
        self.diff_by_key: dict[tuple[str, str, str], DiffPayload] = {}
        self.incremental_diff_by_key_and_base: dict[
            tuple[tuple[str, str, str], str], DiffPayload
        ] = {}
        self.file_contents_by_key_and_ref: dict[tuple[tuple[str, str, str], str, str], str] = {}
        self.threads_by_key: dict[tuple[str, str, str], list[ThreadSnapshot]] = {}
        self.upsert_requests = []
        self.publish_checks = []
        self.general_notes: list[str] = []
        self.general_note_index_by_purpose: dict[str, int] = {}
        self.resolved_threads: list[str] = []
        self.fail_resolve_refs: set[str] = set()
        self._thread_index = 0
        self._comment_index = 0
        self._clock_index = 0

    def set_diff(
        self,
        key: ReviewRequestKey,
        *,
        path: str,
        patch: str,
        head_sha: str = "abc123",
    ) -> None:
        self.set_files_diff(
            key,
            files=[{"path": path, "patch": patch}],
            head_sha=head_sha,
        )

    def set_files_diff(
        self,
        key: ReviewRequestKey,
        *,
        files: list[dict[str, str]],
        head_sha: str = "abc123",
    ) -> None:
        key_tuple = _key_tuple(key)
        self.meta_by_key[key_tuple] = ReviewRequestMeta(
            key=key,
            title=f"MR {key.review_request_id}",
            source_branch="feature",
            target_branch="main",
            base_sha="base123",
            start_sha="start123",
            head_sha=head_sha,
        )
        self.diff_by_key[key_tuple] = DiffPayload(
            pull_request={
                "id": key.review_request_id,
                "base_sha": "base123",
                "start_sha": "start123",
                "head_sha": head_sha,
            },
            files=[
                DiffFile(
                    path=item["path"],
                    status="modified",
                    patch=item["patch"],
                    old_path=item["path"],
                    new_path=item["path"],
                )
                for item in files
            ],
        )

    def set_incremental_diff(
        self,
        key: ReviewRequestKey,
        *,
        base_sha: str,
        files: list[dict[str, str]],
        head_sha: str,
    ) -> None:
        key_tuple = _key_tuple(key)
        self.incremental_diff_by_key_and_base[(key_tuple, base_sha)] = DiffPayload(
            pull_request={
                "id": key.review_request_id,
                "base_sha": base_sha,
                "start_sha": "start123",
                "head_sha": head_sha,
            },
            files=[
                DiffFile(
                    path=item["path"],
                    status="modified",
                    patch=item["patch"],
                    old_path=item.get("old_path") or item["path"],
                    new_path=item.get("new_path") or item["path"],
                )
                for item in files
            ],
        )

    def fetch_review_request_meta(self, key: ReviewRequestKey) -> ReviewRequestMeta:
        return self.meta_by_key[_key_tuple(key)]

    def fetch_diff(
        self,
        key: ReviewRequestKey,
        *,
        mode: str,
        base_sha: str | None = None,
    ) -> DiffPayload:
        if mode == "incremental" and base_sha:
            incremental = self.incremental_diff_by_key_and_base.get((_key_tuple(key), base_sha))
            if incremental is not None:
                return incremental
        return self.diff_by_key[_key_tuple(key)]

    def set_file_content(
        self,
        key: ReviewRequestKey,
        path: str,
        ref: str,
        content: str,
    ) -> None:
        self.file_contents_by_key_and_ref[(_key_tuple(key), path, ref)] = content

    def fetch_file_content(
        self,
        key: ReviewRequestKey,
        path: str,
        ref: str,
    ) -> str | None:
        return self.file_contents_by_key_and_ref.get((_key_tuple(key), path, ref))

    def list_threads(self, key: ReviewRequestKey) -> list[ThreadSnapshot]:
        return list(self.threads_by_key.get(_key_tuple(key), []))

    def upsert_comment(
        self,
        key: ReviewRequestKey,
        request,
    ) -> CommentUpsertResult:
        self.upsert_requests.append(request)
        if self.fail_inline:
            raise ReviewBotError(
                self.fail_inline_message or "Unable to create inline discussion for test",
                category="inline_anchor",
                retryable=False,
            )

        key_tuple = _key_tuple(key)
        threads = self.threads_by_key.setdefault(key_tuple, [])

        if request.existing_thread_ref:
            thread = next(item for item in threads if item.thread_ref == request.existing_thread_ref)
            if request.reopen_if_resolved:
                thread.resolved = False
            note_ref = self._next_note_ref()
            now = self._now()
            thread.notes.append(
                ThreadNoteSnapshot(
                    note_ref=note_ref,
                    body=request.body,
                    author_type="bot",
                    created_at=now,
                )
            )
            thread.updated_at = now
            return CommentUpsertResult(
                ok=True,
                action="updated",
                comment_ref=note_ref,
                thread_ref=thread.thread_ref,
            )

        thread_ref = self._next_thread_ref()
        note_ref = self._next_note_ref()
        now = self._now()
        threads.append(
            ThreadSnapshot(
                thread_ref=thread_ref,
                comment_ref=note_ref,
                resolved=False,
                resolvable=True,
                body=request.body,
                updated_at=now,
                notes=[
                    ThreadNoteSnapshot(
                        note_ref=note_ref,
                        body=request.body,
                        author_type="bot",
                        created_at=now,
                    )
                ],
            )
        )
        return CommentUpsertResult(
            ok=True,
            action="created",
            comment_ref=note_ref,
            thread_ref=thread_ref,
        )

    def resolve_thread(
        self,
        key: ReviewRequestKey,
        thread_ref: str,
        *,
        reason: str,
    ) -> dict[str, str | bool]:
        del reason
        if thread_ref in self.fail_resolve_refs:
            raise ReviewBotError(
                "Unable to resolve thread for test",
                category="gitlab_api",
                retryable=True,
            )
        thread = next(
            item for item in self.threads_by_key.get(_key_tuple(key), []) if item.thread_ref == thread_ref
        )
        thread.resolved = True
        thread.updated_at = self._now()
        self.resolved_threads.append(thread_ref)
        return {"ok": True, "resolved": True}

    def publish_check(self, key: ReviewRequestKey, request) -> CheckPublishResult:
        del key
        self.publish_checks.append(request)
        return CheckPublishResult(
            ok=True,
            state=request.state,
            description=request.description,
        )

    def post_general_note(self, key: ReviewRequestKey, body: str) -> dict[str, bool]:
        del key
        self.general_notes.append(body)
        return {"ok": True}

    def upsert_general_note(
        self,
        key: ReviewRequestKey,
        *,
        body: str,
        purpose: str,
    ) -> dict[str, str | bool]:
        del key
        index = self.general_note_index_by_purpose.get(purpose)
        if index is None:
            self.general_note_index_by_purpose[purpose] = len(self.general_notes)
            self.general_notes.append(body)
            return {"ok": True, "action": "created"}
        self.general_notes[index] = body
        return {"ok": True, "action": "updated"}

    def collect_feedback(
        self,
        key: ReviewRequestKey,
        *,
        since: str | None = None,
    ) -> FeedbackPage:
        del since
        events: list[FeedbackRecord] = []
        for thread in self.threads_by_key.get(_key_tuple(key), []):
            transition_marker = _feedback_time_key(thread.updated_at)
            events.append(
                FeedbackRecord(
                    event_key=f"{thread.thread_ref}:resolved:{transition_marker}:{int(thread.resolved)}",
                    event_type="resolved" if thread.resolved else "unresolved",
                    adapter_thread_ref=thread.thread_ref,
                    adapter_comment_ref=thread.comment_ref,
                    actor_type="system",
                    payload={"resolved": thread.resolved},
                    occurred_at=thread.updated_at,
                )
            )
            for note in thread.notes[1:]:
                if note.author_type != "human":
                    continue
                events.append(
                    FeedbackRecord(
                        event_key=f"{thread.thread_ref}:reply:{note.note_ref}",
                        event_type="reply",
                        adapter_thread_ref=thread.thread_ref,
                        adapter_comment_ref=note.note_ref,
                        actor_type="human",
                        actor_ref=note.author_ref,
                        payload={"body": note.body},
                        occurred_at=note.created_at,
                    )
                )
        return FeedbackPage(events=events)

    def add_human_reply(
        self,
        key: ReviewRequestKey,
        thread_ref: str,
        body: str,
        *,
        author_ref: str = "reviewer",
    ) -> None:
        thread = next(
            item for item in self.threads_by_key.get(_key_tuple(key), []) if item.thread_ref == thread_ref
        )
        now = self._now()
        thread.notes.append(
            ThreadNoteSnapshot(
                note_ref=self._next_note_ref(),
                body=body,
                author_type="human",
                author_ref=author_ref,
                created_at=now,
            )
        )
        thread.updated_at = now

    def mark_resolved(self, key: ReviewRequestKey, thread_ref: str, *, resolved: bool) -> None:
        thread = next(
            item for item in self.threads_by_key.get(_key_tuple(key), []) if item.thread_ref == thread_ref
        )
        thread.resolved = resolved
        thread.updated_at = self._now()

    def _next_thread_ref(self) -> str:
        self._thread_index += 1
        return f"thread-{self._thread_index}"

    def _next_note_ref(self) -> str:
        self._comment_index += 1
        return f"note-{self._comment_index}"

    def _now(self) -> datetime:
        self._clock_index += 1
        return datetime(2026, 4, 20, tzinfo=UTC) + timedelta(seconds=self._clock_index)


def _result(
    rule_no: str,
    *,
    category: str,
    score: float = 0.95,
    reviewability: str = "auto_review",
    false_positive_risk: str = "low",
) -> dict[str, object]:
    return {
        "rule_no": rule_no,
        "source_family": "cpp_core",
        "authority": "external",
        "conflict_policy": "compatible",
        "title": f"{rule_no} title",
        "section": rule_no.split("-")[0] if "-" in rule_no else rule_no.split(".")[0],
        "priority": score,
        "score": score,
        "summary": f"{rule_no} summary",
        "text": f"{rule_no} text",
        "category": category,
        "reviewability": reviewability,
        "false_positive_risk": false_positive_risk,
    }


def _key_tuple(key: ReviewRequestKey) -> tuple[str, str, str]:
    return (key.review_system, key.project_ref, key.review_request_id)


def _feedback_time_key(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    return value.strftime("%Y%m%dT%H%M%S%f%z")


def _counter_value(counter, **labels) -> float:
    return float(counter.labels(**labels)._value.get())


def _malloc_patch() -> str:
    return (
        "@@ -1,2 +1,4 @@\n"
        "+ char* p = (char*)malloc(10);\n"
        "+ free(p);\n"
    )


def _multi_hunk_malloc_patch() -> str:
    return (
        "@@ -1,2 +1,4 @@\n"
        "+ char* p = (char*)malloc(10);\n"
        "+ free(p);\n"
        "@@ -120,2 +130,4 @@\n"
        "+ char* q = (char*)malloc(20);\n"
        "+ free(q);\n"
    )


def _yaml_k8s_long_container_patch() -> str:
    for case in load_review_unit_split_cases():
        if case.case_id == "yaml_k8s_long_container_env":
            return case.patch
    raise AssertionError("yaml_k8s_long_container_env case is missing")


def _python_fastapi_long_handler_patch() -> str:
    for case in load_review_unit_split_cases():
        if case.case_id == "python_fastapi_long_handler":
            return case.patch
    raise AssertionError("python_fastapi_long_handler case is missing")


def _typescript_react_long_component_patch() -> str:
    for case in load_review_unit_split_cases():
        if case.case_id == "typescript_react_long_component":
            return case.patch
    raise AssertionError("typescript_react_long_component case is missing")


def _continue_patch() -> str:
    return (
        "@@ -10,2 +10,3 @@\n"
        "+ if (skip) {\n"
        "+     continue;\n"
        "+ }\n"
    )


def test_open_thread_with_changed_body_updates_existing_thread() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(8001)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    provider = FixedProvider(summary_suffix="v1")
    runner.provider = provider

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=8001, trigger="first")
        provider.summary_suffix = "v2"
        runner.run_review(session, pr_id=8001, trigger="second")

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
    finally:
        session.close()


def test_feedback_false_positive_suppresses_future_candidate() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(8002)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=8002, trigger="first")
        adapter.add_human_reply(key, "thread-1", "bot:false-positive\n이 경고는 오탐입니다.")

        review_run = runner.run_review(session, pr_id=8002, trigger="second")
        current_findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .all()
        )

        assert len(adapter.upsert_requests) == 1
        assert current_findings[0].state == "suppressed"
        assert current_findings[0].suppression_reason == "feedback:false_positive"
    finally:
        session.close()


def test_feedback_allow_overrides_false_positive_request() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(80021)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    provider = FixedProvider(summary_suffix="v1")
    runner.provider = provider

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=80021, trigger="first")
        adapter.add_human_reply(key, "thread-1", "bot:false-positive\n이 경고는 오탐입니다.")
        provider.summary_suffix = "v2"
        runner.run_review(session, pr_id=80021, trigger="second")
        adapter.add_human_reply(key, "thread-1", "bot:allow\n지금은 다시 검토해도 됩니다.")
        provider.summary_suffix = "v3"

        review_run = runner.run_review(session, pr_id=80021, trigger="third")
        current_findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .all()
        )

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert current_findings[0].state == "published"
        assert current_findings[0].suppression_reason is None
    finally:
        session.close()


def test_feedback_later_keeps_candidate_out_of_inline_publish() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(8003)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=8003, trigger="first")
        adapter.add_human_reply(key, "thread-1", "bot:later\n나중에 처리하겠습니다.")

        runner.run_review(session, pr_id=8003, trigger="second")

        assert len(adapter.upsert_requests) == 1
    finally:
        session.close()


def test_feedback_allow_overrides_later_request() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(80031)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    provider = FixedProvider(summary_suffix="v1")
    runner.provider = provider

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=80031, trigger="first")
        adapter.add_human_reply(key, "thread-1", "bot:later\n나중에 처리하겠습니다.")
        provider.summary_suffix = "v2"
        runner.run_review(session, pr_id=80031, trigger="second")
        adapter.add_human_reply(key, "thread-1", "bot:allow\n이제 다시 보여줘도 됩니다.")
        provider.summary_suffix = "v3"

        review_run = runner.run_review(session, pr_id=80031, trigger="third")
        current_findings = (
            session.query(FindingDecision)
            .filter_by(review_run_id=review_run.id)
            .all()
        )

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert current_findings[0].state == "published"
        assert current_findings[0].suppression_reason is None
    finally:
        session.close()


def test_pr_summary_includes_feedback_backlog_and_suppressed_counts() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(80032)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[
            {"path": "src/a.cpp", "patch": _malloc_patch()},
            {"path": "src/b.cpp", "patch": _continue_patch()},
            {"path": "src/c.cpp", "patch": _malloc_patch()},
        ],
        head_sha="head-a",
    )
    runner.platform_client = adapter
    runner.engine_client = SequentialEngineStub(
        [
            [_result("R.10", category="memory")],
            [_result("ES.77", category="control_flow")],
            [_result("I.4", category="type_usage")],
        ]
    )
    runner.provider = ScenarioProvider(
        {
            ("src/a.cpp", "R.10"): FindingDraft(
                title="src/a.cpp 메모리 소유권 관리",
                summary="이 코드는 직접 메모리 해제를 전제로 합니다.",
                suggested_fix="RAII wrapper를 사용해 주세요.",
            ),
            ("src/b.cpp", "ES.77"): FindingDraft(
                title="src/b.cpp 제어 흐름 단순화",
                summary="continue 중심 제어 흐름은 가독성을 떨어뜨립니다.",
                suggested_fix="조건 분기를 정리해 주세요.",
            ),
            ("src/c.cpp", "I.4"): FindingDraft(
                title="src/c.cpp 타입 사용 개선",
                summary="명시적 타입 의도를 더 분명히 해 주세요.",
                suggested_fix="프로젝트 표준 타입 alias를 사용해 주세요.",
            ),
            ("src/d.cpp", "ERR.TEST.001"): FindingDraft(
                title="src/d.cpp 오류 처리 일관성",
                summary="새로운 오류 처리 finding입니다.",
                suggested_fix="반환값 검사를 추가해 주세요.",
            ),
        }
    )

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=80032, trigger="first")
        adapter.add_human_reply(key, "thread-1", "bot:ignore\n이번 건은 의도된 구현입니다.")
        adapter.add_human_reply(key, "thread-2", "bot:false-positive\n이 경고는 오탐입니다.")
        adapter.add_human_reply(key, "thread-3", "bot:later\n다음 정리 때 처리하겠습니다.")

        adapter.set_files_diff(
            key,
            files=[
                {"path": "src/a.cpp", "patch": _malloc_patch()},
                {"path": "src/b.cpp", "patch": _continue_patch()},
                {"path": "src/c.cpp", "patch": _malloc_patch()},
                {"path": "src/d.cpp", "patch": _continue_patch()},
            ],
            head_sha="head-b",
        )
        runner.engine_client = SequentialEngineStub(
            [
                [_result("R.10", category="memory")],
                [_result("ES.77", category="control_flow")],
                [_result("I.4", category="type_usage")],
                [_result("ERR.TEST.001", category="error_handling")],
            ]
        )

        runner.run_review(session, pr_id=80032, trigger="second")

        assert len(adapter.general_notes) == 2
        summary = adapter.general_notes[-1]
        assert "총 **1개** 항목이 게시되었습니다." in summary
        assert "사용자 피드백(`bot:later`)으로 보류된 항목: 1개." in summary
        assert "무시된 항목 1개" in summary
        assert "오탐으로 처리된 항목 1개" in summary
        assert "기존 열린 이슈 1개는 재게시하지 않고 backlog로 유지했습니다." not in summary
    finally:
        session.close()


def test_build_full_report_classifies_backlog_and_feedback_sections() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(80033)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[
            {"path": "src/a.cpp", "patch": _malloc_patch()},
            {"path": "src/b.cpp", "patch": _continue_patch()},
            {"path": "src/c.cpp", "patch": _malloc_patch()},
        ],
        head_sha="head-a",
    )
    runner.platform_client = adapter
    runner.engine_client = SequentialEngineStub(
        [
            [_result("R.10", category="memory")],
            [_result("ES.77", category="control_flow")],
            [_result("I.4", category="type_usage")],
        ]
    )
    runner.provider = ScenarioProvider(
        {
            ("src/a.cpp", "R.10"): FindingDraft(
                title="src/a.cpp 메모리 소유권 관리",
                summary="이 코드는 직접 메모리 해제를 전제로 합니다.",
                suggested_fix="RAII wrapper를 사용해 주세요.",
            ),
            ("src/b.cpp", "ES.77"): FindingDraft(
                title="src/b.cpp 제어 흐름 단순화",
                summary="continue 중심 제어 흐름은 가독성을 떨어뜨립니다.",
                suggested_fix="조건 분기를 정리해 주세요.",
            ),
            ("src/c.cpp", "I.4"): FindingDraft(
                title="src/c.cpp 타입 사용 개선",
                summary="명시적 타입 의도를 더 분명히 해 주세요.",
                suggested_fix="프로젝트 표준 타입 alias를 사용해 주세요.",
            ),
            ("src/d.cpp", "ERR.TEST.001"): FindingDraft(
                title="src/d.cpp 오류 처리 일관성",
                summary="새로운 오류 처리 finding입니다.",
                suggested_fix="반환값 검사를 추가해 주세요.",
            ),
        }
    )

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=80033, trigger="first")
        adapter.add_human_reply(key, "thread-1", "bot:ignore\n이번 건은 의도된 구현입니다.")
        adapter.add_human_reply(key, "thread-2", "bot:false-positive\n이 경고는 오탐입니다.")
        adapter.add_human_reply(key, "thread-3", "bot:later\n다음 정리 때 처리하겠습니다.")

        adapter.set_files_diff(
            key,
            files=[
                {"path": "src/a.cpp", "patch": _malloc_patch()},
                {"path": "src/b.cpp", "patch": _continue_patch()},
                {"path": "src/c.cpp", "patch": _malloc_patch()},
                {"path": "src/d.cpp", "patch": _continue_patch()},
            ],
            head_sha="head-b",
        )
        runner.engine_client = SequentialEngineStub(
            [
                [_result("R.10", category="memory")],
                [_result("ES.77", category="control_flow")],
                [_result("I.4", category="type_usage")],
                [_result("ERR.TEST.001", category="error_handling")],
            ]
        )

        runner.run_review(session, pr_id=80033, trigger="second")
        report = runner.build_full_report(session, key=key)

        assert report["last_status"] == "success"
        assert report["counts"]["published_inline"] == 1
        assert report["counts"]["backlog_feedback_later"] == 1
        assert report["counts"]["suppressed_feedback_ignore"] == 1
        assert report["counts"]["suppressed_feedback_false_positive"] == 1
        assert [item["file_path"] for item in report["published_inline"]] == ["src/d.cpp"]
        assert [item["file_path"] for item in report["backlog_feedback_later"]] == ["src/c.cpp"]
        assert [item["file_path"] for item in report["suppressed_feedback_ignore"]] == ["src/a.cpp"]
        assert [item["file_path"] for item in report["suppressed_feedback_false_positive"]] == ["src/b.cpp"]
    finally:
        session.close()


def test_post_full_report_note_posts_backlog_overview() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(80034)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[
            {"path": "src/a.cpp", "patch": _malloc_patch()},
            {"path": "src/b.cpp", "patch": _continue_patch()},
        ],
        head_sha="head-a",
    )
    runner.platform_client = adapter
    runner.engine_client = SequentialEngineStub(
        [
            [_result("R.10", category="memory")],
            [_result("ES.77", category="control_flow")],
        ]
    )
    runner.provider = ScenarioProvider(
        {
            ("src/a.cpp", "R.10"): FindingDraft(
                title="src/a.cpp 메모리 소유권 관리",
                summary="이 코드는 직접 메모리 해제를 전제로 합니다.",
                suggested_fix="RAII wrapper를 사용해 주세요.",
            ),
            ("src/b.cpp", "ES.77"): FindingDraft(
                title="src/b.cpp 제어 흐름 단순화",
                summary="continue 중심 제어 흐름은 가독성을 떨어뜨립니다.",
                suggested_fix="조건 분기를 정리해 주세요.",
            ),
        }
    )

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=80034, trigger="first")
        adapter.add_human_reply(key, "thread-2", "bot:later\n다음 정리 때 처리하겠습니다.")
        runner.engine_client = SequentialEngineStub(
            [
                [_result("R.10", category="memory")],
                [_result("ES.77", category="control_flow")],
            ]
        )
        runner.run_review(session, pr_id=80034, trigger="second")

        assert runner.post_full_report_note(session, key=key, adapter=adapter) is True
        note = adapter.general_notes[-1]
        assert "자동 리뷰 Full Report" in note
        assert "### 요약" in note
        assert "`bot:later` 보류: 1개" in note
        assert "src/b.cpp" in note
        assert (
            "왜 보였나: 사용자가 `bot:later`를 남겨 현재 backlog에서 보류 상태로 유지됩니다."
            in note
        )
    finally:
        session.close()


def test_render_full_report_note_includes_surfacing_reason_detail_for_suppressed_items() -> None:
    runner = ReviewRunner()
    key = runner._legacy_key(800344)  # noqa: SLF001
    report = runner._empty_full_report(key)  # noqa: SLF001
    report["review_request_title"] = "이유 설명"
    report["last_review_run_id"] = "run-1"
    report["last_status"] = "success"
    report["last_head_sha"] = "head-1"
    report["report_review_run_id"] = "run-1"
    report["report_status"] = "success"
    report["report_head_sha"] = "head-1"
    report["counts"]["pending_batch"] = 1
    report["pending_batch"] = [
        {
            "fingerprint": "fp-pending",
            "file_path": "src/pending.cpp",
            "line_no": 12,
            "rule_no": "TEST.PENDING.001",
            "severity": "medium",
            "title": "배치 대기 finding",
            "summary": "현재 batch 대기 상태입니다.",
            "state": "eligible",
            "disposition": "pending_batch",
            "reason": None,
            "score_final": 0.6,
            "thread_ref": None,
        }
    ]
    report["counts"]["suppressed_other"] = 1
    report["suppressed_other"] = [
        {
            "fingerprint": "fp-suppressed",
            "file_path": "src/suppressed.cpp",
            "line_no": 20,
            "rule_no": "TEST.SUPPRESSED.001",
            "severity": "medium",
            "title": "verify suppress",
            "summary": "verify가 suppress한 항목입니다.",
            "state": "suppressed",
            "disposition": "suppressed_other",
            "reason": "verify:not_a_real_bug",
            "score_final": 0.5,
            "thread_ref": None,
        }
    ]

    note = runner._render_full_report_note(report)  # noqa: SLF001

    assert (
        "왜 보였나: 이번 run에서 감지됐지만 현재 batch limit 때문에 아직 inline으로 게시되지 않았습니다."
        in note
    )
    assert (
        "왜 보였나: verify 단계에서 실제 이슈로 보기 어렵다고 판정되어 이번 run에서 suppress되었습니다."
        in note
    )
    assert "reason: `verify:not_a_real_bug`" in note


def test_full_report_prefers_latest_completed_run_while_showing_in_flight_run() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(800340)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch(), head_sha="head-a")
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider(summary_suffix="done")

    session = SessionLocal()
    try:
        completed_run = runner.run_review(session, pr_id=800340, trigger="first")
        queued_run = runner.create_review_run_for_key(
            session,
            key,
            trigger="second",
            mode="manual",
            meta=adapter.fetch_review_request_meta(key),
        )

        report = runner.build_full_report(session, key=key)

        assert report["last_review_run_id"] == queued_run.id
        assert report["last_status"] == "queued"
        assert report["report_review_run_id"] == completed_run.id
        assert report["report_status"] == "success"
        assert report["in_flight_review_run_id"] == queued_run.id
        assert report["in_flight_status"] == "queued"
        assert report["counts"]["published_inline"] == 1

        assert runner.post_full_report_note(session, key=key, adapter=adapter) is True
        note = adapter.general_notes[-1]
        assert "보고서 기준 run" in note
        assert "진행 중 run" in note
        assert "가장 최근에 완료된 run 기준입니다." in note
    finally:
        session.close()


def test_post_full_report_note_upserts_same_purpose_general_note() -> None:
    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(800343)  # noqa: SLF001
    report = runner._empty_full_report(key)  # noqa: SLF001
    report["last_review_run_id"] = "run-1"
    report["last_status"] = "success"
    report["last_head_sha"] = "head-1"
    report["report_review_run_id"] = "run-1"
    report["report_status"] = "success"
    report["report_head_sha"] = "head-1"
    report["review_request_title"] = "첫 번째"
    report["counts"]["backlog_existing_open"] = 1
    report["backlog_existing_open"] = [
        {
            "fingerprint": "fp-1",
            "file_path": "src/a.cpp",
            "line_no": 10,
            "rule_no": "TEST.RULE.001",
            "severity": "medium",
            "title": "첫 번째 backlog",
            "summary": "첫 번째 내용",
            "state": "backlog",
            "disposition": "backlog_existing_open",
            "reason": "existing_open_thread",
            "score_final": 0.5,
            "thread_ref": "thread-1",
        }
    ]

    original_build_full_report = runner.build_full_report
    runner.build_full_report = lambda *args, **kwargs: report
    session = SessionLocal()
    try:
        assert runner.post_full_report_note(session, key=key, adapter=adapter) is True
        assert len(adapter.general_notes) == 1
        assert "첫 번째 backlog" in adapter.general_notes[0]

        report["review_request_title"] = "두 번째"
        report["backlog_existing_open"][0]["title"] = "두 번째 backlog"

        assert runner.post_full_report_note(session, key=key, adapter=adapter) is True
        assert len(adapter.general_notes) == 1
        assert "두 번째 backlog" in adapter.general_notes[0]
    finally:
        runner.build_full_report = original_build_full_report
        session.close()


def test_post_full_report_note_truncates_long_general_note() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(800341)  # noqa: SLF001
    report = runner._empty_full_report(key)  # noqa: SLF001
    report["review_request_title"] = "긴 Full Report"
    report["last_review_run_id"] = "run-long"
    report["last_status"] = "success"
    report["last_head_sha"] = "head-long"

    long_items = []
    for idx in range(30):
        long_items.append(
            {
                "fingerprint": f"fp-{idx}",
                "file_path": f"src/file_{idx}.cpp",
                "line_no": idx + 1,
                "rule_no": "LONG.RULE.001",
                "severity": "high",
                "title": f"긴 제목 {idx} " + ("T" * 120),
                "summary": "요약 " + ("S" * 260),
                "state": "published",
                "disposition": "published_inline",
                "reason": "created",
                "score_final": 0.99,
                "thread_ref": f"thread-{idx}",
            }
        )
    report["published_inline"] = long_items
    report["counts"]["published_inline"] = len(long_items)

    original_build_full_report = runner.build_full_report
    runner.build_full_report = lambda *args, **kwargs: report

    session = SessionLocal()
    try:
        assert runner.post_full_report_note(session, key=key, adapter=adapter) is True
        note = adapter.general_notes[-1]
        assert len(note) <= MAX_COMMENT_BODY
        assert "일부 항목이 잘렸습니다" in note
    finally:
        runner.build_full_report = original_build_full_report
        session.close()


def test_pr_summary_general_note_is_truncated_when_too_long() -> None:
    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(800342)  # noqa: SLF001
    published_candidates = [
        SimpleNamespace(
            decision=SimpleNamespace(severity="high", file_path=f"src/file_{idx}.cpp"),
            draft=SimpleNamespace(title=f"아주 긴 제목 {idx} " + ("X" * 180)),
        )
        for idx in range(80)
    ]

    runner._post_pr_summary(
        adapter=adapter,
        key=key,
        review_run=SimpleNamespace(),
        published_candidates=published_candidates,
        batch_no=3,
    )

    note = adapter.general_notes[-1]
    assert len(note) <= MAX_COMMENT_BODY
    assert "일부 항목이 잘렸습니다" in note


def test_opt_in_reminder_mode_can_restore_old_behavior() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.settings = dataclass_replace(runner.settings, repeat_open_thread_reminder_enabled=True)
    adapter = FakeAdapter()
    key = runner._legacy_key(8004)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("R.10", category="memory")])
    runner.provider = FixedProvider(summary_suffix="same")

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=8004, trigger="first")
        runner.run_review(session, pr_id=8004, trigger="second")

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert len(adapter.list_threads(key)[0].notes) == 2
    finally:
        session.close()


def test_build_full_report_preserves_backlog_across_incremental_runs() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(80099)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[
            {"path": "src/a.cpp", "patch": _malloc_patch()},
            {"path": "src/b.cpp", "patch": _continue_patch()},
        ],
        head_sha="head-a",
    )
    runner.platform_client = adapter
    runner.engine_client = SequentialEngineStub(
        [
            [_result("R.10", category="memory")],
            [_result("ES.77", category="control_flow")],
        ]
    )
    runner.provider = ScenarioProvider(
        {
            ("src/a.cpp", "R.10"): FindingDraft(
                title="src/a.cpp 메모리 소유권 관리",
                summary="이 코드는 직접 메모리 해제를 전제로 합니다.",
                suggested_fix="RAII wrapper를 사용해 주세요.",
            ),
            ("src/b.cpp", "ES.77"): FindingDraft(
                title="src/b.cpp 제어 흐름 단순화",
                summary="continue 중심 제어 흐름은 가독성을 떨어뜨립니다.",
                suggested_fix="조건 분기를 정리해 주세요.",
            ),
            ("src/c.cpp", "I.4"): FindingDraft(
                title="src/c.cpp 타입 사용 개선",
                summary="명시적 타입 의도를 더 분명히 해 주세요.",
                suggested_fix="프로젝트 표준 타입 alias를 사용해 주세요.",
            ),
        }
    )

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=80099, trigger="first")
        open_threads = (
            session.query(ThreadSyncState)
            .filter_by(review_request_id="80099", sync_status="open")
            .count()
        )
        assert open_threads == 2

        # Second run is incremental and only touches src/c.cpp. The sync
        # phase should leave the existing open threads for a/b alone.
        adapter.set_files_diff(
            key,
            files=[{"path": "src/c.cpp", "patch": _malloc_patch()}],
            head_sha="head-b",
        )
        runner.engine_client = SequentialEngineStub(
            [
                [_result("I.4", category="type_usage")],
            ]
        )
        second_run = runner.create_review_run_for_key(
            session, key, trigger="second", mode="incremental"
        )
        runner.execute_review_run(session, second_run.id)

        report = runner.build_full_report(session, key=key)

        assert report["counts"]["published_inline"] == 1
        assert [item["file_path"] for item in report["published_inline"]] == ["src/c.cpp"]
        assert report["counts"]["backlog_existing_open"] == 2
        backlog_files = sorted(
            item["file_path"] for item in report["backlog_existing_open"]
        )
        assert backlog_files == ["src/a.cpp", "src/b.cpp"]
    finally:
        session.close()


def test_post_backlog_note_posts_backlog_only_view() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(80101)  # noqa: SLF001
    adapter.set_files_diff(
        key,
        files=[{"path": "src/a.cpp", "patch": _malloc_patch()}],
        head_sha="head-a",
    )
    runner.platform_client = adapter
    runner.engine_client = SequentialEngineStub(
        [[_result("R.10", category="memory")]]
    )
    runner.provider = ScenarioProvider(
        {
            ("src/a.cpp", "R.10"): FindingDraft(
                title="src/a.cpp 메모리 소유권 관리",
                summary="이 코드는 직접 메모리 해제를 전제로 합니다.",
                suggested_fix="RAII wrapper를 사용해 주세요.",
            ),
            ("src/b.cpp", "ES.77"): FindingDraft(
                title="src/b.cpp 제어 흐름 단순화",
                summary="continue 중심 제어 흐름은 가독성을 떨어뜨립니다.",
                suggested_fix="조건 분기를 정리해 주세요.",
            ),
        }
    )

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=80101, trigger="first")

        adapter.set_files_diff(
            key,
            files=[{"path": "src/b.cpp", "patch": _continue_patch()}],
            head_sha="head-b",
        )
        runner.engine_client = SequentialEngineStub(
            [[_result("ES.77", category="control_flow")]]
        )
        second_run = runner.create_review_run_for_key(
            session, key, trigger="second", mode="incremental"
        )
        runner.execute_review_run(session, second_run.id)

        assert runner.post_backlog_note(session, key=key, adapter=adapter) is True
        note = adapter.general_notes[-1]
        assert "자동 리뷰 Backlog" in note
        # Backlog note must NOT include the run-specific published-inline section.
        assert "이번 run에서 inline으로 게시된 항목" not in note
        assert "기존 open thread backlog" in note
        assert "src/a.cpp" in note
        assert (
            "왜 보였나: 현재 MR에 같은 finding의 open thread가 남아 있어 backlog로 집계됐습니다."
            in note
        )

        backlog_report = runner.build_full_report(session, key=key, view="backlog")
        assert backlog_report["counts"]["published_inline"] == 0
        assert backlog_report["published_inline"] == []
        assert backlog_report["counts"]["backlog_existing_open"] == 1
    finally:
        session.close()


def test_load_rule_effectiveness_weights_uses_distinct_fingerprint() -> None:
    _reset_db()

    runner = ReviewRunner()
    session = SessionLocal()
    try:
        from review_bot.db.models import (
            FindingDecision as FD,
            FindingEvidence as FE,
            ReviewRequest,
            ReviewRun,
            ThreadSyncState as TSS,
        )

        review_request = ReviewRequest(
            review_system="gitlab",
            project_ref="group/project",
            review_request_id="500",
        )
        session.add(review_request)
        session.flush()

        review_run = ReviewRun(
            review_request_pk=review_request.id,
            review_system="gitlab",
            project_ref="group/project",
            review_request_id="500",
            trigger="test",
            mode="manual",
            status="success",
        )
        session.add(review_run)
        session.flush()

        evidence = FE(
            review_run_id=review_run.id,
            review_request_pk=review_request.id,
            file_path="src/a.cpp",
            patch_digest="digest",
            change_snippet="",
        )
        session.add(evidence)
        session.flush()

        fingerprints = [f"fp-{idx}" for idx in range(6)]
        # Resolve 3 out of 6 unique findings.
        human_resolved = set(fingerprints[:3])
        for fp in human_resolved:
            session.add(
                TSS(
                    review_request_pk=review_request.id,
                    review_system="gitlab",
                    project_ref="group/project",
                    review_request_id="500",
                    finding_fingerprint=fp,
                    anchor_signature="sig",
                    adapter_thread_ref=f"thread-{fp}",
                    sync_status="resolved",
                    resolution_reason="remote_resolved",
                )
            )

        # Insert 20 decision rows per fingerprint to simulate reruns.
        for fp in fingerprints:
            for run_idx in range(20):
                state = "resolved" if fp in human_resolved else "published"
                session.add(
                    FD(
                        review_run_id=review_run.id,
                        evidence_id=evidence.id,
                        review_request_pk=review_request.id,
                        review_system="gitlab",
                        project_ref="group/project",
                        review_request_id="500",
                        fingerprint=fp,
                        dedupe_key=f"dk-{fp}-{run_idx}",
                        file_path="src/a.cpp",
                        rule_no="TEST.RULE.001",
                        source_family="cpp_core",
                        score_raw=0.9,
                        score_final=0.9,
                        anchor_signature="sig",
                        state=state,
                    )
                )
        session.commit()

        weights = runner._load_rule_effectiveness_weights(session)  # noqa: SLF001
        assert "TEST.RULE.001" in weights
        # 3 human-resolved out of 6 unique fingerprints = 0.5 → weight ≈ 1.2.
        assert weights["TEST.RULE.001"] == 1.2
    finally:
        session.close()


def _seed_rule_effectiveness_project(
    session,
    *,
    project_ref: str,
    review_request_id: str,
    resolved_fingerprints: set[str],
    all_fingerprints: list[str],
) -> None:
    from review_bot.db.models import (
        FindingDecision as FD,
        FindingEvidence as FE,
        ReviewRequest,
        ReviewRun,
        ThreadSyncState as TSS,
    )

    review_request = ReviewRequest(
        review_system="gitlab",
        project_ref=project_ref,
        review_request_id=review_request_id,
    )
    session.add(review_request)
    session.flush()

    review_run = ReviewRun(
        review_request_pk=review_request.id,
        review_system="gitlab",
        project_ref=project_ref,
        review_request_id=review_request_id,
        trigger="test",
        mode="manual",
        status="success",
    )
    session.add(review_run)
    session.flush()

    evidence = FE(
        review_run_id=review_run.id,
        review_request_pk=review_request.id,
        file_path="src/a.cpp",
        patch_digest=f"digest-{review_request_id}",
        change_snippet="",
    )
    session.add(evidence)
    session.flush()

    for fingerprint in all_fingerprints:
        if fingerprint in resolved_fingerprints:
            session.add(
                TSS(
                    review_request_pk=review_request.id,
                    review_system="gitlab",
                    project_ref=project_ref,
                    review_request_id=review_request_id,
                    finding_fingerprint=fingerprint,
                    anchor_signature=f"sig-{fingerprint}",
                    adapter_thread_ref=f"thread-{fingerprint}",
                    sync_status="resolved",
                    resolution_reason="remote_resolved_manual_only",
                )
            )
        session.add(
            FD(
                review_run_id=review_run.id,
                evidence_id=evidence.id,
                review_request_pk=review_request.id,
                review_system="gitlab",
                project_ref=project_ref,
                review_request_id=review_request_id,
                fingerprint=fingerprint,
                dedupe_key=f"dk-{fingerprint}",
                file_path="src/a.cpp",
                rule_no="TEST.RULE.001",
                source_family="cpp_core",
                score_raw=0.9,
                score_final=0.9,
                anchor_signature=f"sig-{fingerprint}",
                state="resolved" if fingerprint in resolved_fingerprints else "published",
            )
        )


def test_load_rule_effectiveness_weights_uses_project_local_override() -> None:
    _reset_db()

    runner = ReviewRunner()
    session = SessionLocal()
    try:
        _seed_rule_effectiveness_project(
            session,
            project_ref="group/project-a",
            review_request_id="501",
            resolved_fingerprints={f"project-a-fp-{idx}" for idx in range(5)},
            all_fingerprints=[f"project-a-fp-{idx}" for idx in range(5)],
        )
        _seed_rule_effectiveness_project(
            session,
            project_ref="group/project-b",
            review_request_id="502",
            resolved_fingerprints=set(),
            all_fingerprints=[f"project-b-fp-{idx}" for idx in range(5)],
        )
        session.commit()

        global_weights = runner._load_rule_effectiveness_weights(session)  # noqa: SLF001
        project_a_weights = runner._load_rule_effectiveness_weights(  # noqa: SLF001
            session,
            project_ref="group/project-a",
        )
        project_b_weights = runner._load_rule_effectiveness_weights(  # noqa: SLF001
            session,
            project_ref="group/project-b",
        )

        assert global_weights["TEST.RULE.001"] == 1.2
        assert project_a_weights["TEST.RULE.001"] == 1.2
        assert project_b_weights["TEST.RULE.001"] == 0.8
    finally:
        session.close()


def test_load_rule_effectiveness_weights_falls_back_to_global_when_project_sample_is_small() -> None:
    _reset_db()

    runner = ReviewRunner()
    session = SessionLocal()
    try:
        _seed_rule_effectiveness_project(
            session,
            project_ref="group/project-a",
            review_request_id="503",
            resolved_fingerprints=set(),
            all_fingerprints=[f"project-a-fp-{idx}" for idx in range(5)],
        )
        _seed_rule_effectiveness_project(
            session,
            project_ref="group/project-b",
            review_request_id="504",
            resolved_fingerprints={f"project-b-fp-{idx}" for idx in range(4)},
            all_fingerprints=[f"project-b-fp-{idx}" for idx in range(4)],
        )
        session.commit()

        global_weights = runner._load_rule_effectiveness_weights(session)  # noqa: SLF001
        project_b_weights = runner._load_rule_effectiveness_weights(  # noqa: SLF001
            session,
            project_ref="group/project-b",
        )

        assert global_weights["TEST.RULE.001"] == pytest.approx(0.8 + (4 / 9) * 0.4)
        assert project_b_weights["TEST.RULE.001"] == pytest.approx(
            global_weights["TEST.RULE.001"]
        )
    finally:
        session.close()


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
