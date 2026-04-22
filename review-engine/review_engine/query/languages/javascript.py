from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="javascript",
    display_name="JavaScript",
    default_focus="async error handling, runtime type assumptions, DOM safety, and module-side effects",
    pattern_specs=(
        PatternSpec(
            "eval_usage",
            r"\beval\s*\(",
            "eval usage detected; review code injection risk and safer parsing alternatives.",
            1.0,
        ),
        PatternSpec(
            "innerhtml",
            r"\.innerHTML\s*=",
            "innerHTML assignment detected; review DOM injection and escaping boundaries.",
            0.95,
        ),
        PatternSpec(
            "loose_equality",
            r"[^=!]==[^=]|!=[^=]",
            "Loose equality detected; review coercion risk and intent clarity.",
            0.72,
        ),
        PatternSpec(
            "promise_without_await",
            r"\.then\s*\(",
            "Promise chaining detected; review error propagation and async readability.",
            0.72,
        ),
        PatternSpec(
            "document_write",
            r"document\.write\s*\(",
            "document.write detected; review raw HTML injection and page mutation safety.",
            0.98,
        ),
        PatternSpec(
            "settimeout_string",
            r"\b(?:setTimeout|setInterval)\s*\(\s*[\"']",
            "String-based timer callback detected; review dynamic execution and safer function references.",
            0.92,
        ),
    ),
    hinted_rules={
        "eval_usage": ("JS.1", "JS.4"),
        "innerhtml": ("JS.2", "JS.3"),
        "loose_equality": ("JS.NODE.2", "JS.NODE.4"),
        "promise_without_await": ("JS.NODE.1", "JS.NODE.3"),
        "document_write": ("JS.5",),
        "settimeout_string": ("JS.NODE.5",),
    },
    direct_hint_patterns={
        "eval_usage",
        "innerhtml",
        "loose_equality",
        "promise_without_await",
        "document_write",
        "settimeout_string",
    },
)
