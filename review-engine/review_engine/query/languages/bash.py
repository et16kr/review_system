from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="bash",
    display_name="Bash",
    default_focus="quoting, shell options, command safety, and destructive glob expansion",
    pattern_specs=(
        PatternSpec(
            "set_e_missing",
            r"(?s)\A(?!.*set\s+-[^\n]*e)(?!.*set\s+-[^\n]*u)(?!.*pipefail).*",
            "Shell options are not obviously strict; review whether the script should fail fast and treat unset vars safely.",
            0.7,
        ),
        PatternSpec(
            "unquoted_variable",
            r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?",
            "Variable expansion detected; review whether word-splitting or globbing should be quoted explicitly.",
            0.7,
        ),
        PatternSpec(
            "curl_pipe_shell",
            r"curl\b.*\|\s*(?:bash|sh)\b",
            "curl piped to shell detected; review trust boundaries and safer installation flow.",
            1.0,
        ),
        PatternSpec(
            "rm_rf_glob",
            r"rm\s+-rf\s+[^#\n]+",
            "Recursive delete detected; review quoting, path validation, and accidental expansion risk.",
            0.95,
        ),
        PatternSpec(
            "sudo_usage",
            r"\bsudo\b",
            "sudo usage detected; review privilege boundaries and whether checked-in automation should depend on interactive escalation.",
            0.86,
        ),
        PatternSpec(
            "curl_insecure",
            r"curl\b[^\n]*(?:--insecure|-k)\b",
            "curl TLS verification bypass detected; review transport trust assumptions and safer artifact verification.",
            0.98,
        ),
    ),
    hinted_rules={
        "set_e_missing": ("BASH.SAFE.1", "BASH.SAFE.3"),
        "unquoted_variable": ("BASH.1", "BASH.3", "BASH.7"),
        "curl_pipe_shell": ("BASH.SAFE.2", "BASH.SAFE.4"),
        "rm_rf_glob": ("BASH.2", "BASH.4"),
        "sudo_usage": ("BASH.5", "BASH.SAFE.6"),
        "curl_insecure": ("BASH.SAFE.5",),
    },
    direct_hint_patterns={
        "set_e_missing",
        "unquoted_variable",
        "curl_pipe_shell",
        "rm_rf_glob",
        "sudo_usage",
        "curl_insecure",
    },
)
