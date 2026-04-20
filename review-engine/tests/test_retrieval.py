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


def test_retrieval_does_not_force_rule_r_for_ide_rc_declaration_only(fixture_settings) -> None:
    ingest_all_sources(fixture_settings)
    service = GuidelineSearchService(fixture_settings)
    code = """
    class idsTde {
    public:
        static IDE_RC createKeyStore(const SChar* aKeyStorePath,
                                     const SChar* aWrapKeyPath,
                                     idsTdeResult* aResult);
    };
    """

    response = service.review_code(code, top_k=8)
    returned_rules = [result.rule_no for result in response.results]

    assert returned_rules == []
    assert "Rule-R1" not in returned_rules
    assert "Rule-R2" not in returned_rules
    assert "Rule-R3" not in returned_rules


def test_retrieval_returns_no_results_for_clean_altibase_typed_code(fixture_settings) -> None:
    ingest_all_sources(fixture_settings)
    service = GuidelineSearchService(fixture_settings)
    code = """
    SInt addValues(SInt leftValue, SInt rightValue)
    {
        return leftValue + rightValue;
    }
    """

    response = service.review_code(code, top_k=8)

    assert response.results == []


def test_retrieval_keeps_ide_test_raise_guidance_out_of_auto_review(fixture_settings) -> None:
    ingest_all_sources(fixture_settings)
    service = GuidelineSearchService(fixture_settings)
    code = """
    IDE_TEST_RAISE( sParseTree->TBSAttr == NULL, ERR_INVALID_PARSE_TREE );
    """

    response = service.review_code(code, top_k=8)

    assert response.results == []
