from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="typescript",
    display_name="TypeScript",
    default_focus="type narrowing, unsafe any usage, async error handling, and public API typing",
    pattern_specs=(
        PatternSpec(
            "any_type",
            r":\s*any\b|\bas\s+any\b",
            "any usage detected; review whether the type boundary can stay explicit and narrow.",
            1.0,
        ),
        PatternSpec(
            "non_null_assertion",
            r"\w+!\.",
            "Non-null assertion detected; review whether the value is actually proven safe.",
            0.9,
        ),
        PatternSpec(
            "ts_ignore",
            r"@ts-ignore",
            "TypeScript ignore directive detected; review whether the type error should be fixed directly.",
            0.92,
        ),
        PatternSpec(
            "unsafe_json_parse",
            r"JSON\.parse\(",
            "JSON.parse detected; review runtime validation at untrusted boundaries.",
            0.78,
        ),
        PatternSpec(
            "promise_without_await",
            r"\.then\s*\(",
            "Promise chaining detected; review async error propagation and readability.",
            0.72,
        ),
        PatternSpec(
            "ts_expect_error",
            r"@ts-expect-error",
            "TypeScript expect-error directive detected; review whether the unsafe boundary is still intentional and locally justified.",
            0.9,
        ),
        PatternSpec(
            "double_cast",
            r"\bas\s+unknown\s+as\s+\w+",
            "Double cast through unknown detected; review whether runtime validation is missing at the boundary.",
            0.92,
        ),
    ),
    hinted_rules={
        "any_type": ("TS.1", "TS.3", "TS.API.5"),
        "non_null_assertion": ("TS.2", "TS.4"),
        "ts_ignore": ("TS.API.1", "TS.API.3"),
        "unsafe_json_parse": ("TS.API.2", "TS.API.4", "TS.API.5"),
        "promise_without_await": ("TS.5",),
        "ts_expect_error": ("TS.API.6",),
        "double_cast": ("TS.API.7",),
    },
    direct_hint_patterns={
        "any_type",
        "non_null_assertion",
        "ts_ignore",
        "unsafe_json_parse",
        "promise_without_await",
        "ts_expect_error",
        "double_cast",
    },
)
