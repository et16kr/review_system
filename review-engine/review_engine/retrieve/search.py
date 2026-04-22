from __future__ import annotations

from review_engine.config import Settings, get_settings
from review_engine.ingest.build_records import ingest_all_sources
from review_engine.ingest.chroma_store import ChromaGuidelineStore
from review_engine.ingest.rule_loader import load_rule_runtime
from review_engine.languages import get_language_registry
from review_engine.models import CandidateHit, IngestionSummary, QueryAnalysis, ReviewResponse, ReviewResult
from review_engine.query.code_to_query import build_query_analysis
from review_engine.query.detectors import QueryDetectorManager
from review_engine.retrieve.applicability import is_candidate_applicable
from review_engine.retrieve.rerank import rerank_candidates


class GuidelineSearchService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = ChromaGuidelineStore(self.settings)
        self.language_registry = get_language_registry()

    def ingest(self, force_refresh: bool = False) -> IngestionSummary:
        return ingest_all_sources(self.settings, force_refresh=force_refresh)

    def review_code(
        self,
        code: str,
        top_k: int = 10,
        *,
        file_path: str | None = None,
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
    ) -> ReviewResponse:
        return self._review_text(
            code,
            input_kind="code",
            top_k=top_k,
            file_path=file_path,
            file_context=file_context,
            language_id=language_id,
            profile_id=profile_id,
            context_id=context_id,
            dialect_id=dialect_id,
        )

    def review_diff(
        self,
        diff: str,
        top_k: int = 10,
        *,
        file_path: str | None = None,
        file_context: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
    ) -> ReviewResponse:
        match = self.language_registry.resolve(
            file_path=file_path,
            source_text=file_context or diff,
            language_id=language_id,
            profile_id=profile_id,
            context_id=context_id,
            dialect_id=dialect_id,
            default_language_id=self.settings.default_language_id,
        )
        if not match.reviewable:
            return self._empty_review_response(match)
        runtime = load_rule_runtime(
            self.settings,
            language_id=match.language_id,
            profile_id=match.profile_id,
            context_id=match.context_id,
            dialect_id=match.dialect_id,
        )
        analysis = build_query_analysis(
            diff,
            input_kind="diff",
            settings=self.settings,
            file_path=file_path,
            file_context=file_context,
            language_id=runtime.language_id,
            profile_id=runtime.profile.profile_id,
            context_id=runtime.context_id,
            dialect_id=runtime.dialect_id,
            query_plugin_id=match.query_plugin_id,
            detector_refs=runtime.detector_refs,
        )
        analysis = self._augment_diff_analysis_with_context(analysis, file_context)
        return self._review_analysis(analysis, runtime=runtime, top_k=top_k)

    def inspect_rule(self, rule_no: str, *, language_id: str | None = None):
        self._ensure_runtime_data(language_id or self.settings.default_language_id)
        return self.store.get_rule(rule_no, language_id=language_id)

    def _review_text(
        self,
        source_text: str,
        input_kind: str,
        top_k: int,
        *,
        file_path: str | None,
        file_context: str | None,
        language_id: str | None,
        profile_id: str | None,
        context_id: str | None,
        dialect_id: str | None,
    ) -> ReviewResponse:
        match = self.language_registry.resolve(
            file_path=file_path,
            source_text=source_text,
            language_id=language_id,
            profile_id=profile_id,
            context_id=context_id,
            dialect_id=dialect_id,
            default_language_id=self.settings.default_language_id,
        )
        if not match.reviewable:
            return self._empty_review_response(match)
        runtime = load_rule_runtime(
            self.settings,
            language_id=match.language_id,
            profile_id=match.profile_id,
            context_id=match.context_id,
            dialect_id=match.dialect_id,
        )
        analysis = build_query_analysis(
            source_text,
            input_kind=input_kind,
            settings=self.settings,
            file_path=file_path,
            file_context=file_context,
            language_id=runtime.language_id,
            profile_id=runtime.profile.profile_id,
            context_id=runtime.context_id,
            dialect_id=runtime.dialect_id,
            query_plugin_id=match.query_plugin_id,
            detector_refs=runtime.detector_refs,
        )
        return self._review_analysis(analysis, runtime=runtime, top_k=top_k)

    def _empty_review_response(self, match) -> ReviewResponse:
        return ReviewResponse(
            language_id=match.language_id,
            profile_id=match.profile_id,
            context_id=match.context_id,
            dialect_id=match.dialect_id,
            prompt_overlay_refs=[],
            query_text="",
            detected_patterns=[],
            results=[],
        )

    def _review_analysis(self, analysis: QueryAnalysis, *, runtime, top_k: int) -> ReviewResponse:
        self._ensure_runtime_data(runtime.language_id)
        candidates = self.store.query(
            analysis.query_text,
            language_id=runtime.language_id,
            top_n=max(40, top_k * 4),
        )
        candidates = self._select_runtime_candidates(candidates, runtime)
        candidates = self._augment_with_pattern_hints(candidates, analysis, runtime.language_id)
        candidates = self._select_runtime_candidates(candidates, runtime)
        reranked = rerank_candidates(
            candidates,
            analysis,
            self.settings,
            top_k=max(len(candidates), max(30, top_k * 3)),
            policy=runtime.policy,
        )
        validated = [
            candidate
            for candidate in reranked
            if is_candidate_applicable(candidate, analysis)
        ][:top_k]
        results = [
            ReviewResult(
                rule_no=candidate.record.rule_no,
                rule_uid=candidate.record.rule_uid,
                rule_pack=candidate.record.rule_pack,
                source_family=candidate.record.source_family or candidate.record.pack_id or "",
                authority=candidate.record.authority or "",
                conflict_policy=candidate.record.conflict_policy or "",
                title=candidate.record.title,
                section=candidate.record.section,
                priority=candidate.record.priority or candidate.record.base_score,
                score=candidate.final_score,
                summary=candidate.record.summary,
                text=candidate.record.text,
                category=candidate.record.category,
                reviewability=candidate.record.reviewability,
                fix_guidance=candidate.record.fix_guidance,
                pack_id=candidate.record.pack_id,
                source_kind=candidate.record.source_kind,
                priority_tier=candidate.record.priority_tier,
                pack_weight=candidate.record.pack_weight,
                language_id=candidate.record.language_id,
                context_id=candidate.record.context_id,
                dialect_id=candidate.record.dialect_id,
                conflict_action=candidate.record.conflict_action,
            )
            for candidate in validated
        ]
        return ReviewResponse(
            language_id=runtime.language_id,
            profile_id=runtime.profile.profile_id,
            context_id=runtime.context_id,
            dialect_id=runtime.dialect_id,
            prompt_overlay_refs=list(runtime.prompt_overlay_refs),
            query_text=analysis.query_text,
            detected_patterns=[pattern.name for pattern in analysis.patterns],
            results=results,
        )

    def _augment_diff_analysis_with_context(
        self,
        analysis: QueryAnalysis,
        file_context: str | None,
    ) -> QueryAnalysis:
        if not file_context:
            return analysis

        context_analysis = build_query_analysis(
            file_context[:1500],
            input_kind="code",
            settings=self.settings,
            language_id=analysis.language_id,
            profile_id=analysis.profile_id,
            context_id=analysis.context_id,
            dialect_id=analysis.dialect_id,
            query_plugin_id=analysis.query_plugin_id,
            detector_refs=analysis.detector_refs,
        )
        if not context_analysis.patterns:
            return analysis

        diff_pattern_names = {pattern.name for pattern in analysis.patterns}
        extra_descriptions = [
            pattern.description
            for pattern in context_analysis.patterns
            if pattern.name not in diff_pattern_names
        ]
        if not extra_descriptions:
            return analysis

        context_suffix = " Additional unchanged file context hints: " + " ".join(extra_descriptions)
        return analysis.model_copy(update={"query_text": f"{analysis.query_text}{context_suffix}"})

    def _augment_with_pattern_hints(
        self,
        candidates: list[CandidateHit],
        analysis: QueryAnalysis,
        language_id: str,
    ) -> list[CandidateHit]:
        hinted_rule_nos = QueryDetectorManager(self.settings).collect_hinted_rules(
            query_plugin_id=analysis.query_plugin_id or analysis.language_id,
            patterns=analysis.patterns,
            direct_only=True,
        )
        existing_by_rule = {candidate.record.rule_no: candidate for candidate in candidates}
        for rule_no in sorted(hinted_rule_nos):
            existing = existing_by_rule.get(rule_no)
            if existing is not None:
                existing.similarity_score = max(existing.similarity_score, 0.8)
                existing.distance = min(existing.distance, 0.2)

        missing_rule_nos = sorted(hinted_rule_nos - set(existing_by_rule))
        for record in self.store.get_rules(missing_rule_nos, language_id=language_id):
            candidates.append(
                CandidateHit(
                    record=record,
                    distance=0.2,
                    similarity_score=0.8,
                )
            )
        return candidates

    def _ensure_runtime_data(self, language_id: str | None) -> None:
        if self.store.has_runtime_data(language_id):
            return
        self.ingest(force_refresh=False)

    def _select_runtime_candidates(self, candidates: list[CandidateHit], runtime) -> list[CandidateHit]:
        selected_pack_ids = set(runtime.selected_pack_ids)
        filtered: list[CandidateHit] = []
        excluded_rule_uids = {record.rule_uid for record in runtime.excluded_records}
        for candidate in candidates:
            if candidate.record.pack_id not in selected_pack_ids:
                continue
            if runtime.context_id and candidate.record.context_id not in {None, runtime.context_id}:
                continue
            if runtime.dialect_id and candidate.record.dialect_id not in {None, runtime.dialect_id}:
                continue
            if candidate.record.rule_uid in excluded_rule_uids:
                continue
            candidate.record.pack_weight = float(
                runtime.policy.pack_weights.get(
                    candidate.record.pack_id or "",
                    runtime.policy.defaults.default_pack_weight,
                )
            )
            filtered.append(candidate)
        return filtered
