from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="go",
    display_name="Go",
    default_focus="error propagation, defer-based cleanup, HTTP handler validation boundaries, context propagation, and goroutine lifetime",
    pattern_specs=(
        PatternSpec(
            "ignored_error",
            r"_,\s*err\s*:=",
            "Error-returning call detected; review whether err is handled immediately and completely.",
            0.82,
        ),
        PatternSpec(
            "sentinel_error_compare",
            r"\berr\s*(?:==|!=)\s*(?!nil\b)[A-Za-z_][\w\.]*",
            "Sentinel error comparison detected; review whether errors.Is/errors.As is needed if wrappers can appear.",
            0.8,
        ),
        PatternSpec(
            "defer_close_missing",
            r"os\.Open\(|http\.Get\(",
            "Resource-opening call detected; review whether close cleanup is paired promptly.",
            0.9,
        ),
        PatternSpec(
            "transaction_commit_without_rollback",
            r"(?s)(?P<tx>[A-Za-z_]\w*)\s*,\s*[A-Za-z_]\w*\s*(?::=|=)\s*.*?\.(?:Begin|BeginTx)\([^)]*\)(?:(?!\b(?P=tx)\.Rollback\(\)).)*?\b(?P=tx)\.Commit\(",
            "Transaction starts and commits without a visible rollback guard; review failure-path cleanup ownership.",
            0.86,
        ),
        PatternSpec(
            "http_handler_json_decode_without_validation",
            r"(?is)func\s+(?:\([^)]*\)\s*)?\w+\s*\([^)]*http\.ResponseWriter[^)]*\*http\.Request[^)]*\)\s*\{[\s\S]{0,700}(?:(?!\bDisallowUnknownFields\s*\().)*?\bjson\.NewDecoder\(\s*[A-Za-z_]\w*\.Body\s*\)\.Decode\(\s*&(?P<payload>[A-Za-z_]\w+)\s*\)(?:(?!\b(?:[A-Za-z_]\w*\.)?(?:Validate|Struct)\s*\().){0,220}\b(?:(?P=payload)\.(?!Validate\b)[A-Za-z_]\w+|(?!Validate\b|Struct\b)[A-Za-z_]\w+\([^)]*\b(?P=payload)\b)",
            "net/http handler decodes request JSON and uses it without a visible validation step; review the boundary contract.",
            0.9,
        ),
        PatternSpec(
            "http_handler_json_decoder_variable_without_validation",
            r"(?is)func\s+(?:\([^)]*\)\s*)?\w+\s*\([^)]*http\.ResponseWriter[^)]*\*http\.Request[^)]*\)\s*\{[\s\S]{0,700}(?:(?!\bDisallowUnknownFields\s*\().)*?\b(?P<decoder>[A-Za-z_]\w*)\s*:?=\s*json\.NewDecoder\(\s*[A-Za-z_]\w*\.Body\s*\)(?:(?!\bDisallowUnknownFields\s*\().){0,180}\b(?P=decoder)\.Decode\(\s*&(?P<payload>[A-Za-z_]\w+)\s*\)(?:(?!\b(?:[A-Za-z_]\w*\.)?(?:Validate|Struct)\s*\().){0,220}\b(?:(?P=payload)\.(?!Validate\b)[A-Za-z_]\w+|(?!Validate\b|Struct\b)[A-Za-z_]\w+\([^)]*\b(?P=payload)\b)",
            "net/http handler keeps a JSON decoder variable, decodes request input, and uses it without a visible validation step; review the boundary contract.",
            0.89,
        ),
        PatternSpec(
            "gin_handler_json_bind_without_validation",
            r"(?is)func\s+(?:\([^)]*\)\s*)?\w+\s*\([^)]*(?P<context>[A-Za-z_]\w*)\s+\*gin\.Context[^)]*\)\s*\{[\s\S]{0,700}\b(?P=context)\.(?:ShouldBindJSON|BindJSON)\(\s*&(?P<payload>[A-Za-z_]\w+)\s*\)(?:(?!\b(?:[A-Za-z_]\w*\.)?(?:Validate|Struct)\s*\().){0,220}\b(?:(?P=payload)\.(?!Validate\b)[A-Za-z_]\w+|(?!Validate\b|Struct\b)[A-Za-z_]\w+\([^)]*\b(?P=payload)\b)",
            "Gin handler binds request JSON and uses it without a visible validation step; review the boundary contract.",
            0.89,
        ),
        PatternSpec(
            "context_missing",
            r"http\.NewRequest\(",
            "Request construction detected; review whether context propagation should be explicit.",
            0.78,
        ),
        PatternSpec(
            "goroutine_leak",
            r"\bgo\s+(?:\w+\(|func\b)",
            "Goroutine launch detected; review lifecycle ownership, cancellation, and leak risk.",
            0.85,
        ),
        PatternSpec(
            "context_background",
            r"context\.(?:Background|TODO)\(",
            "Detached context creation detected; review whether this work should inherit request cancellation or deadlines.",
            0.82,
        ),
        PatternSpec(
            "panic_call",
            r"\bpanic\s*\(",
            "panic call detected; review whether the failure should propagate as an error instead of crashing the call path.",
            0.88,
        ),
    ),
    hinted_rules={
        "ignored_error": ("GO.3", "GO.7"),
        "sentinel_error_compare": ("GO.11",),
        "defer_close_missing": ("GO.1", "GO.6"),
        "transaction_commit_without_rollback": ("GO.12",),
        "http_handler_json_decode_without_validation": ("GO.13",),
        "http_handler_json_decoder_variable_without_validation": ("GO.13",),
        "gin_handler_json_bind_without_validation": ("GO.13",),
        "context_missing": ("GO.2", "GO.5"),
        "goroutine_leak": ("GO.4", "GO.10"),
        "context_background": ("GO.8",),
        "panic_call": ("GO.9",),
    },
    direct_hint_patterns={
        "ignored_error",
        "sentinel_error_compare",
        "defer_close_missing",
        "transaction_commit_without_rollback",
        "http_handler_json_decode_without_validation",
        "http_handler_json_decoder_variable_without_validation",
        "gin_handler_json_bind_without_validation",
        "context_missing",
        "goroutine_leak",
        "context_background",
        "panic_call",
    },
)
