from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FindingDraft:
    title: str
    summary: str
    suggested_fix: str | None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    confidence: float = 0.7
    should_publish: bool = True
    line_no: int | None = None
    # 증거 기반 코멘트: 실제 코드 인용 문자열 (file:line 포함)
    evidence_snippet: str | None = None
    # Auto-fix: 신뢰도 > 0.9일 때 GitLab suggestion 블록용 수정 코드
    auto_fix_lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerifyDraftResult:
    applies: bool = True
    reason: str = ""
    confidence: float | None = None


@dataclass(frozen=True)
class ProviderRuntimeMetadata:
    configured_provider: str
    effective_provider: str
    fallback_used: bool = False
    fallback_reason: str | None = None


@dataclass(frozen=True)
class ProviderDraftResult:
    draft: FindingDraft
    runtime: ProviderRuntimeMetadata


class ReviewCommentProvider:
    provider_name = "unknown"

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
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
        prompt_overlay_refs: list[str] | tuple[str, ...] | None = None,
        pr_title: str | None = None,
        pr_source_branch: str | None = None,
        pr_target_branch: str | None = None,
        similar_code: list[dict] | None = None,
    ) -> FindingDraft:
        raise NotImplementedError

    def build_draft_with_runtime(
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
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
        prompt_overlay_refs: list[str] | tuple[str, ...] | None = None,
        pr_title: str | None = None,
        pr_source_branch: str | None = None,
        pr_target_branch: str | None = None,
        similar_code: list[dict] | None = None,
    ) -> ProviderDraftResult:
        draft = self.build_draft(
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
            language_id=language_id,
            profile_id=profile_id,
            context_id=context_id,
            dialect_id=dialect_id,
            prompt_overlay_refs=prompt_overlay_refs,
            pr_title=pr_title,
            pr_source_branch=pr_source_branch,
            pr_target_branch=pr_target_branch,
            similar_code=similar_code,
        )
        return ProviderDraftResult(
            draft=draft,
            runtime=ProviderRuntimeMetadata(
                configured_provider=self.provider_name,
                effective_provider=self.provider_name,
            ),
        )

    def verify_draft(
        self,
        *,
        draft: FindingDraft,
        file_path: str,
        rule_no: str,
        title: str,
        summary: str,
        category: str | None = None,
        change_snippet: str | None = None,
        line_no: int | None = None,
        candidate_line_nos: tuple[int, ...] = (),
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
        prompt_overlay_refs: list[str] | tuple[str, ...] | None = None,
        pr_title: str | None = None,
        pr_source_branch: str | None = None,
        pr_target_branch: str | None = None,
        similar_code: list[dict] | None = None,
    ) -> VerifyDraftResult:
        del (
            draft,
            file_path,
            rule_no,
            title,
            summary,
            category,
            change_snippet,
            line_no,
            candidate_line_nos,
            file_context,
            language_id,
            profile_id,
            context_id,
            dialect_id,
            prompt_overlay_refs,
            pr_title,
            pr_source_branch,
            pr_target_branch,
            similar_code,
        )
        return VerifyDraftResult()
