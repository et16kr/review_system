from __future__ import annotations

import re

from app.models import QueryPattern
from app.text_utils import clean_text

IDE_RC_FLOW_SIGNAL_RE = re.compile(
    r"\b(?:IDE_RC\s+\w+\s*=|return\s+(?:IDE_[A-Z_]+|\w+)\s*;|IDE_ASSERT|goto\s+\w+\s*;|cleanup\b)"
)

PATTERN_SPECS = [
    (
        "raw_new",
        re.compile(r"\bnew\b"),
        "Possible raw owning pointer allocation with new; review ownership and RAII guidance.",
        1.0,
    ),
    (
        "malloc_free",
        re.compile(r"\b(?:malloc|calloc|realloc|free)\s*\("),
        "Manual C-style allocation or free detected; review Altibase memory rules "
        "and C++ resource management guidance.",
        1.0,
    ),
    (
        "manual_delete",
        re.compile(r"\bdelete(?:\s*\[\s*\])?\b"),
        "Explicit delete detected; review ownership, RAII, and explicit delete guidance.",
        0.95,
    ),
    (
        "manual_lock_unlock",
        re.compile(r"(?:\.|->)\s*(?:lock|unlock)\s*\("),
        "Manual lock or unlock call detected; review scoped lock and lifetime safety guidance.",
        0.9,
    ),
    (
        "ownership_ambiguity",
        re.compile(r"\b[A-Za-z_]\w*\s*\*\s+[A-Za-z_]\w+"),
        "Raw pointer usage may imply unclear ownership; review non-owning pointer "
        "and ownership rules.",
        0.8,
    ),
    (
        "return_move_local",
        re.compile(r"\breturn\s+std::move\s*\("),
        "Return of std::move(local) detected; review move misuse guidance.",
        0.7,
    ),
    (
        "line_comment",
        re.compile(r"//"),
        "Line comments detected; review internal comment-style policy.",
        0.8,
    ),
    (
        "identifier_underscore",
        re.compile(r"\b[A-Za-z]+[A-Za-z0-9]*_[A-Za-z0-9_]+\b"),
        "Identifiers containing underscores detected; review Altibase naming rules.",
        0.75,
    ),
    (
        "primitive_types",
        re.compile(r"\b(?:int|long|short|char|float|double|bool)\b"),
        "Primitive type usage detected; review Altibase typedef and portability rules.",
        0.8,
    ),
    (
        "direct_system_header",
        re.compile(
            r"#include\s*<(?:stdio\.h|stdlib\.h|string\.h|unistd\.h|pthread\.h|iostream|vector|memory|mutex)>"
        ),
        "Direct system or standard header include detected; review Altibase wrapper include rules.",
        0.95,
    ),
    (
        "direct_system_call",
        re.compile(r"\b(?:printf|malloc|free|exit|fopen|fclose|open|close)\s*\("),
        "Direct system library call detected; review Altibase wrapper and portability rules.",
        0.85,
    ),
    (
        "continue_usage",
        re.compile(r"\bcontinue\s*;"),
        "Continue statement detected; review Altibase control-flow rules.",
        0.82,
    ),
    (
        "switch_without_default",
        re.compile(r"\bswitch\s*\("),
        "Switch statement detected; confirm Altibase default-branch requirements.",
        0.65,
    ),
    (
        "for_initializer_declaration",
        re.compile(r"\bfor\s*\(\s*(?:const\s+)?(?:SInt|UInt|ULong|idBool|int|long|short|char)\s+\w+"),
        "Variable declaration inside for initializer detected; review Altibase control-flow rules.",
        0.8,
    ),
    (
        "primitive_format_specifier",
        re.compile(r"%(?:d|i|u|x|X|ld|lld|lu|llu|p|f|s)"),
        "Primitive format specifier detected; review Altibase ID_*_FMT portability rules.",
        0.78,
    ),
]

PATTERN_RULE_HINTS = {
    "raw_new": ["R.11", "R.12", "R.20", "R.3"],
    "malloc_free": ["R.10", "R.1", "ALTI-MEM-006", "ALTI-MEM-007"],
    "manual_delete": ["R.11", "R.12", "R.20", "R.3"],
    "manual_lock_unlock": ["R.1", "CP.20"],
    "ownership_ambiguity": ["R.3", "R.20", "R.30"],
    "return_move_local": ["F.48"],
    "line_comment": ["ALTI-COM-001"],
    "identifier_underscore": ["ALTI-NAE-009", "ALTI-NAE-010"],
    "primitive_types": ["ALTI-TYC-001"],
    "direct_system_header": ["ALTI-PRE-004", "ALTI-PRE-002", "ALTI-PCM-002"],
    "direct_system_call": ["ALTI-PCM-002"],
    "continue_usage": ["ALTI-COF-001"],
    "switch_without_default": ["ALTI-COF-002"],
    "for_initializer_declaration": ["ALTI-COF-006"],
    "primitive_format_specifier": ["ALTI-PCM-005", "ALTI-DCL-008"],
    "free_without_null_reset": ["ALTI-MEM-007"],
    "ide_rc_flow": ["Rule-R1", "Rule-R2", "Rule-R3", "ALTI-ERR-001", "ALTI-ERR-002"],
}

DIRECT_HINT_PATTERNS = {
    "raw_new",
    "malloc_free",
    "manual_delete",
    "manual_lock_unlock",
    "line_comment",
    "primitive_types",
    "direct_system_header",
    "direct_system_call",
    "continue_usage",
    "switch_without_default",
    "for_initializer_declaration",
    "primitive_format_specifier",
    "free_without_null_reset",
}


def extract_query_patterns(source_text: str) -> list[QueryPattern]:
    patterns: list[QueryPattern] = []
    lines = source_text.splitlines()
    has_default = "default:" in source_text
    has_null_reset = "= NULL" in source_text or "= nullptr" in source_text
    has_ide_rc = "IDE_RC" in source_text
    has_ide_test = "IDE_TEST" in source_text or "IDE_TEST_RAISE" in source_text
    has_ide_exception = "IDE_EXCEPTION" in source_text
    has_ide_rc_flow_signal = IDE_RC_FLOW_SIGNAL_RE.search(source_text) is not None

    for name, regex, description, weight in PATTERN_SPECS:
        if name == "switch_without_default":
            if regex.search(source_text) and not has_default:
                patterns.append(QueryPattern(name=name, description=description, weight=weight))
            continue
        if name == "malloc_free":
            if regex.search(source_text):
                evidence = _matching_lines(lines, regex)
                patterns.append(
                    QueryPattern(
                        name=name,
                        description=description,
                        weight=weight,
                        evidence=evidence,
                    )
                )
                if "free(" in source_text and not has_null_reset:
                    patterns.append(
                        QueryPattern(
                            name="free_without_null_reset",
                            description="free() detected without an immediate NULL reset; "
                            "review Altibase memory rules.",
                            weight=0.9,
                        )
                    )
            continue

        if regex.search(source_text):
            evidence = _matching_lines(lines, regex)
            patterns.append(
                QueryPattern(
                    name=name,
                    description=description,
                    weight=weight,
                    evidence=evidence,
                )
            )

    if has_ide_rc and has_ide_rc_flow_signal and not (has_ide_test or has_ide_exception):
        patterns.append(
            QueryPattern(
                name="ide_rc_flow",
                description="IDE_RC return pattern detected without matching IDE_TEST "
                "or IDE_EXCEPTION flow handling.",
                weight=0.85,
                evidence=_matching_lines(lines, IDE_RC_FLOW_SIGNAL_RE),
            )
        )

    return _deduplicate_patterns(patterns)


def collect_hinted_rules(patterns: list[QueryPattern], *, direct_only: bool = False) -> set[str]:
    hinted_rules: set[str] = set()
    for pattern in patterns:
        if direct_only and pattern.name not in DIRECT_HINT_PATTERNS:
            continue
        hinted_rules.update(PATTERN_RULE_HINTS.get(pattern.name, []))
    return hinted_rules


def _matching_lines(lines: list[str], regex: re.Pattern[str]) -> list[str]:
    snippets: list[str] = []
    for line in lines:
        if regex.search(line):
            snippets.append(clean_text(line))
        if len(snippets) >= 3:
            break
    return snippets


def _deduplicate_patterns(patterns: list[QueryPattern]) -> list[QueryPattern]:
    deduped: dict[str, QueryPattern] = {}
    for pattern in patterns:
        existing = deduped.get(pattern.name)
        if existing is None or pattern.weight > existing.weight:
            deduped[pattern.name] = pattern
    return list(deduped.values())
