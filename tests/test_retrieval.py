from __future__ import annotations

from app.ingest.build_records import ingest_all_sources
from app.retrieve.search import GuidelineSearchService


def test_retrieval_prefers_pattern_hint_rules(fixture_settings) -> None:
    ingest_all_sources(fixture_settings)
    service = GuidelineSearchService(fixture_settings)
    code = """
    #include <stdio.h>
    void bad() {
        int* ptr = new int(1);
        free(ptr);
        // wrong comment style
        for (int i = 0; i < 10; ++i) { continue; }
    }
    """

    response = service.review_code(code, top_k=6)
    returned_rules = [result.rule_no for result in response.results]

    assert "ALTI-MEM-007" in returned_rules
    assert "ALTI-COM-001" in returned_rules
    assert any(rule in returned_rules for rule in {"R.10", "R.11"})
