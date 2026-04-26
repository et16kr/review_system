from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


_DYNAMIC_SQL_PATTERN = (
    r"(?is)\b(?:SELECT|UPDATE|DELETE|INSERT)\b[\s\S]{0,240}"
    r"(?:\+|%s|format\s*\(|f[\"']|\$\{)"
)
_HARDCODED_SECRET_PATTERN = (
    r"(?i)(api[_-]?key|secret|token|password)\s*(?::=|=|:)\s*[\"'][^\"']+[\"']"
)
_SHELL_INJECTION_PATTERN = (
    r"(?i)(os\.system|system\(|Runtime\.getRuntime\(\)\.exec|"
    r"subprocess\..*shell\s*=\s*True|child_process\.exec\s*\(|"
    r"exec\.Command\s*\(\s*[\"'](?:sh|bash|cmd|powershell)[\"']\s*,\s*[\"'](?:-c|/c)[\"'])"
)

PLUGIN = LanguageQueryPlugin(
    plugin_id="shared",
    display_name="shared code",
    default_focus="security-sensitive inputs, secrets handling, and unsafe command or query construction",
    pattern_specs=(
        PatternSpec(
            "hardcoded_secret",
            _HARDCODED_SECRET_PATTERN,
            "Hardcoded secret-like value detected; review secret handling and configuration boundaries.",
            1.0,
        ),
        PatternSpec(
            "shell_injection",
            _SHELL_INJECTION_PATTERN,
            "Possible shell execution path detected; review command construction and injection risk.",
            0.95,
        ),
        PatternSpec(
            "sql_injection",
            _DYNAMIC_SQL_PATTERN,
            "Dynamic SQL construction detected; review parameterization and injection risk.",
            0.95,
        ),
        PatternSpec(
            "dynamic_sql",
            _DYNAMIC_SQL_PATTERN,
            "Dynamic SQL construction detected; review parameterization and injection risk.",
            0.95,
        ),
    ),
    hinted_rules={
        "hardcoded_secret": ("SEC.1", "SEC.4", "SEC.7"),
        "shell_injection": ("SEC.2", "SEC.5"),
        "sql_injection": ("SEC.3",),
        "dynamic_sql": ("SEC.3", "SEC.6"),
    },
    direct_hint_patterns={
        "hardcoded_secret",
        "shell_injection",
        "sql_injection",
        "dynamic_sql",
    },
)
