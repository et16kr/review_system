from __future__ import annotations

from review_engine.models import QueryPattern
from review_engine.query.languages.cpp import PLUGIN


def extract_query_patterns(source_text: str) -> list[QueryPattern]:
    return PLUGIN.analyze(source_text)


def collect_hinted_rules(patterns: list[QueryPattern], *, direct_only: bool = False) -> set[str]:
    return PLUGIN.collect_hinted_rules(patterns, direct_only=direct_only)
