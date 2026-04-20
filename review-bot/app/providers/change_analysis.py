from __future__ import annotations

import re
from dataclasses import dataclass

NUMBERED_CHANGE_LINE_RE = re.compile(
    r"^(?:(?:L(?P<new>\d+))|(?:OLD(?P<old>\d+))) \| (?P<marker>[+-]) (?P<text>.*)$"
)
RAW_DIFF_LINE_RE = re.compile(r"^(?P<marker>[+-])(?![+-])(?P<text>.*)$")
IDE_RC_FLOW_SIGNAL_RE = re.compile(
    r"\b(?:IDE_RC\s+\w+\s*=|IDE_SET\s*\(|goto\s+\w+\s*;|cleanup\b)"
)
IDE_EXCEPTION_FLOW_SIGNAL_RE = re.compile(r"\b(?:IDE_TEST_RAISE|IDE_EXCEPTION|IDE_TEST\s*\()")
DIRECT_LIBC_OR_FORMAT_RE = re.compile(
    r"(?<![:\w])(?:strcpy|strncpy|memcpy|sprintf|snprintf|printf)\s*\("
)
ISSUE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "malloc_free": ("malloc(", "free("),
    "raw_new_delete": ("new ", "delete ", "delete["),
    "continue_usage": ("continue;",),
    "switch_without_default": ("switch",),
    "ide_assert": ("ide_assert",),
    "ide_rc_flow": ("ide_rc ", "="),
    "ide_exception_flow": ("ide_test_raise", "ide_exception", "ide_test("),
    "direct_libc_or_format": ("printf(",),
    "portability": ("#include <", "unistd.h", "windows.h", "pthread_"),
}

ISSUE_PRIORITY_KEYWORDS: dict[str, tuple[tuple[str, ...], ...]] = {
    "ide_rc_flow": (
        ("return ide_",),
        ("ide_test_raise", "ide_test(", "ide_exception", "ide_set("),
        ("goto ", "cleanup"),
        ("ide_rc ", "="),
    ),
    "ide_exception_flow": (
        ("ide_test_raise",),
        ("ide_exception",),
        ("ide_test(",),
    ),
}


@dataclass(frozen=True)
class SnippetLine:
    marker: str
    text: str
    new_line_no: int | None = None
    old_line_no: int | None = None


def parse_numbered_change_snippet(change_snippet: str) -> list[SnippetLine]:
    lines: list[SnippetLine] = []
    for raw_line in change_snippet.splitlines():
        stripped = raw_line.strip()
        match = NUMBERED_CHANGE_LINE_RE.match(stripped)
        if match is not None:
            lines.append(
                SnippetLine(
                    marker=match.group("marker"),
                    text=match.group("text"),
                    new_line_no=int(match.group("new")) if match.group("new") else None,
                    old_line_no=int(match.group("old")) if match.group("old") else None,
                )
            )
            continue

        raw_match = RAW_DIFF_LINE_RE.match(stripped)
        if raw_match is not None:
            lines.append(
                SnippetLine(
                    marker=raw_match.group("marker"),
                    text=raw_match.group("text"),
                )
            )
    return lines


def extract_changed_excerpt(change_snippet: str) -> str:
    return "\n".join(line.text for line in parse_numbered_change_snippet(change_snippet)).strip()


def classify_issue(
    excerpt: str,
    category: str | None,
    title: str,
    summary: str,
) -> str:
    excerpt_lower = excerpt.lower()
    if "malloc(" in excerpt_lower or "free(" in excerpt_lower:
        return "malloc_free"
    if "new " in excerpt_lower or "delete " in excerpt_lower or "delete[" in excerpt_lower:
        return "raw_new_delete"
    if "continue;" in excerpt_lower:
        return "continue_usage"
    if "switch" in excerpt_lower and "default" not in excerpt_lower:
        return "switch_without_default"
    if "ide_assert" in excerpt_lower:
        return "ide_assert"
    if "ide_rc" in excerpt_lower and IDE_RC_FLOW_SIGNAL_RE.search(excerpt):
        return "ide_rc_flow"
    if IDE_EXCEPTION_FLOW_SIGNAL_RE.search(excerpt):
        return "ide_exception_flow"
    if DIRECT_LIBC_OR_FORMAT_RE.search(excerpt):
        return "direct_libc_or_format"
    portability_tokens = ["#include <", "unistd.h", "windows.h", "pthread_"]
    if any(token in excerpt_lower for token in portability_tokens):
        return "portability"
    if category == "memory":
        return "memory_generic"
    if category == "control_flow":
        return "control_flow_generic"
    if category == "error_handling":
        return "error_handling_generic"
    if category == "wrapper_usage":
        return "wrapper_usage_generic"
    if category == "format_usage":
        return "format_usage_generic"
    return "generic"


def select_candidate_line(
    *,
    change_snippet: str,
    candidate_line_nos: tuple[int, ...],
    issue: str,
) -> int | None:
    if not candidate_line_nos:
        return None

    snippet_lines = parse_numbered_change_snippet(change_snippet)
    prioritized = _prioritized_new_lines(snippet_lines)
    if not prioritized:
        return candidate_line_nos[0]

    priority_keywords = ISSUE_PRIORITY_KEYWORDS.get(issue)
    if priority_keywords:
        for keyword_group in priority_keywords:
            for line in prioritized:
                text = line.text.lower()
                if all(keyword in text for keyword in keyword_group):
                    return line.new_line_no
        return None

    if issue == "direct_libc_or_format":
        for line in prioritized:
            if DIRECT_LIBC_OR_FORMAT_RE.search(line.text):
                return line.new_line_no
        return None

    keywords = ISSUE_KEYWORDS.get(issue)
    if keywords:
        for line in prioritized:
            text = line.text.lower()
            if any(keyword in text for keyword in keywords):
                return line.new_line_no
        return None

    return prioritized[0].new_line_no


def requires_direct_signal(issue: str) -> bool:
    return issue in ISSUE_KEYWORDS


def _prioritized_new_lines(lines: list[SnippetLine]) -> list[SnippetLine]:
    added = [line for line in lines if line.marker == "+" and line.new_line_no is not None]
    if added:
        return added
    return [line for line in lines if line.new_line_no is not None]
