from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="python",
    display_name="Python",
    default_focus="exception handling, context managers, typing discipline, and API clarity",
    pattern_specs=(
        PatternSpec(
            "mutable_default",
            r"def\s+\w+\s*\([^)]*=\s*(?:\[\]|\{\})",
            "Mutable default argument detected; review shared state leakage across calls.",
            1.0,
        ),
        PatternSpec(
            "bare_except",
            r"except\s*:",
            "Bare except block detected; review exception taxonomy and error visibility.",
            0.95,
        ),
        PatternSpec(
            "subprocess_shell_true",
            r"subprocess\.\w+\([^)]*shell\s*=\s*True",
            "subprocess shell=True detected; review command injection and escaping.",
            0.95,
        ),
        PatternSpec(
            "open_without_context",
            r"(?m)^\s*\w+\s*=\s*open\(",
            "open() assignment detected; review whether file lifetime should be bound to a context manager.",
            0.82,
        ),
        PatternSpec(
            "eval_exec",
            r"\b(?:eval|exec)\s*\(",
            "Dynamic code execution detected; review trust boundaries and safer parsing strategies.",
            0.98,
        ),
        PatternSpec(
            "except_exception",
            r"except\s+Exception(?:\s+as\s+\w+)?\s*:",
            "Broad Exception catch detected; review whether the handler is masking programmer or cancellation failures.",
            0.84,
        ),
        PatternSpec(
            "assert_usage",
            r"(?m)^\s*assert\s+",
            "assert statement detected; review whether runtime validation or external input handling depends on debug-only checks.",
            0.82,
        ),
        PatternSpec(
            "yaml_unsafe_load",
            r"yaml\.load\s*\(",
            "yaml.load detected; review trusted-input assumptions and whether safe_load should be used instead.",
            0.97,
        ),
    ),
    hinted_rules={
        "mutable_default": ("PY.1", "PY.4"),
        "bare_except": ("PY.2", "PY.3"),
        "subprocess_shell_true": ("PY.PROJ.2", "PY.PROJ.4"),
        "open_without_context": ("PY.PROJ.1", "PY.PROJ.3"),
        "eval_exec": ("PY.PROJ.2", "PY.PROJ.5"),
        "except_exception": ("PY.5",),
        "assert_usage": ("PY.PROJ.6",),
        "yaml_unsafe_load": ("PY.PROJ.7",),
    },
    direct_hint_patterns={
        "mutable_default",
        "bare_except",
        "subprocess_shell_true",
        "open_without_context",
        "eval_exec",
        "except_exception",
        "assert_usage",
        "yaml_unsafe_load",
    },
)
