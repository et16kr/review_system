from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="cpp",
    display_name="C++",
    default_focus="resource ownership, RAII, type safety, portability, and control-flow clarity",
    pattern_specs=(
        PatternSpec(
            "raw_new",
            r"\bnew\b",
            "Possible raw owning pointer allocation with new; review ownership and RAII guidance.",
            1.0,
        ),
        PatternSpec(
            "malloc_free",
            r"\b(?:malloc|calloc|realloc|free)\s*\(",
            "Manual C-style allocation or free detected; review resource management guidance.",
            1.0,
        ),
        PatternSpec(
            "manual_delete",
            r"\bdelete(?:\s*\[\s*\])?\b",
            "Explicit delete detected; review ownership, RAII, and explicit delete guidance.",
            0.95,
        ),
        PatternSpec(
            "manual_lock_unlock",
            r"(?:\.|->)\s*(?:lock|unlock)\s*\(",
            "Manual lock or unlock call detected; review scoped locking guidance.",
            0.9,
        ),
        PatternSpec(
            "ownership_ambiguity",
            r"\b[A-Za-z_]\w*\s*\*\s+[A-Za-z_]\w+",
            "Raw pointer usage may imply unclear ownership; review ownership boundaries.",
            0.8,
        ),
        PatternSpec(
            "return_move_local",
            r"\breturn\s+std::move\s*\(",
            "Return of std::move(local) detected; review move misuse guidance.",
            0.7,
        ),
        PatternSpec(
            "line_comment",
            r"//",
            "Line comments detected; review whether code or naming can carry the intent more directly.",
            0.6,
        ),
        PatternSpec(
            "primitive_types",
            r"\b(?:int|long|short|char|float|double|bool)\b",
            "Primitive type usage detected; review stronger type boundaries.",
            0.8,
        ),
        PatternSpec(
            "direct_system_header",
            r"#include\s*<(?:stdio\.h|stdlib\.h|string\.h|unistd\.h|pthread\.h|iostream|vector|memory|mutex)>",
            "Direct system or standard header include detected; review portability and include guidance.",
            0.95,
        ),
        PatternSpec(
            "direct_system_call",
            r"\b(?:printf|malloc|free|exit|fopen|fclose|open|close)\s*\(",
            "Direct system library call detected; review encapsulation and safer interface guidance.",
            0.85,
        ),
        PatternSpec(
            "continue_usage",
            r"\bcontinue\s*;",
            "Continue statement detected; review control-flow clarity guidance.",
            0.82,
        ),
        PatternSpec(
            "switch_without_default",
            r"\bswitch\s*\(",
            "Switch statement detected; review default-path handling and fallthrough clarity.",
            0.65,
        ),
        PatternSpec(
            "for_initializer_declaration",
            r"\bfor\s*\([^;]*=\s*[^;]+;",
            "Variable declaration inside for initializer detected; review loop scoping guidance.",
            0.8,
        ),
        PatternSpec(
            "primitive_format_specifier",
            r"%(?:d|i|u|x|X|ld|lld|lu|llu|p|f|s)",
            "Primitive format specifier detected; review formatting and I/O guidance.",
            0.78,
        ),
    ),
    hinted_rules={
        "raw_new": ("R.11", "R.12", "R.20", "R.3", "R.5", "R.22", "R.23", "R.30", "R.32"),
        "malloc_free": ("R.10", "R.12", "R.1", "P.8", "E.19"),
        "manual_delete": ("R.11", "R.12", "R.20", "R.3", "R.15"),
        "manual_lock_unlock": ("R.1", "CP.20", "CP.21", "CP.22"),
        "ownership_ambiguity": ("I.11", "R.20", "R.11"),
        "return_move_local": ("F.48",),
        "primitive_types": ("I.4", "F.16"),
        "direct_system_header": ("SF.13", "P.11"),
        "direct_system_call": ("SL.io.3", "P.11", "E.19"),
        "continue_usage": ("ES.77",),
        "switch_without_default": ("ES.78", "ES.79"),
        "primitive_format_specifier": ("SL.io.3", "ES.34"),
    },
    direct_hint_patterns={
        "raw_new",
        "malloc_free",
        "manual_delete",
        "manual_lock_unlock",
        "primitive_types",
        "direct_system_header",
        "direct_system_call",
        "continue_usage",
        "switch_without_default",
        "for_initializer_declaration",
        "primitive_format_specifier",
    },
)
