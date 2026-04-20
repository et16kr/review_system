from __future__ import annotations

from dataclasses import dataclass, replace as dataclass_replace
from datetime import UTC, datetime, timedelta

from review_bot.bot.review_runner import ReviewRunner
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
from review_bot.db.models import DeadLetterRecord, FeedbackEvent, FindingDecision, PublicationState, ThreadSyncState
from review_bot.db.session import Base, SessionLocal, engine
from review_bot.errors import ReviewBotError
from review_bot.policy import PathPolicy, ReviewPolicy
from review_bot.providers.base import FindingDraft, ReviewCommentProvider


def test_review_runner_publishes_inline_comment_and_persists_thread_state() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(101)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=202, trigger="test-hunks")
        findings = (
            session.query(FindingDecision)
            .filter_by(review_request_id="202", rule_no="ALTI-MEM-007")
            .order_by(FindingDecision.line_no.asc())
            .all()
        )

        assert len(findings) == 2
        assert findings[0].fingerprint != findings[1].fingerprint
        assert findings[0].line_no != findings[1].line_no
    finally:
        session.close()


def test_review_runner_resurfaces_unfixed_open_finding_on_full_rerun() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(404)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert [item.publish_state for item in publications] == ["created", "updated"]
        assert len(threads) == 1
        assert len(threads[0].notes) == 2
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
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory", score=0.8)])
    provider = ScenarioProvider(
        {
            ("src/a.cpp", "ALTI-MEM-007"): FindingDraft(
                title="메모리를 직접 할당하고 해제하고 있습니다",
                summary="첫 번째 게시입니다.",
                suggested_fix="RAII 또는 프로젝트 표준 wrapper로 옮겨 주세요.",
            ),
            ("src/b.cpp", "ALTI-COF-001"): FindingDraft(
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
        provider.mapping[("src/a.cpp", "ALTI-MEM-007")] = FindingDraft(
            title="메모리를 직접 할당하고 해제하고 있습니다",
            summary="기존 thread를 먼저 갱신해야 합니다.",
            suggested_fix="RAII 또는 프로젝트 표준 wrapper로 옮겨 주세요.",
        )
        runner.engine_client = SequentialEngineStub(
            [
                [_result("ALTI-MEM-007", category="memory", score=0.75)],
                [_result("ALTI-COF-001", category="control_flow", score=0.99)],
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
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory", score=0.8)])
    provider = ScenarioProvider(
        {
            ("src/a.cpp", "ALTI-MEM-007"): FindingDraft(
                title="메모리를 직접 할당하고 해제하고 있습니다",
                summary="변화가 없는 기존 thread입니다.",
                suggested_fix="RAII 또는 프로젝트 표준 wrapper로 옮겨 주세요.",
            ),
            ("src/b.cpp", "ALTI-COF-001"): FindingDraft(
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
                [_result("ALTI-MEM-007", category="memory", score=0.8)],
                [_result("ALTI-COF-001", category="control_flow", score=0.99)],
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
        assert [item.publish_state for item in publications] == ["created", "skipped", "created"]
        assert len(adapter.list_threads(key)) == 2
    finally:
        session.close()


def test_review_runner_resolves_stale_thread_when_finding_is_no_longer_auto_publishable() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(606)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    engine = EngineStub([_result("ALTI-MEM-007", category="memory")])
    runner.platform_client = adapter
    runner.engine_client = engine
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=606, trigger="first")
        engine.results = [_result("ALTI-MEM-007", category="memory", reviewability="manual_only")]
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
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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


def test_review_runner_recovers_stale_thread_after_resolve_failure_when_remote_thread_is_still_open() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(708)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=708, trigger="first")

        adapter.fail_resolve_refs.add("thread-1")
        runner.engine_client = EngineStub(
            [_result("ALTI-MEM-007", category="memory", reviewability="manual_only")]
        )
        runner.run_review(session, pr_id=708, trigger="resolve-fails")

        stale_state = session.query(ThreadSyncState).filter_by(review_request_id="708").one()
        assert stale_state.sync_status == "stale"
        assert stale_state.resolution_reason == "resolve_failed"

        adapter.fail_resolve_refs.clear()
        runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
        runner.run_review(session, pr_id=708, trigger="recovered")

        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="708").one()

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert thread_state.sync_status == "open"
        assert thread_state.resolution_reason is None
        assert len(adapter.list_threads(key)) == 1
        assert len(adapter.list_threads(key)[0].notes) == 2
    finally:
        session.close()


def test_review_runner_persists_manual_reopen_without_posting_redundant_bot_reply() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(709)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=709, trigger="first")

        adapter.mark_resolved(key, "thread-1", resolved=True)
        runner.engine_client = EngineStub(
            [_result("ALTI-MEM-007", category="memory", reviewability="manual_only")]
        )
        runner.run_review(session, pr_id=709, trigger="resolved")

        adapter.mark_resolved(key, "thread-1", resolved=False)
        runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
        runner.run_review(session, pr_id=709, trigger="manual-reopen")

        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="709").one()

        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert thread_state.sync_status == "open"
        assert adapter.list_threads(key)[0].resolved is False
        assert len(adapter.list_threads(key)[0].notes) == 2
    finally:
        session.close()


def test_review_runner_records_repeated_resolve_and_unresolve_feedback_transitions() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(710)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=710, trigger="first")

        adapter.mark_resolved(key, "thread-1", resolved=True)
        runner.engine_client = EngineStub(
            [_result("ALTI-MEM-007", category="memory", reviewability="manual_only")]
        )
        runner.run_review(session, pr_id=710, trigger="resolved")

        adapter.mark_resolved(key, "thread-1", resolved=False)
        runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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


def test_review_runner_reopens_resolved_thread_on_full_reconcile() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter()
    key = runner._legacy_key(717)  # noqa: SLF001
    adapter.set_diff(key, path="src/a.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
    runner.provider = FixedProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=717, trigger="first")
        adapter.mark_resolved(key, "thread-1", resolved=True)

        review_run = runner.run_review(session, pr_id=717, trigger="full-reconcile")
        thread_state = session.query(ThreadSyncState).filter_by(review_request_id="717").one()

        assert review_run.status == "success"
        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
        assert adapter.upsert_requests[1].reopen_if_resolved is True
        assert thread_state.sync_status == "open"
        assert len(adapter.list_threads(key)) == 1
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
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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
        assert len(adapter.upsert_requests) == 2
        assert adapter.upsert_requests[1].existing_thread_ref == "thread-1"
    finally:
        session.close()


def test_review_runner_records_dead_letter_for_failed_publication() -> None:
    _reset_db()

    runner = ReviewRunner()
    adapter = FakeAdapter(fail_inline=True)
    key = runner._legacy_key(726)  # noqa: SLF001
    adapter.set_diff(key, path="src/flow.cpp", patch=_continue_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ALTI-COF-001", category="control_flow")])
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
    runner.engine_client = EngineStub([_result("ALTI-COF-001", category="control_flow")])
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
    runner.engine_client = EngineStub([_result("ALTI-COF-001", category="control_flow")])
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
                suppress_rules=frozenset({"ALTI-MEM-007"}),
            ),
        )
    )
    adapter = FakeAdapter()
    key = runner._legacy_key(777)  # noqa: SLF001
    adapter.set_diff(key, path="src/id/ids/idsTde.cpp", patch=_malloc_patch())
    runner.platform_client = adapter
    runner.engine_client = EngineStub([_result("ALTI-MEM-007", category="memory")])
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
        [_result("ALTI-MEM-007", category="memory", reviewability="manual_only")]
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
            _result("ALTI-COF-001", category="control_flow"),
            _result("ALTI-COF-009", category="control_flow"),
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


@dataclass
class EngineStub:
    results: list[dict[str, object]]
    detected_patterns: list[str] | None = None

    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del diff, top_k
        return {
            "detected_patterns": list(self.detected_patterns or []),
            "results": [dict(result) for result in self.results],
        }


@dataclass
class SequentialEngineStub:
    responses: list[list[dict[str, object]]]
    detected_patterns: list[str] | None = None

    def __post_init__(self) -> None:
        self._index = 0

    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del diff, top_k
        response_index = min(self._index, len(self.responses) - 1)
        self._index += 1
        return {
            "detected_patterns": list(self.detected_patterns or []),
            "results": [dict(result) for result in self.responses[response_index]],
        }


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
        self.threads_by_key: dict[tuple[str, str, str], list[ThreadSnapshot]] = {}
        self.upsert_requests = []
        self.publish_checks = []
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

    def fetch_review_request_meta(self, key: ReviewRequestKey) -> ReviewRequestMeta:
        return self.meta_by_key[_key_tuple(key)]

    def fetch_diff(
        self,
        key: ReviewRequestKey,
        *,
        mode: str,
        base_sha: str | None = None,
    ) -> DiffPayload:
        del mode, base_sha
        return self.diff_by_key[_key_tuple(key)]

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
        "source_family": "altibase" if rule_no.startswith("ALTI") else "cpp_core",
        "authority": "internal" if rule_no.startswith("ALTI") else "external",
        "conflict_policy": "authoritative" if rule_no.startswith("ALTI") else "compatible",
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


def _continue_patch() -> str:
    return (
        "@@ -10,2 +10,3 @@\n"
        "+ if (skip) {\n"
        "+     continue;\n"
        "+ }\n"
    )


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
