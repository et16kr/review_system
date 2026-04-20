from __future__ import annotations

import re
from collections.abc import Iterable

from review_engine.models import ParsedRule
from review_engine.text_utils import clean_text, extract_keywords, summarize_text

SECTION_HEADING_RE = re.compile(r"^##\s+(.+)$")
RULE_CATEGORY_RE = re.compile(r"^###\s+(.+)$")
RULE_BULLET_RE = re.compile(
    r"^- (?:(?:`(?P<backticked>[^`]+)`)|(?P<plain>Rule-R\d+))(?: \([^)]*\))?: (?P<title>.+)$"
)
PAGE_SUFFIX_RE = re.compile(r"\s+\(p\.[^)]+\)$")

CATEGORY_CONTEXT_HINTS = {
    "Naming and prefixes": ["Root prefixes", "Naming rules"],
    "Formatting and layout": ["File and layout rules"],
    "Comments": ["Comments"],
    "Declarations and function design": ["Types, declarations, and expressions"],
    "Types and casts": ["Types, declarations, and expressions"],
    "C string and storage rules": ["Types, declarations, and expressions", "Memory rules"],
    "Preprocessor": ["Preprocessor and portability rules"],
    "Operators and expressions": ["Types, declarations, and expressions"],
    "Control flow": ["Control flow rules"],
    "Memory": ["Memory rules"],
    "Pointers and object lifetime": ["Memory rules"],
    "Portability and compatibility": ["Preprocessor and portability rules"],
    "Altibase error macros": ["Altibase-specific error handling conventions"],
    "Error handling conventions": ["Altibase-specific error handling conventions"],
    "Error code and message rules": ["Error code naming and message rules"],
}


def parse_internal_convention(markdown_text: str, source: str) -> list[ParsedRule]:
    narrative_sections = _collect_narrative_sections(markdown_text)
    records: list[ParsedRule] = []

    current_category = ""
    for line in _iter_rule_index_lines(markdown_text):
        category_match = RULE_CATEGORY_RE.match(line)
        if category_match:
            current_category = _normalize_category(category_match.group(1).strip())
            continue

        rule_match = RULE_BULLET_RE.match(line)
        if not rule_match:
            continue

        rule_no = rule_match.group("backticked") or rule_match.group("plain")
        title = clean_text(rule_match.group("title").rstrip("."))
        context = _build_context(current_category, narrative_sections)
        text = clean_text(f"{title} {context}")
        section = _derive_section(rule_no, current_category)
        keyword_basis = f"{current_category} {rule_no} {title} {context}"
        records.append(
            ParsedRule(
                rule_no=rule_no,
                source=source,
                source_family="altibase",
                section=section,
                title=title,
                text=text,
                summary=title,
                keywords=extract_keywords(keyword_basis),
            )
        )

    return records


def _iter_rule_index_lines(markdown_text: str) -> Iterable[str]:
    lines = markdown_text.splitlines()
    in_rule_index = False
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if line.startswith("## Rule index"):
            in_rule_index = True
            index += 1
            continue
        if not in_rule_index:
            index += 1
            continue
        if line.startswith("### "):
            yield line
            index += 1
            continue
        if line.startswith("- "):
            item_lines = [line]
            index += 1
            while index < len(lines):
                continuation = lines[index].rstrip()
                if not continuation:
                    break
                if continuation.startswith(("### ", "- ", "## ")):
                    break
                item_lines.append(continuation.strip())
                index += 1
            yield clean_text(" ".join(item_lines))
            continue
        index += 1


def _collect_narrative_sections(markdown_text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading = "Intro"
    in_rule_index = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## Rule index"):
            in_rule_index = True
        if in_rule_index:
            continue
        heading_match = SECTION_HEADING_RE.match(line)
        if heading_match:
            current_heading = heading_match.group(1).strip()
            sections.setdefault(current_heading, [])
            continue
        if line:
            sections.setdefault(current_heading, []).append(line)

    return {
        heading: clean_text(" ".join(lines))
        for heading, lines in sections.items()
        if clean_text(" ".join(lines))
    }


def _build_context(category: str, narrative_sections: dict[str, str]) -> str:
    hints = CATEGORY_CONTEXT_HINTS.get(category, [])
    chunks = [narrative_sections[hint] for hint in hints if hint in narrative_sections]
    if not chunks:
        chunks = list(_fallback_sections(category, narrative_sections))
    return summarize_text(" ".join(chunks[:2]), max_sentences=3, max_chars=420)


def _fallback_sections(category: str, narrative_sections: dict[str, str]) -> Iterable[str]:
    lowered_category = category.lower()
    for heading, text in narrative_sections.items():
        if any(token in heading.lower() for token in lowered_category.split()):
            yield text


def _derive_section(rule_no: str, category: str) -> str:
    if rule_no.startswith("ALTI-"):
        parts = rule_no.split("-")
        return "-".join(parts[:2])
    if rule_no.startswith("Rule-R"):
        return "Rule-R"
    return category


def _normalize_category(category: str) -> str:
    return PAGE_SUFFIX_RE.sub("", category).strip()
