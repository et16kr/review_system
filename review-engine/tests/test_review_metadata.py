from __future__ import annotations

from types import SimpleNamespace

from review_engine.ingest.chroma_store import ChromaGuidelineStore
from review_engine.ingest.rule_loader import load_rule_runtime
from review_engine.models import CandidateHit, GuidelineRecord, PriorityPolicy, QueryAnalysis
from review_engine.retrieve.search import GuidelineSearchService


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


def test_search_service_results_keep_source_family_as_pack_id_alias(
    fixture_settings,
    monkeypatch,
) -> None:
    service = GuidelineSearchService(fixture_settings)
    candidate = CandidateHit(
        record=GuidelineRecord(
            rule_no="ORG.MEM.1",
            source="fixture",
            pack_id="org_cpp",
            source_kind="organization_policy",
            section="ORG",
            title="Use the organization owner wrapper",
            text="Prefer the owner wrapper over raw ownership.",
            summary="Organization owner wrapper guidance.",
        ),
        distance=0.1,
        similarity_score=0.9,
        final_score=0.88,
    )
    runtime = SimpleNamespace(
        language_id="cpp",
        policy=PriorityPolicy(policy_id="test-priority"),
        profile=SimpleNamespace(profile_id="default"),
        context_id=None,
        dialect_id=None,
        prompt_overlay_refs=[],
    )
    analysis = QueryAnalysis(input_kind="code", query_text="owner wrapper", patterns=[])

    monkeypatch.setattr(service, "_ensure_runtime_data", lambda language_id: None)
    monkeypatch.setattr(service.store, "query", lambda query_text, language_id, top_n: [candidate])
    monkeypatch.setattr(service, "_select_runtime_candidates", lambda candidates, runtime: candidates)
    monkeypatch.setattr(
        service,
        "_augment_with_pattern_hints",
        lambda candidates, analysis, language_id: candidates,
    )
    monkeypatch.setattr(
        "review_engine.retrieve.search.rerank_candidates",
        lambda candidates, analysis, settings, top_k, policy: candidates,
    )
    monkeypatch.setattr(
        "review_engine.retrieve.search.is_candidate_applicable",
        lambda candidate, analysis: True,
    )

    response = service._review_analysis(analysis, runtime=runtime, top_k=1)

    assert response.results[0].pack_id == "org_cpp"
    assert response.results[0].source_family == "org_cpp"
