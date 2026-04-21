from __future__ import annotations

from review_engine.ingest.build_records import ingest_all_sources
from review_engine.retrieve.search import GuidelineSearchService


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

    assert "R.10" in returned_rules
    assert "R.11" in returned_rules
    assert "R.12" in returned_rules


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


def test_retrieval_returns_no_results_for_clean_typed_code(fixture_settings) -> None:
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


def test_review_diff_file_context_does_not_change_detected_patterns_or_applicability(
    fixture_settings,
) -> None:
    ingest_all_sources(fixture_settings)
    service = GuidelineSearchService(fixture_settings)
    diff = "@@ -1 +1 @@\n-int x = 0;\n+int x = 1;\n"
    file_context = "IDE_RC rc;\nif (rc != IDE_SUCCESS) { return rc; }\n"

    without_context = service.review_diff(diff, top_k=8)
    with_context = service.review_diff(diff, top_k=8, file_context=file_context)

    assert with_context.detected_patterns == without_context.detected_patterns
    assert all(result.category != "error_handling" for result in with_context.results)
