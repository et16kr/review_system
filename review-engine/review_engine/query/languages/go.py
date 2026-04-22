from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="go",
    display_name="Go",
    default_focus="error propagation, defer-based cleanup, context propagation, and goroutine lifetime",
    pattern_specs=(
        PatternSpec(
            "ignored_error",
            r"_,\s*err\s*:=",
            "Error-returning call detected; review whether err is handled immediately and completely.",
            0.82,
        ),
        PatternSpec(
            "defer_close_missing",
            r"os\.Open\(|http\.Get\(",
            "Resource-opening call detected; review whether close cleanup is paired promptly.",
            0.9,
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
        "defer_close_missing": ("GO.1", "GO.6"),
        "context_missing": ("GO.2", "GO.5"),
        "goroutine_leak": ("GO.4", "GO.10"),
        "context_background": ("GO.8",),
        "panic_call": ("GO.9",),
    },
    direct_hint_patterns={
        "ignored_error",
        "defer_close_missing",
        "context_missing",
        "goroutine_leak",
        "context_background",
        "panic_call",
    },
)
