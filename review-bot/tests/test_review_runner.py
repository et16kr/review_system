from __future__ import annotations

from fastapi import HTTPException

from app.bot.review_runner import ReviewRunner
from app.db.models import FindingPublication, ReviewFinding
from app.db.session import Base, SessionLocal, engine
from app.providers.base import FindingDraft, ReviewCommentProvider
from app.providers.change_analysis import select_candidate_line
from app.providers.fallback_provider import FallbackReviewCommentProvider
from app.providers.stub_provider import StubReviewCommentProvider


class FakePlatformClient:
    def __init__(self, fail_on_comment_number: int | None = None) -> None:
        self.comments: list[dict[str, object]] = []
        self.statuses: list[dict[str, object]] = []
        self.fail_on_comment_number = fail_on_comment_number

    def get_pull_request_diff(self, pr_id: int) -> dict[str, object]:
        return {
            "pull_request": {"id": pr_id, "head_sha": "abc123"},
            "files": [
                {
                    "path": "src/a.cpp",
                    "patch": "@@ -1,2 +1,4 @@\n+ char* p = (char*)malloc(10);\n+ free(p);\n",
                },
                {
                    "path": "src/b.cpp",
                    "patch": "@@ -1,2 +1,4 @@\n+ switch (x) {}\n+ continue;\n",
                },
            ],
        }

    def post_comment(
        self,
        pr_id: int,
        *,
        body: str,
        file_path: str | None,
        line_no: int | None,
        comment_type: str = "inline",
        author_type: str = "bot",
    ) -> dict[str, object]:
        comment_id = len(self.comments) + 1
        if self.fail_on_comment_number == comment_id:
            raise HTTPException(status_code=503, detail="comment publish failure")
        self.comments.append(
            {
                "id": comment_id,
                "pr_id": pr_id,
                "body": body,
                "file_path": file_path,
                "line_no": line_no,
                "comment_type": comment_type,
                "author_type": author_type,
            }
        )
        return {"id": comment_id}

    def post_status(self, pr_id: int, *, state: str, description: str) -> dict[str, object]:
        self.statuses.append({"pr_id": pr_id, "state": state, "description": description})
        return {"ok": True}


class FakeEngineClient:
    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del top_k
        if "malloc" in diff:
            return {
                "results": [
                    _result("ALTI-MEM-007", 0.97),
                    _result("ALTI-MEM-006", 0.95),
                    _result("R.10", 0.88),
                ]
            }
        return {
            "results": [
                _result("ALTI-COF-002", 0.96),
                _result("ALTI-COF-001", 0.94),
                _result("ALTI-PCM-002", 0.89),
            ]
        }


class MultiHunkPlatformClient(FakePlatformClient):
    def get_pull_request_diff(self, pr_id: int) -> dict[str, object]:
        return {
            "pull_request": {"id": pr_id, "head_sha": "abc123"},
            "files": [
                {
                    "path": "src/a.cpp",
                    "patch": (
                        "@@ -1,2 +1,4 @@\n"
                        "+ char* p = (char*)malloc(10);\n"
                        "+ free(p);\n"
                        "@@ -20,2 +22,4 @@\n"
                        "+ char* q = (char*)malloc(20);\n"
                        "+ free(q);\n"
                    ),
                }
            ],
        }


class ContinueOnlyPlatformClient(FakePlatformClient):
    def get_pull_request_diff(self, pr_id: int) -> dict[str, object]:
        return {
            "pull_request": {"id": pr_id, "head_sha": "abc123"},
            "files": [
                {
                    "path": "src/flow.cpp",
                    "patch": "@@ -10,2 +10,3 @@\n+ if (skip) {\n+     continue;\n+ }\n",
                }
            ],
        }


class ContinueOnlyEngineClient:
    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del diff, top_k
        return {"results": [_result("ALTI-COF-001", 0.96)]}


class LowScoreEngineClient:
    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del diff, top_k
        return {"results": [_result("ALTI-MEM-007", 0.42)]}


class HeaderOnlyPlatformClient(FakePlatformClient):
    def get_pull_request_diff(self, pr_id: int) -> dict[str, object]:
        return {
            "pull_request": {"id": pr_id, "head_sha": "abc123"},
            "files": [
                {
                    "path": "src/id/include/idsTde.h",
                    "patch": (
                        "@@ -0,0 +1,4 @@\n"
                        "+class idsTde\n"
                        "+{\n"
                        "+public:\n"
                        "+    static void createKeyStore();\n"
                    ),
                }
            ],
        }


class AssertMismatchedEngineClient:
    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del diff, top_k
        return {
            "results": [
                {
                    **_result("ALTI-PCM-002", 0.96),
                    "title": "IDE_ASSERT usage should be avoided",
                    "summary": "IDE_ASSERT detected in error path",
                }
            ]
        }


class GenericErrorHandlingEngineClient:
    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del diff, top_k
        return {
            "results": [
                {
                    **_result("ALTI-ERR-003", 0.82),
                    "title": "IDE_FT macro usage",
                    "summary": (
                        "IDE_FT macro usage The PDF has a separate section "
                        "for Altibase error handling"
                    ),
                    "category": "error_handling",
                }
            ]
        }


class ReturnOnlyPlatformClient(FakePlatformClient):
    def get_pull_request_diff(self, pr_id: int) -> dict[str, object]:
        return {
            "pull_request": {"id": pr_id, "head_sha": "abc123"},
            "files": [
                {
                    "path": "src/error.cpp",
                    "patch": (
                        "@@ -10,0 +10,3 @@\n"
                        "+ if (failed == ID_TRUE) {\n"
                        "+     return IDE_FAILURE;\n"
                        "+ }\n"
                    ),
                }
            ],
        }


class ErrorHandlingEngineClient:
    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del diff, top_k
        return {
            "results": [
                {
                    **_result("ALTI-ERR-001", 0.88),
                    "title": "IDE_RC return flow",
                    "summary": "IDE_RC return flow should be more explicit",
                    "category": "error_handling",
                    "reviewability": "auto_review",
                }
            ]
        }


class WrapperCallPlatformClient(FakePlatformClient):
    def get_pull_request_diff(self, pr_id: int) -> dict[str, object]:
        return {
            "pull_request": {"id": pr_id, "head_sha": "abc123"},
            "files": [
                {
                    "path": "src/wrapper.cpp",
                    "patch": (
                        "@@ -20,0 +20,4 @@\n"
                        "+ if (need_name == ID_TRUE) {\n"
                        "+     idlOS::snprintf(buffer, buffer_size, \"%s\", value);\n"
                        "+ }\n"
                    ),
                }
            ],
        }


class WrapperUsageEngineClient:
    def review_diff(self, diff: str, top_k: int = 8) -> dict[str, object]:
        del diff, top_k
        return {
            "results": [
                {
                    **_result("ALTI-PCM-002", 0.9),
                    "title": "Do not call system library functions directly",
                    "summary": "Direct system library call detected",
                    "category": "wrapper_usage",
                    "reviewability": "auto_review",
                }
            ]
        }


class RejectingInlinePlatformClient(FakePlatformClient):
    def post_comment(
        self,
        pr_id: int,
        *,
        body: str,
        file_path: str | None,
        line_no: int | None,
        comment_type: str = "inline",
        author_type: str = "bot",
    ) -> dict[str, object]:
        del pr_id, body, comment_type, author_type
        if file_path and line_no is not None:
            raise RuntimeError(f"Unable to create inline discussion for {file_path}:{line_no}")
        return {"id": 1}


class InvalidLineProvider(ReviewCommentProvider):
    def build_draft(self, **kwargs) -> FindingDraft:
        del kwargs
        return FindingDraft(
            title="루프 흐름을 단순하게 정리해 주세요",
            summary="continue가 실제로 사용된 줄에 코멘트가 붙어야 합니다.",
            suggested_fix=None,
            line_no=999,
        )


def test_review_runner_suppresses_semantically_duplicate_findings() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = FakePlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = FakeEngineClient()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=101, trigger="test")
        assert review_run.status == "success"

        finding_count = session.query(ReviewFinding).filter(ReviewFinding.pr_id == 101).count()
        publication_count = (
            session.query(FindingPublication).filter(FindingPublication.pr_id == 101).count()
        )
        assert finding_count == 2
        assert publication_count == 2
        assert len(fake_platform.comments) == 2
        assert "규칙:" not in fake_platform.comments[0]["body"]
        assert "ALTI-" not in fake_platform.comments[0]["body"]
        assert "권장 수정" in fake_platform.comments[0]["body"]

        state = runner.build_state(session, 101)
        assert state["last_status"] == "success"
        assert state["published_batch_count"] == 1
        assert state["open_finding_count"] == 2
        assert state["resolved_finding_count"] == 0
    finally:
        session.close()


def test_review_runner_keeps_distinct_findings_per_hunk() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.platform_client = MultiHunkPlatformClient()
    runner.engine_client = FakeEngineClient()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=202, trigger="test-hunks")
        findings = (
            session.query(ReviewFinding)
            .filter(ReviewFinding.pr_id == 202, ReviewFinding.rule_no == "ALTI-MEM-007")
            .order_by(ReviewFinding.line_no.asc())
            .all()
        )
        assert len(findings) == 2
        assert findings[0].fingerprint != findings[1].fingerprint
        assert findings[0].line_no != findings[1].line_no
    finally:
        session.close()


def test_review_runner_persists_already_published_findings_on_partial_failure() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = FakePlatformClient(fail_on_comment_number=2)
    runner.platform_client = fake_platform
    runner.engine_client = FakeEngineClient()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=303, trigger="test-partial-failure")

        publications = (
            session.query(FindingPublication)
            .filter(FindingPublication.pr_id == 303)
            .order_by(FindingPublication.id.asc())
            .all()
        )
        published_findings = (
            session.query(ReviewFinding)
            .filter(ReviewFinding.pr_id == 303, ReviewFinding.status == "published")
            .all()
        )
        failed_publications = (
            session.query(ReviewFinding)
            .filter(ReviewFinding.pr_id == 303, ReviewFinding.status == "failed_publication")
            .all()
        )

        assert review_run.status == "partial"
        assert len(publications) == 1
        assert len(published_findings) == 1
        assert len(failed_publications) >= 1
    finally:
        session.close()


def test_review_runner_targets_exact_changed_line_for_continue() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = ContinueOnlyPlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = ContinueOnlyEngineClient()
    runner.provider = StubReviewCommentProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=505, trigger="test-exact-line")
        assert len(fake_platform.comments) == 1
        assert fake_platform.comments[0]["line_no"] == 11
        assert "continue" in str(fake_platform.comments[0]["body"])
    finally:
        session.close()


def test_review_runner_falls_back_to_valid_changed_line_when_provider_returns_invalid_line(
) -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = ContinueOnlyPlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = ContinueOnlyEngineClient()
    runner.provider = InvalidLineProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=606, trigger="test-invalid-line")
        assert len(fake_platform.comments) == 1
        assert fake_platform.comments[0]["line_no"] == 11
    finally:
        session.close()


def test_review_runner_skips_low_score_candidates() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = ContinueOnlyPlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = LowScoreEngineClient()
    runner.provider = StubReviewCommentProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=616, trigger="test-low-score")
        assert fake_platform.comments == []
        assert session.query(ReviewFinding).filter(ReviewFinding.pr_id == 616).count() == 0
    finally:
        session.close()


def test_review_runner_skips_findings_without_a_matching_changed_line_signal() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = HeaderOnlyPlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = AssertMismatchedEngineClient()
    runner.provider = StubReviewCommentProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=707, trigger="test-weak-anchor")
        assert fake_platform.comments == []
        assert session.query(ReviewFinding).filter(ReviewFinding.pr_id == 707).count() == 0
    finally:
        session.close()


def test_review_runner_skips_generic_error_handling_candidates() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = HeaderOnlyPlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = GenericErrorHandlingEngineClient()
    runner.provider = StubReviewCommentProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=717, trigger="test-generic-error-handling")
        assert fake_platform.comments == []
        assert session.query(ReviewFinding).filter(ReviewFinding.pr_id == 717).count() == 0
    finally:
        session.close()


def test_review_runner_skips_return_only_error_handling_comments() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = ReturnOnlyPlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = ErrorHandlingEngineClient()
    runner.provider = StubReviewCommentProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=718, trigger="test-return-only-error")
        assert fake_platform.comments == []
        assert session.query(ReviewFinding).filter(ReviewFinding.pr_id == 718).count() == 0
    finally:
        session.close()


def test_review_runner_skips_wrapper_calls_that_are_already_namespaced() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = WrapperCallPlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = WrapperUsageEngineClient()
    runner.provider = StubReviewCommentProvider()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=719, trigger="test-wrapper-call")
        assert fake_platform.comments == []
        assert session.query(ReviewFinding).filter(ReviewFinding.pr_id == 719).count() == 0
    finally:
        session.close()


def test_review_runner_does_not_fallback_to_general_note_when_inline_anchor_fails() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = RejectingInlinePlatformClient()
    runner.platform_client = fake_platform
    runner.engine_client = ContinueOnlyEngineClient()
    runner.provider = StubReviewCommentProvider()

    session = SessionLocal()
    try:
        review_run = runner.run_review(session, pr_id=727, trigger="test-inline-only")
        findings = (
            session.query(ReviewFinding)
            .filter(ReviewFinding.pr_id == 727)
            .all()
        )
        assert review_run.status == "partial"
        assert fake_platform.comments == []
        assert findings
        assert all(finding.status == "failed_publication" for finding in findings)
        assert all(
            "inline discussion" in (finding.publication_error or "") for finding in findings
        )
    finally:
        session.close()


def test_fallback_provider_uses_stub_when_primary_raises() -> None:
    class ExplodingProvider(ReviewCommentProvider):
        def __init__(self) -> None:
            self.calls = 0

        def build_draft(self, **kwargs):
            del kwargs
            self.calls += 1
            raise RuntimeError("provider failure")

    exploding = ExplodingProvider()
    provider = FallbackReviewCommentProvider(
        primary=exploding,
        fallback=StubReviewCommentProvider(),
    )
    draft = provider.build_draft(
        file_path="src/a.cpp",
        rule_no="ALTI-MEM-007",
        title="메모리 해제 규칙",
        summary="raw memory usage detected",
        change_snippet="@@ -1 +1 @@\n+ char* p = (char*)malloc(10);\n+ free(p);\n",
    )
    assert "malloc/free" in draft.summary
    assert "```cpp" in (draft.suggested_fix or "")
    assert draft.should_publish is True

    second = provider.build_draft(
        file_path="src/b.cpp",
        rule_no="ALTI-COF-001",
        title="continue usage",
        summary="continue detected",
        change_snippet="@@ -1 +1 @@\n+ continue;\n",
    )
    assert "continue" in second.summary
    assert exploding.calls == 1


def test_stub_provider_filters_out_raw_english_fix_guidance() -> None:
    provider = StubReviewCommentProvider()

    draft = provider.build_draft(
        file_path="src/error.cpp",
        rule_no="Rule-R1",
        title="Rule-R1 title",
        summary="exception cleanup flow",
        category="error_handling",
        fix_guidance="Follow the internal Rule-R guidance for RC flow and cleanup sequencing.",
        change_snippet="@@ -1 +1 @@\n+ IDE_EXCEPTION_ERR(rc != IDE_SUCCESS, cleanup);\n",
    )

    assert "Rule-R" not in (draft.suggested_fix or "")
    assert "guidance" not in (draft.suggested_fix or "").lower()


def test_select_candidate_line_prefers_error_flow_signal_over_function_signature() -> None:
    change_snippet = "\n".join(
        [
            "@@ -50,0 +50,8 @@",
            "L61 | + static IDE_RC qdcRaiseTdeError( idsTdeResult  aResult,",
            "L62 | +                                 const SChar * aKeyStorePath,",
            "L63 | +                                 const SChar * aWrapKeyPath )",
            "L64 | + {",
            "L65 | +     IDE_SET( ideSetErrorCode( smERR_ABORT_TDEKeyStoreNotFound,",
            "L66 | +                               aKeyStorePath ) );",
            "L67 | +     return IDE_FAILURE;",
            "L68 | + }",
        ]
    )

    selected = select_candidate_line(
        change_snippet=change_snippet,
        candidate_line_nos=(61, 62, 63, 64, 65, 66, 67, 68),
        issue="ide_rc_flow",
    )

    assert selected == 67


def test_review_runner_splits_large_added_hunks_into_multiple_review_units() -> None:
    runner = ReviewRunner()
    added_lines = "\n".join(f"+ line_{index}" for index in range(1, 201))
    patch = f"@@ -0,0 +1,200 @@\n{added_lines}"

    units = runner._iter_review_units(patch)

    assert len(units) == 3
    assert units[0].candidate_line_nos[0] == 1
    assert units[0].candidate_line_nos[-1] == 80
    assert units[1].candidate_line_nos[0] == 81
    assert units[2].candidate_line_nos[-1] == 200


def test_build_state_uses_latest_review_run() -> None:
    _reset_db()

    runner = ReviewRunner()
    runner.platform_client = FakePlatformClient()
    runner.engine_client = FakeEngineClient()

    session = SessionLocal()
    try:
        runner.run_review(session, pr_id=404, trigger="first")
        runner.run_review(session, pr_id=404, trigger="second")

        state = runner.build_state(session, 404)

        assert state["pr_id"] == 404
        assert state["last_review_run_id"] is not None
        assert state["last_status"] == "success"
        assert state["last_head_sha"] == "abc123"
    finally:
        session.close()


def test_publish_next_batch_prefers_diverse_findings_over_repeating_same_file_title() -> None:
    _reset_db()

    runner = ReviewRunner()
    fake_platform = FakePlatformClient()
    runner.platform_client = fake_platform

    session = SessionLocal()
    try:
        review_run = runner.create_review_run(session, pr_id=808, trigger="diversity")
        findings = [
            ReviewFinding(
                review_run_id=review_run.id,
                pr_id=808,
                fingerprint=f"f-{index}",
                file_path=file_path,
                line_no=line_no,
                rule_no="ALTI-MEM-007",
                source_family="altibase",
                score=score,
                severity="high",
                confidence=0.8,
                title=title,
                summary=f"{title} summary",
                suggested_fix=None,
                status="open",
            )
            for index, (file_path, line_no, title, score) in enumerate(
                [
                    (
                        "src/id/ids/idsTde.cpp",
                        76,
                        "메모리를 직접 할당하고 해제하고 있습니다",
                        0.95,
                    ),
                    (
                        "src/id/ids/idsTde.cpp",
                        82,
                        "메모리를 직접 할당하고 해제하고 있습니다",
                        0.94,
                    ),
                    (
                        "src/id/ids/idsTde.cpp",
                        177,
                        "메모리를 직접 할당하고 해제하고 있습니다",
                        0.93,
                    ),
                    (
                        "src/sm/smm/smmFT.cpp",
                        1514,
                        "메모리를 직접 할당하고 해제하고 있습니다",
                        0.92,
                    ),
                    (
                        "src/sm/smm/smmManager.cpp",
                        5018,
                        "루프 흐름이 `continue`에 의존하고 있습니다",
                        0.91,
                    ),
                    (
                        "src/id/ids/idsTde.cpp",
                        1838,
                        "`switch`에 예외 입력을 처리하는 분기가 없습니다",
                        0.9,
                    ),
                ],
                start=1,
            )
        ]
        session.add_all(findings)
        session.commit()

        published, failed = runner.publish_next_batch(session, 808, review_run.id)

        assert failed == 0
        assert published == 4
        assert len(fake_platform.comments) == 4

        posted_pairs = {
            (comment["file_path"], comment["body"].splitlines()[0])
            for comment in fake_platform.comments
        }
        assert len(posted_pairs) == 4
    finally:
        session.close()


def _result(rule_no: str, score: float) -> dict[str, object]:
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
    }


def _reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
