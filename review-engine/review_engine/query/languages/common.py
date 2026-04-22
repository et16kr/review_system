from __future__ import annotations

from review_engine.models import QueryPattern
from review_engine.text_utils import clean_text


def matching_lines(source_text: str, pattern) -> list[str]:
    snippets: list[str] = []
    for line in source_text.splitlines():
        if pattern.search(line):
            snippets.append(clean_text(line))
        if len(snippets) >= 3:
            break
    return snippets


def deduplicate_patterns(patterns: list[QueryPattern]) -> list[QueryPattern]:
    deduped: dict[str, QueryPattern] = {}
    for pattern in patterns:
        existing = deduped.get(pattern.name)
        if existing is None or pattern.weight > existing.weight:
            deduped[pattern.name] = pattern
    return list(deduped.values())
