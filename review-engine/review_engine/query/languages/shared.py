from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="shared",
    display_name="shared code",
    default_focus="security-sensitive inputs, secrets handling, and unsafe command or query construction",
    pattern_specs=(
        PatternSpec(
            "hardcoded_secret",
            r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"'][^\"']+[\"']",
            "Hardcoded secret-like value detected; review secret handling and configuration boundaries.",
            1.0,
        ),
        PatternSpec(
            "shell_injection",
            r"(?i)(os\.system|system\(|Runtime\.getRuntime\(\)\.exec|subprocess\..*shell\s*=\s*True)",
            "Possible shell execution path detected; review command construction and injection risk.",
            0.95,
        ),
        PatternSpec(
            "sql_injection",
            r"(?i)(SELECT|UPDATE|DELETE|INSERT).*(\+|%s|format\(|f\")",
            "Dynamic SQL construction detected; review parameterization and injection risk.",
            0.95,
        ),
    ),
    hinted_rules={
        "hardcoded_secret": ("SEC.1", "SEC.4", "SEC.7"),
        "shell_injection": ("SEC.2", "SEC.5"),
        "sql_injection": ("SEC.3", "SEC.6"),
    },
    direct_hint_patterns={
        "hardcoded_secret",
        "shell_injection",
        "sql_injection",
    },
)
