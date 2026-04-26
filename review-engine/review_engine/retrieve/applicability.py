from __future__ import annotations

from review_engine.models import CandidateHit, QueryAnalysis

DIRECT_CATEGORY_SIGNALS: dict[str, set[str]] = {
    "memory": {
        "raw_new",
        "malloc_free",
        "manual_delete",
        "free_without_null_reset",
        "manual_cleanup_goto",
        "mutable_default",
    },
    "error_handling": {
        "ide_rc_flow",
        "ide_exception_flow",
        "ide_assert",
        "error_code_flow",
        "bare_except",
        "except_exception",
        "promise_without_await",
        "void_fetch_call",
        "ignored_error",
        "sentinel_error_compare",
        "context_missing",
        "context_background",
        "goroutine_leak",
        "catch_exception",
        "assert_usage",
        "panic_call",
        "unwrap_usage",
        "dbg_macro",
        "panic_macro",
        "todo_macro",
        "tokio_detached_spawn",
        "set_e_missing",
        "async_effect_callback",
        "cuda_kernel_launch",
    },
    "wrapper_usage": {"direct_system_call", "manual_lock_unlock"},
    "portability": {"direct_system_header", "include_portability"},
    "control_flow": {
        "continue_usage",
        "switch_without_default",
        "for_initializer_declaration",
        "loose_equality",
    },
    "comment_usage": {"line_comment", "commented_out_code"},
    "format_usage": {"primitive_format_specifier", "printf_usage"},
    "type_usage": {
        "primitive_types",
        "primitive_type_usage",
        "typedef_usage",
        "any_type",
        "non_null_assertion",
        "ts_ignore",
        "ts_nocheck",
        "ts_expect_error",
        "null_return",
        "unsafe_string_api",
        "malloc_free",
        "ownership_ambiguity",
    },
}

PATTERN_ALIASES: dict[str, set[str]] = {
    "primitive_types": {"primitive_type_usage"},
    "primitive_type_usage": {"primitive_types"},
    "ide_exception_flow": {"ide_test_raise", "error_code_flow"},
    "ide_test_raise": {"ide_exception_flow", "error_code_flow"},
    "ide_rc_flow": {"error_code_flow"},
    "error_code_flow": {"ide_rc_flow", "ide_exception_flow", "ide_test_raise"},
}


def is_candidate_applicable(candidate: CandidateHit, query_analysis: QueryAnalysis) -> bool:
    detected_patterns = _expanded_patterns({pattern.name for pattern in query_analysis.patterns})
    trigger_patterns = set(candidate.record.trigger_patterns)

    if candidate.record.reviewability != "auto_review":
        return False

    if trigger_patterns:
        matched_patterns = trigger_patterns & detected_patterns
        if not matched_patterns:
            return False

        direct_signals = DIRECT_CATEGORY_SIGNALS.get(candidate.record.category)
        if direct_signals is None:
            return True
        return bool(matched_patterns & direct_signals)

    return candidate.record.false_positive_risk != "high"


def _expanded_patterns(patterns: set[str]) -> set[str]:
    expanded = set(patterns)
    for pattern in list(patterns):
        expanded.update(PATTERN_ALIASES.get(pattern, set()))
    return expanded
