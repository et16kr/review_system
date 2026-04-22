from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="rust",
    display_name="Rust",
    default_focus="error propagation, unsafe boundaries, panic behavior, and ownership-driven API clarity",
    pattern_specs=(
        PatternSpec(
            "unwrap_usage",
            r"\.(?:unwrap|expect)\s*\(",
            "unwrap/expect detected; review panic behavior and recoverable error handling.",
            0.95,
        ),
        PatternSpec(
            "unsafe_block",
            r"\bunsafe\s*\{",
            "unsafe block detected; review invariants, containment, and justification.",
            1.0,
        ),
        PatternSpec(
            "panic_macro",
            r"\bpanic!\s*\(",
            "panic! detected; review failure mode and whether error propagation is preferable.",
            0.88,
        ),
        PatternSpec(
            "todo_macro",
            r"\b(?:todo|unimplemented)!\s*\(",
            "todo!/unimplemented! detected; review production-readiness and failure behavior.",
            0.92,
        ),
        PatternSpec(
            "dbg_macro",
            r"\bdbg!\s*\(",
            "dbg! macro detected; review whether temporary debugging output is leaking into runtime paths.",
            0.75,
        ),
        PatternSpec(
            "unsafe_fn",
            r"\bunsafe\s+fn\b",
            "unsafe fn detected; review caller invariants and whether the unsafe contract is documented at the boundary.",
            0.9,
        ),
    ),
    hinted_rules={
        "unwrap_usage": ("RUST.2", "RUST.4", "RUST.5"),
        "unsafe_block": ("RUST.1", "RUST.6"),
        "panic_macro": ("RUST.3", "RUST.4"),
        "todo_macro": ("RUST.3", "RUST.7"),
        "dbg_macro": ("RUST.8",),
        "unsafe_fn": ("RUST.9",),
    },
    direct_hint_patterns={
        "unwrap_usage",
        "unsafe_block",
        "panic_macro",
        "todo_macro",
        "dbg_macro",
        "unsafe_fn",
    },
)
