from __future__ import annotations

from review_engine.config import Settings, load_json_file
from review_engine.models import CandidateHit, QueryAnalysis
from review_engine.query.cpp_feature_extractor import PATTERN_RULE_HINTS, collect_hinted_rules
from review_engine.text_utils import tokenize


def rerank_candidates(
    candidates: list[CandidateHit],
    query_analysis: QueryAnalysis,
    settings: Settings,
    top_k: int = 10,
) -> list[CandidateHit]:
    authority_scores = load_json_file(settings.source_priority_path)["authority_scores"]
    filtered = [
        candidate
        for candidate in candidates
        if candidate.record.conflict_policy not in {"excluded", "overridden"}
    ]

    for candidate in filtered:
        candidate.authority_score = float(authority_scores[candidate.record.source_family])
        candidate.pattern_boost = _pattern_boost(candidate, query_analysis)
        candidate.final_score = round(
            candidate.similarity_score * 0.45
            + candidate.authority_score * 0.20
            + candidate.record.priority * 0.20
            + candidate.record.severity_default * 0.10
            + candidate.pattern_boost * 0.05,
            4,
        )

    filtered.sort(
        key=lambda candidate: (
            candidate.final_score,
            _hint_match_count(candidate, query_analysis),
            candidate.record.review_rank_default,
            candidate.record.source_family == "altibase",
            candidate.record.priority,
        ),
        reverse=True,
    )
    return filtered[:top_k]


def _pattern_boost(candidate: CandidateHit, query_analysis: QueryAnalysis) -> float:
    if not query_analysis.patterns:
        return 0.0

    hinted_rules = collect_hinted_rules(query_analysis.patterns, direct_only=True)
    if candidate.record.rule_no in hinted_rules:
        return 1.0

    candidate_terms = set(tokenize(" ".join(candidate.record.keywords)))
    candidate_terms.update(tokenize(candidate.record.title))
    candidate_terms.update(tokenize(candidate.record.summary))

    matched_weight = 0.0
    total_weight = 0.0
    for pattern in query_analysis.patterns:
        total_weight += pattern.weight
        pattern_terms = set(tokenize(pattern.name.replace("_", " ")))
        pattern_terms.update(tokenize(pattern.description))
        if candidate_terms & pattern_terms:
            matched_weight += pattern.weight

    if total_weight == 0.0:
        return 0.0
    return round(min(1.0, matched_weight / total_weight), 4)


def _exact_hint_match(candidate: CandidateHit, query_analysis: QueryAnalysis) -> bool:
    return any(
        candidate.record.rule_no in PATTERN_RULE_HINTS.get(pattern.name, [])
        for pattern in query_analysis.patterns
    )


def _hint_match_count(candidate: CandidateHit, query_analysis: QueryAnalysis) -> int:
    hinted_rules = collect_hinted_rules(query_analysis.patterns, direct_only=True)
    return 1 if candidate.record.rule_no in hinted_rules else 0
