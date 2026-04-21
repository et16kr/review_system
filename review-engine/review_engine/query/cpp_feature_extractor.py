from __future__ import annotations

import re

from review_engine.models import QueryPattern
from review_engine.text_utils import clean_text

FOR_INITIALIZER_DECL_RE = re.compile(
    r"\bfor\s*\(\s*"
    r"(?:const\s+)?"
    r"(?:"
    r"auto|bool|char|short|int|long|float|double|"
    r"unsigned(?:\s+(?:char|short|int|long))?|"
    r"signed(?:\s+(?:char|short|int|long))?|"
    r"[A-Za-z_]\w*(?:::\w+)*(?:<[^;(){}]+>)?"
    r")"
    r"\s*(?:[*&]\s*)?\w+\s*(?:=|\{|\()"
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
        "Manual C-style allocation or free detected; review C++ resource management guidance.",
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
        "Line comments detected; review applicable public comment and readability guidance.",
        0.8,
    ),
    (
        "identifier_underscore",
        re.compile(r"\b[A-Za-z]+[A-Za-z0-9]*_[A-Za-z0-9_]+\b"),
        "Identifiers containing underscores detected; review applicable naming and readability guidance.",
        0.75,
    ),
    (
        "primitive_types",
        re.compile(r"\b(?:int|long|short|char|float|double|bool)\b"),
        "Primitive type usage detected; review strong typing and portability guidance.",
        0.8,
    ),
    (
        "direct_system_header",
        re.compile(
            r"#include\s*<(?:stdio\.h|stdlib\.h|string\.h|unistd\.h|pthread\.h|iostream|vector|memory|mutex)>"
        ),
        "Direct system or standard header include detected; review portability and include guidance.",
        0.95,
    ),
    (
        "direct_system_call",
        re.compile(r"\b(?:printf|malloc|free|exit|fopen|fclose|open|close)\s*\("),
        "Direct system library call detected; review encapsulation, portability, and safer interface guidance.",
        0.85,
    ),
    (
        "continue_usage",
        re.compile(r"\bcontinue\s*;"),
        "Continue statement detected; review public control-flow guidance.",
        0.82,
    ),
    (
        "switch_without_default",
        re.compile(r"\bswitch\s*\("),
        "Switch statement detected without an obvious default path; review public switch guidance.",
        0.65,
    ),
    (
        "for_initializer_declaration",
        FOR_INITIALIZER_DECL_RE,
        "Variable declaration inside for initializer detected; capture loop-scoping context for public guidance.",
        0.8,
    ),
    (
        "primitive_format_specifier",
        re.compile(r"%(?:d|i|u|x|X|ld|lld|lu|llu|p|f|s)"),
        "Primitive format specifier detected; review safer formatting and I/O guidance.",
        0.78,
    ),
]

PATTERN_RULE_HINTS = {
    "raw_new": ["R.11", "R.12", "R.20", "I.11"],
    "malloc_free": ["R.10", "R.12", "R.1", "P.8", "E.19"],
    "manual_delete": ["R.11", "R.12", "R.20", "I.11"],
    "manual_lock_unlock": ["R.1", "CP.20"],
    "ownership_ambiguity": ["I.11", "R.20", "R.11"],
    "return_move_local": ["F.48"],
    "line_comment": [],
    "identifier_underscore": [],
    "primitive_types": ["I.4"],
    "direct_system_header": ["SF.13", "P.11"],
    "direct_system_call": ["SL.io.3", "P.11", "E.19"],
    "continue_usage": ["ES.77"],
    "switch_without_default": ["ES.78", "ES.79"],
    "for_initializer_declaration": [],
    "primitive_format_specifier": ["SL.io.3", "ES.34"],
    "free_without_null_reset": ["R.10", "E.19"],
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
                            description="free() detected without an immediate reset or ownership handoff; review memory guidance.",
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
