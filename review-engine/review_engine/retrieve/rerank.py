from __future__ import annotations

from functools import cmp_to_key

from review_engine.config import Settings
from review_engine.models import CandidateHit, PriorityPolicy, QueryAnalysis
from review_engine.query.detectors import QueryDetectorManager
from review_engine.text_utils import tokenize


def rerank_candidates(
    candidates: list[CandidateHit],
    query_analysis: QueryAnalysis,
    settings: Settings,
    top_k: int = 10,
    *,
    policy: PriorityPolicy | None = None,
) -> list[CandidateHit]:
    del settings
    effective_policy = policy or PriorityPolicy(policy_id="default")
    filtered = [
        candidate
        for candidate in candidates
        if candidate.record.conflict_action not in {"excluded", "overridden"}
    ]

    for candidate in filtered:
        candidate.pack_weight_score = float(candidate.record.pack_weight)
        candidate.pattern_boost = _pattern_boost(candidate, query_analysis)
        tier_boost = _tier_rank_map(effective_policy).get(candidate.record.priority_tier, 0) / max(
            1,
            len(effective_policy.tier_order),
        )
        candidate.final_score = round(
            candidate.similarity_score * 0.36
            + candidate.pack_weight_score * 0.16
            + candidate.record.base_score * 0.18
            + candidate.record.severity_default * 0.10
            + candidate.pattern_boost * 0.10
            + candidate.record.specificity * 0.07
            + tier_boost * 0.03,
            4,
        )

    filtered.sort(
        key=cmp_to_key(
            lambda left, right: _compare_candidates(
                left,
                right,
                effective_policy,
            )
        )
    )
    return filtered[:top_k]


def _compare_candidates(
    left: CandidateHit,
    right: CandidateHit,
    policy: PriorityPolicy,
) -> int:
    for breaker in policy.tie_breakers:
        breaker_cmp = _compare_tie_breaker(left, right, breaker, policy)
        if breaker_cmp != 0:
            return breaker_cmp

    final_cmp = _compare_desc(left.final_score, right.final_score)
    if final_cmp != 0:
        return final_cmp

    left_id = left.record.id or left.record.rule_no
    right_id = right.record.id or right.record.rule_no
    if left_id < right_id:
        return -1
    if left_id > right_id:
        return 1
    return 0


def _compare_tie_breaker(
    left: CandidateHit,
    right: CandidateHit,
    breaker: str,
    policy: PriorityPolicy,
) -> int:
    if breaker == "explicit_override":
        return _compare_desc(
            int(left.record.explicit_override),
            int(right.record.explicit_override),
        )
    if breaker == "higher_tier":
        rank_map = _tier_rank_map(policy)
        return _compare_desc(
            rank_map.get(left.record.priority_tier, 0),
            rank_map.get(right.record.priority_tier, 0),
        )
    if breaker == "higher_pattern_boost":
        return _compare_desc(left.pattern_boost, right.pattern_boost)
    if breaker == "higher_similarity":
        return _compare_desc(left.similarity_score, right.similarity_score)
    if breaker == "higher_specificity":
        return _compare_desc(left.record.specificity, right.record.specificity)
    if breaker == "higher_base_score":
        return _compare_desc(left.record.base_score, right.record.base_score)
    if breaker == "higher_pack_weight":
        return _compare_desc(left.record.pack_weight, right.record.pack_weight)
    if breaker == "lexical_rule_id":
        left_id = left.record.id or left.record.rule_no
        right_id = right.record.id or right.record.rule_no
        if left_id < right_id:
            return -1
        if left_id > right_id:
            return 1
        return 0
    return 0


def _tier_rank_map(policy: PriorityPolicy) -> dict[str, int]:
    highest = len(policy.tier_order)
    return {tier: highest - index for index, tier in enumerate(policy.tier_order)}


def _compare_desc(left: float | int, right: float | int) -> int:
    if left > right:
        return -1
    if left < right:
        return 1
    return 0


def _pattern_boost(candidate: CandidateHit, query_analysis: QueryAnalysis) -> float:
    if not query_analysis.patterns:
        return 0.0
    patterns_by_name = {pattern.name: pattern for pattern in query_analysis.patterns}
    detected_pattern_names = set(patterns_by_name)

    hinted_rules = QueryDetectorManager().collect_hinted_rules(
        query_plugin_id=query_analysis.query_plugin_id or query_analysis.language_id,
        patterns=query_analysis.patterns,
        direct_only=True,
    )
    if candidate.record.rule_no in hinted_rules:
        return 1.0

    exact_trigger_matches = set(candidate.record.trigger_patterns) & detected_pattern_names
    if exact_trigger_matches:
        total_query_weight = sum(pattern.weight for pattern in query_analysis.patterns) or 1.0
        matched_weight = sum(patterns_by_name[name].weight for name in exact_trigger_matches)
        exact_match_boost = 0.88 + min(0.1, matched_weight / total_query_weight * 0.1)
        return round(min(0.98, exact_match_boost), 4)

    candidate_terms = set(tokenize(" ".join(candidate.record.keywords)))
    candidate_terms.update(tokenize(candidate.record.title))
    candidate_terms.update(tokenize(candidate.record.summary))

    matched_weight = 0.0
    total_weight = 0.0
    for pattern in query_analysis.patterns:
        total_weight += pattern.weight
        pattern_terms = set(tokenize(pattern.name.replace("_", " ")))
        pattern_terms.update(tokenize(pattern.description))
        overlapping_terms = candidate_terms & pattern_terms
        if not overlapping_terms:
            continue
        matched_weight += pattern.weight * (len(overlapping_terms) / max(1, len(pattern_terms)))

    if total_weight == 0.0:
        return 0.0
    return round(min(1.0, matched_weight / total_weight), 4)
