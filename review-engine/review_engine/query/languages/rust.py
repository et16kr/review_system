from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="rust",
    display_name="Rust",
    default_focus="error propagation, unsafe boundaries, panic behavior, and Tokio async ownership",
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
        PatternSpec(
            "tokio_blocking_in_async",
            r"(?is)async\s+fn\b[\s\S]{0,500}\b(?:std::thread::sleep|reqwest::blocking|std::fs::|std::process::Command::new)\b",
            "Blocking std or reqwest::blocking path detected inside async Rust; review Tokio runtime starvation and ownership.",
            0.96,
        ),
        PatternSpec(
            "tokio_detached_spawn",
            r"\btokio::spawn\s*\(",
            "tokio::spawn detected; review join, cancellation, and detached-task ownership.",
            0.84,
        ),
        PatternSpec(
            "tokio_unbounded_channel",
            r"\bunbounded_channel(?:\s*::\s*<[^()]+>)?\s*\(",
            "Unbounded Tokio channel detected; review backpressure and queue growth assumptions.",
            0.88,
        ),
        PatternSpec(
            "tokio_test_sleep",
            r"(?is)#\[tokio::test\][\s\S]{0,400}\bsleep\s*\(",
            "tokio::test with timing sleep detected; review test determinism and scheduler assumptions.",
            0.72,
        ),
    ),
    hinted_rules={
        "unwrap_usage": ("RUST.2", "RUST.4", "RUST.5"),
        "unsafe_block": ("RUST.1", "RUST.6"),
        "panic_macro": ("RUST.3", "RUST.4"),
        "todo_macro": ("RUST.3", "RUST.7"),
        "dbg_macro": ("RUST.8",),
        "unsafe_fn": ("RUST.9",),
        "tokio_blocking_in_async": ("RUST.TOKIO.1",),
        "tokio_detached_spawn": ("RUST.TOKIO.2",),
        "tokio_unbounded_channel": ("RUST.TOKIO.3",),
        "tokio_test_sleep": ("RUST.TOKIO.REF.2",),
    },
    direct_hint_patterns={
        "unwrap_usage",
        "unsafe_block",
        "panic_macro",
        "todo_macro",
        "dbg_macro",
        "unsafe_fn",
        "tokio_blocking_in_async",
        "tokio_detached_spawn",
        "tokio_unbounded_channel",
        "tokio_test_sleep",
    },
)
