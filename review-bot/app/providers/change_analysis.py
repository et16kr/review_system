from __future__ import annotations

import re
from dataclasses import dataclass

NUMBERED_CHANGE_LINE_RE = re.compile(
    r"^(?:(?:L(?P<new>\d+))|(?:OLD(?P<old>\d+))) \| (?P<marker>[+-]) (?P<text>.*)$"
)
RAW_DIFF_LINE_RE = re.compile(r"^(?P<marker>[+-])(?![+-])(?P<text>.*)$")
ISSUE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "malloc_free": ("malloc(", "free("),
    "raw_new_delete": ("new ", "delete ", "delete["),
    "continue_usage": ("continue;",),
    "switch_without_default": ("switch",),
    "ide_assert": ("ide_assert",),
    "ide_rc_flow": ("ide_rc", "return ide_"),
    "ide_exception_flow": ("ide_test_raise", "ide_exception"),
    "direct_libc_or_format": ("strcpy(", "strncpy(", "memcpy(", "sprintf(", "printf("),
    "portability": ("#include <", "unistd.h", "windows.h", "pthread_"),
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
    combined = "\n".join(
        part for part in [excerpt, category or "", title or "", summary or ""] if part
    ).lower()
    if "malloc(" in combined or "free(" in combined:
        return "malloc_free"
    if "new " in combined or "delete " in combined or "delete[" in combined:
        return "raw_new_delete"
    if "continue;" in combined:
        return "continue_usage"
    if "switch" in combined and "default" not in combined:
        return "switch_without_default"
    if "ide_assert" in combined:
        return "ide_assert"
    if "ide_rc" in combined or "return ide_" in combined:
        return "ide_rc_flow"
    if "ide_test_raise" in combined or "ide_exception" in combined:
        return "ide_exception_flow"
    libc_tokens = [
        "strcpy(",
        "strncpy(",
        "memcpy(",
        "sprintf(",
        "printf(",
    ]
    if any(token in combined for token in libc_tokens):
        return "direct_libc_or_format"
    portability_tokens = ["#include <", "unistd.h", "windows.h", "pthread_"]
    if any(token in combined for token in portability_tokens):
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
