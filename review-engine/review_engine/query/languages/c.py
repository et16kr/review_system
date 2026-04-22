from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="c",
    display_name="C",
    default_focus="manual memory management, POSIX resource cleanup, string safety, and explicit error handling",
    pattern_specs=(
        PatternSpec(
            "malloc_free",
            r"\b(?:malloc|calloc|realloc|free)\s*\(",
            "Manual heap allocation detected; review ownership, lifetime, and cleanup paths.",
            1.0,
        ),
        PatternSpec(
            "unsafe_string_api",
            r"\b(?:strcpy|strcat|sprintf|gets)\s*\(",
            "Unsafe C string API detected; review bounds handling and safer alternatives.",
            1.0,
        ),
        PatternSpec(
            "manual_cleanup_goto",
            r"\bgoto\s+\w*(?:cleanup|error|fail)\w*\b",
            "Manual cleanup jump detected; review whether cleanup stays consistent across failure paths.",
            0.82,
        ),
        PatternSpec(
            "primitive_format_specifier",
            r"%(?:d|i|u|x|X|ld|lld|lu|llu|p|f|s)",
            "printf-style formatting detected; review format safety and type alignment.",
            0.75,
        ),
    ),
    hinted_rules={
        "malloc_free": ("C.NM.1", "C.NM.2", "C.NM.3", "C.POSIX.2", "C.POSIX.4"),
        "unsafe_string_api": ("C.POSIX.1", "C.POSIX.3", "C.POSIX.5", "C.PROJ.1", "C.PROJ.2"),
        "manual_cleanup_goto": ("C.POSIX.2", "C.POSIX.4", "C.POSIX.6"),
        "primitive_format_specifier": ("C.POSIX.3", "C.POSIX.5", "C.PROJ.3"),
    },
    direct_hint_patterns={
        "malloc_free",
        "unsafe_string_api",
        "manual_cleanup_goto",
        "primitive_format_specifier",
    },
)
