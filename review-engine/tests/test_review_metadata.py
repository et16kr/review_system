from __future__ import annotations

from app.ingest.build_records import build_guideline_records
from app.ingest.chroma_store import ChromaGuidelineStore
from app.models import GuidelineRecord, ParsedRule


def test_build_guideline_records_assigns_operational_metadata(fixture_settings) -> None:
    records = build_guideline_records(
        [
            ParsedRule(
                rule_no="ALTI-MEM-007",
                source="fixture",
                source_family="altibase",
                section="ALTI-MEM",
                title="Free memory explicitly",
                text="Free memory explicitly and avoid leaked ownership.",
                summary="Free memory explicitly",
                keywords=["malloc", "free", "ownership"],
            ),
            ParsedRule(
                rule_no="T.1",
                source="fixture",
                source_family="cpp_core",
                section="T",
                title="Use templates carefully",
                text="General template guidance.",
                summary="Use templates carefully",
                keywords=["template", "generic"],
            ),
        ],
        fixture_settings,
    )
    by_rule = {record.rule_no: record for record in records}

    assert by_rule["ALTI-MEM-007"].reviewability == "auto_review"
    assert by_rule["ALTI-MEM-007"].category == "memory"
    assert "malloc_free" in by_rule["ALTI-MEM-007"].trigger_patterns
    assert by_rule["T.1"].reviewability == "reference_only"


def test_chroma_store_queries_only_active_collection(fixture_settings) -> None:
    store = ChromaGuidelineStore(fixture_settings)
    active = [
        GuidelineRecord(
            id="altibase:ALTI-MEM-007",
            rule_no="ALTI-MEM-007",
            source="fixture",
            source_family="altibase",
            section="ALTI-MEM",
            title="Memory rule",
            text="Avoid malloc/free pairs.",
            summary="Avoid malloc/free pairs.",
            keywords=["malloc", "free"],
            authority="internal",
            priority=0.95,
            severity_default=0.95,
            conflict_policy="authoritative",
            embedding_text="malloc free memory",
            reviewability="auto_review",
            category="memory",
            trigger_patterns=["malloc_free"],
            fix_guidance="Use RAII.",
            review_rank_default=0.95,
        )
    ]
    reference = [
        GuidelineRecord(
            id="cpp_core:T.1",
            rule_no="T.1",
            source="fixture",
            source_family="cpp_core",
            section="T",
            title="Template rule",
            text="Template design advice.",
            summary="Template design advice.",
            keywords=["template"],
            authority="external",
            priority=0.4,
            severity_default=0.4,
            conflict_policy="compatible",
            embedding_text="template generic",
            reviewability="reference_only",
            category="general",
            review_rank_default=0.4,
        )
    ]
    store.rebuild(active_records=active, reference_records=reference, excluded_records=[])

    results = store.query("malloc free", top_n=5)
    assert [result.record.rule_no for result in results] == ["ALTI-MEM-007"]
