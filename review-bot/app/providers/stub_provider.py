from __future__ import annotations

from app.providers.base import FindingDraft, ReviewCommentProvider


class StubReviewCommentProvider(ReviewCommentProvider):
    def build_draft(
        self,
        *,
        file_path: str,
        rule_no: str,
        title: str,
        summary: str,
        rule_text: str | None = None,
        fix_guidance: str | None = None,
        category: str | None = None,
        line_no: int | None = None,
    ) -> FindingDraft:
        del rule_text, category
        comment_summary = (
            f"`{file_path}`에서 감지된 변경이 `{rule_no}` 규칙과 충돌할 가능성이 "
            f"있습니다. {summary}"
        )
        return FindingDraft(
            title=title,
            summary=comment_summary,
            suggested_fix=fix_guidance
            or (
                "관련 규칙 설명을 확인하고 해당 패턴을 제거하거나 "
                "내부 래퍼/컨벤션에 맞게 수정하세요."
            ),
            severity="medium",
            confidence=0.72,
            should_publish=True,
            line_no=line_no,
        )
