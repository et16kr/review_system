from __future__ import annotations

from review_engine.ingest.chroma_store import ChromaGuidelineStore
from review_engine.ingest.rule_loader import load_rule_runtime
from review_engine.models import GuidelineRecord


def test_runtime_records_expose_operational_metadata(fixture_settings) -> None:
    runtime = load_rule_runtime(fixture_settings)
    by_rule = {
        record.rule_no: record
        for record in [*runtime.active_records, *runtime.reference_records]
    }

    assert by_rule["R.10"].reviewability == "auto_review"
    assert by_rule["R.10"].category == "memory"
    assert "malloc_free" in by_rule["R.10"].trigger_patterns
    assert by_rule["CPP.PROJ.7"].reviewability == "reference_only"


def test_chroma_store_queries_only_active_collection(fixture_settings) -> None:
    store = ChromaGuidelineStore(fixture_settings)
    active = [
        GuidelineRecord(
            id="cpp_core:R.10",
            rule_no="R.10",
            source="fixture",
            pack_id="cpp_core",
            source_kind="public_standard",
            namespace="public",
            source_family="cpp_core",
            section="R",
            title="Memory rule",
            text="Avoid malloc/free pairs.",
            summary="Avoid malloc/free pairs.",
            keywords=["malloc", "free"],
            authority="external",
            priority=0.95,
            severity_default=0.95,
            conflict_policy="compatible",
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
            id="project_cpp:CPP.PROJ.7",
            rule_no="CPP.PROJ.7",
            source="fixture",
            pack_id="project_cpp",
            source_kind="project_policy",
            namespace="project",
            source_family="project_cpp",
            section="CPP",
            title="API contract rule",
            text="Prefer span-like carrier types at pointer plus size boundaries.",
            summary="Prefer span-like carrier types.",
            keywords=["span", "pointer", "size"],
            authority="external",
            priority=0.4,
            severity_default=0.4,
            conflict_policy="compatible",
            embedding_text="pointer size span",
            reviewability="reference_only",
            category="general",
            review_rank_default=0.4,
        )
    ]
    store.rebuild(active_records=active, reference_records=reference, excluded_records=[])

    results = store.query("malloc free", top_n=5)
    assert [result.record.rule_no for result in results] == ["R.10"]
