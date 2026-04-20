from __future__ import annotations

from review_engine.config import Settings, get_settings
from review_engine.ingest.build_records import ingest_all_sources
from review_engine.ingest.chroma_store import ChromaGuidelineStore
from review_engine.models import CandidateHit, IngestionSummary, ReviewResponse, ReviewResult
from review_engine.query.code_to_query import build_query_analysis
from review_engine.query.cpp_feature_extractor import collect_hinted_rules
from review_engine.retrieve.applicability import is_candidate_applicable
from review_engine.retrieve.rerank import rerank_candidates


class GuidelineSearchService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = ChromaGuidelineStore(self.settings)

    def ingest(self, force_refresh: bool = False) -> IngestionSummary:
        return ingest_all_sources(self.settings, force_refresh=force_refresh)

    def review_code(self, code: str, top_k: int = 10) -> ReviewResponse:
        return self._review_text(code, input_kind="code", top_k=top_k)

    def review_diff(self, diff: str, top_k: int = 10) -> ReviewResponse:
        return self._review_text(diff, input_kind="diff", top_k=top_k)

    def inspect_rule(self, rule_no: str):
        return self.store.get_rule(rule_no)

    def _review_text(self, source_text: str, input_kind: str, top_k: int) -> ReviewResponse:
        analysis = build_query_analysis(source_text, input_kind=input_kind)
        candidates = self.store.query(analysis.query_text, top_n=max(30, top_k * 3))
        candidates = self._augment_with_pattern_hints(candidates, analysis)
        reranked = rerank_candidates(candidates, analysis, self.settings, top_k=max(30, top_k * 3))
        validated = [
            candidate
            for candidate in reranked
            if is_candidate_applicable(candidate, analysis)
        ][:top_k]
        results = [
            ReviewResult(
                rule_no=candidate.record.rule_no,
                source_family=candidate.record.source_family,
                authority=candidate.record.authority,
                conflict_policy=candidate.record.conflict_policy,
                title=candidate.record.title,
                section=candidate.record.section,
                priority=candidate.record.priority,
                score=candidate.final_score,
                summary=candidate.record.summary,
                text=candidate.record.text,
                category=candidate.record.category,
                reviewability=candidate.record.reviewability,
                fix_guidance=candidate.record.fix_guidance,
            )
            for candidate in validated
        ]
        return ReviewResponse(
            query_text=analysis.query_text,
            detected_patterns=[pattern.name for pattern in analysis.patterns],
            results=results,
        )

    def _augment_with_pattern_hints(
        self, candidates: list[CandidateHit], analysis
    ) -> list[CandidateHit]:
        hinted_rule_nos = collect_hinted_rules(analysis.patterns, direct_only=True)
        existing_by_rule = {candidate.record.rule_no: candidate for candidate in candidates}
        for rule_no in sorted(hinted_rule_nos):
            existing = existing_by_rule.get(rule_no)
            if existing is not None:
                existing.similarity_score = max(existing.similarity_score, 0.8)
                existing.distance = min(existing.distance, 0.2)

        missing_rule_nos = sorted(hinted_rule_nos - set(existing_by_rule))
        for record in self.store.get_rules(missing_rule_nos):
            candidates.append(
                CandidateHit(
                    record=record,
                    distance=0.2,
                    similarity_score=0.8,
                )
            )
        return candidates
