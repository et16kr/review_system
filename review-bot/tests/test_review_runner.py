from __future__ import annotations

from fastapi import HTTPException

from app.bot.review_runner import ReviewRunner
from app.db.models import FindingPublication, ReviewFinding
from app.db.session import Base, SessionLocal, engine
from app.providers.base import FindingDraft, ReviewCommentProvider
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
