from __future__ import annotations

from review_bot.providers.base import FindingDraft, ReviewCommentProvider


class FallbackReviewCommentProvider(ReviewCommentProvider):
    def __init__(
        self,
        primary: ReviewCommentProvider,
        fallback: ReviewCommentProvider,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_available = True

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
        change_snippet: str | None = None,
        line_no: int | None = None,
        candidate_line_nos: tuple[int, ...] = (),
        file_context: str | None = None,
        pr_title: str | None = None,
        pr_source_branch: str | None = None,
        pr_target_branch: str | None = None,
        similar_code: list[dict] | None = None,
    ) -> FindingDraft:
        kwargs = dict(
            file_path=file_path,
            rule_no=rule_no,
            title=title,
            summary=summary,
            rule_text=rule_text,
            fix_guidance=fix_guidance,
            category=category,
            change_snippet=change_snippet,
            line_no=line_no,
            candidate_line_nos=candidate_line_nos,
            file_context=file_context,
            pr_title=pr_title,
            pr_source_branch=pr_source_branch,
            pr_target_branch=pr_target_branch,
            similar_code=similar_code,
        )
        if self.primary_available:
            try:
                return self.primary.build_draft(**kwargs)
            except Exception:
                self.primary_available = False

        return self.fallback.build_draft(**kwargs)
