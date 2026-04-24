from __future__ import annotations

from review_bot.providers.base import (
    FindingDraft,
    ProviderDraftResult,
    ProviderRuntimeMetadata,
    ReviewCommentProvider,
    VerifyDraftResult,
)


class FallbackReviewCommentProvider(ReviewCommentProvider):
    def __init__(
        self,
        primary: ReviewCommentProvider,
        fallback: ReviewCommentProvider,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.primary_build_available = True
        self.primary_build_failure_reason: str | None = None

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
        return self.build_draft_with_runtime(
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
        ).draft

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
        configured_provider = self._provider_name(self.primary)
        if self.primary_build_available:
            try:
                return self.primary.build_draft_with_runtime(**kwargs)
            except Exception as exc:
                self.primary_build_available = False
                self.primary_build_failure_reason = f"build_draft_error:{type(exc).__name__}"

        fallback_result = self.fallback.build_draft_with_runtime(**kwargs)
        return ProviderDraftResult(
            draft=fallback_result.draft,
            runtime=self._fallback_runtime(
                configured_provider=configured_provider,
                fallback_runtime=fallback_result.runtime,
            ),
        )

    def provider_runtime_metadata(
        self,
        *,
        configured_provider: str | None = None,
        effective_provider: str | None = None,
        fallback_used: bool = False,
        fallback_reason: str | None = None,
    ) -> ProviderRuntimeMetadata:
        primary_runtime = self.primary.provider_runtime_metadata()
        primary_unavailable = not self.primary_build_available
        use_fallback = fallback_used or primary_unavailable
        return ProviderRuntimeMetadata(
            configured_provider=configured_provider or primary_runtime.configured_provider,
            effective_provider=(
                effective_provider
                or (
                    self._provider_name(self.fallback)
                    if use_fallback
                    else primary_runtime.effective_provider
                )
            ),
            fallback_used=use_fallback,
            fallback_reason=(
                fallback_reason
                if fallback_reason is not None
                else (self.primary_build_failure_reason if use_fallback else None)
            ),
            configured_model=primary_runtime.configured_model,
            endpoint_base_url=primary_runtime.endpoint_base_url,
            transport_class=primary_runtime.transport_class,
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
        kwargs = dict(
            draft=draft,
            file_path=file_path,
            rule_no=rule_no,
            title=title,
            summary=summary,
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
        try:
            return self.primary.verify_draft(**kwargs)
        except Exception:
            # Verify failures should fall back for this call only. They must not
            # disable the primary draft builder for subsequent publications.
            pass
        return self.fallback.verify_draft(**kwargs)

    @staticmethod
    def _provider_name(provider: ReviewCommentProvider) -> str:
        name = str(getattr(provider, "provider_name", "unknown") or "").strip()
        return name or "unknown"

    def _fallback_runtime(
        self,
        *,
        configured_provider: str,
        fallback_runtime: ProviderRuntimeMetadata,
    ) -> ProviderRuntimeMetadata:
        primary_runtime = self.primary.provider_runtime_metadata()
        return ProviderRuntimeMetadata(
            configured_provider=configured_provider,
            effective_provider=fallback_runtime.effective_provider,
            fallback_used=True,
            fallback_reason=self.primary_build_failure_reason or "primary_build_disabled",
            configured_model=primary_runtime.configured_model,
            endpoint_base_url=primary_runtime.endpoint_base_url,
            transport_class=primary_runtime.transport_class or fallback_runtime.transport_class,
        )
