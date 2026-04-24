from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from textwrap import dedent

import pytest

from review_engine.ingest.build_records import ingest_all_sources
from review_engine.ingest.rule_loader import load_rule_runtime
from review_engine.models import CandidateHit, GuidelineRecord, PriorityPolicy, QueryAnalysis, QueryPattern
from review_engine.prompting import PromptComposer
from review_engine.retrieve.rerank import rerank_candidates


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).strip() + "\n", encoding="utf-8")


def _build_extension_root(tmp_path: Path) -> Path:
    root = tmp_path / "org-extension"
    _write(
        root / "manifest.yaml",
        """
        schema_version: 1
        language_id: cpp
        pack_files:
          - packs/org_cpp.yaml
        profile_files:
          - profiles/default.yaml
        policy_files:
          - policies/org_default.yaml
        """,
    )
    _write(
        root / "packs" / "org_cpp.yaml",
        """
        schema_version: 1
        pack_id: org_cpp
        namespace: organization
        language_id: cpp
        source_kind: organization_policy
        description: Organization extension pack used by tests.
        default_enabled: true
        default_priority_tier: override
        entries:
          - rule_no: ORG.MEM.1
            section: ORG
            title: Prefer explicit owner abstractions over raw owning pointers
            summary: Ownership must stay explicit in project-specific wrappers.
            text: Organization rule that replaces direct raw ownership guidance with a project-specific owner wrapper.
            category: memory
            trigger_patterns: [raw_new, manual_delete, ownership_ambiguity]
            fix_guidance: Wrap dynamic ownership in the project owner type instead of a raw pointer.
            base_score: 0.97
            severity_default: 0.98
            priority_tier: override
            specificity: 0.99
            false_positive_risk: low
        """,
    )
    _write(
        root / "profiles" / "default.yaml",
        """
        schema_version: 1
        profile_id: default
        language_id: cpp
        enabled_packs:
          - org_cpp
        shared_packs: []
        prompt_overlay_refs:
          - org
        detector_refs: []
        priority_policy_ref: org_default
        """,
    )
    _write(
        root / "policies" / "org_default.yaml",
        """
        schema_version: 1
        policy_id: org_default
        language_id: cpp
        pack_weights:
          cpp_core: 0.72
          org_cpp: 0.97
        overrides:
          - match:
              rule_no: R.11
            action: overridden
            overridden_by:
              - org_cpp:ORG.MEM.1
            rationale: Organization owner wrapper rule replaces the public raw-new guidance.
        exclusions:
          - match:
              rule_no: ES.6
            rationale: This profile excludes the for-initializer style preference.
        """,
    )
    return root


def test_public_ingest_uses_canonical_yaml_rule_root(fixture_settings) -> None:
    summary = ingest_all_sources(fixture_settings)

    assert summary.total_parsed >= summary.cpp_core_records
    assert summary.active_records > 0
    assert Path(summary.active_dataset_path).exists()
    assert summary.public_rule_root.endswith("/rules")
    assert "cpp" in summary.languages
    assert "python" in summary.languages


def test_extension_rule_root_can_override_and_exclude_public_rules(
    fixture_settings,
    tmp_path,
) -> None:
    extension_root = _build_extension_root(tmp_path)
    settings = replace(fixture_settings, extension_rule_roots=(extension_root,))

    runtime = load_rule_runtime(settings)

    active_rules = {record.rule_no for record in runtime.active_records}
    excluded_rules = {record.rule_no for record in runtime.excluded_records}

    assert "ORG.MEM.1" in active_rules
    assert "R.11" in excluded_rules
    assert "ES.6" in excluded_rules
    assert runtime.extension_rule_roots == [str(extension_root.resolve())]
    assert runtime.prompt_overlay_refs == ["org"]


def test_extension_entry_point_loading_matches_filesystem_loading(
    fixture_settings,
    tmp_path,
    monkeypatch,
) -> None:
    extension_root = _build_extension_root(tmp_path)

    class FakeEntryPoint:
        name = "org-extension"

        def load(self):
            return lambda: {"name": "org-extension", "rule_roots": [extension_root]}

    monkeypatch.setattr(
        "review_engine.extensions.entry_points",
        lambda group: [FakeEntryPoint()],
    )

    runtime = load_rule_runtime(replace(fixture_settings, extension_rule_roots=()))

    assert any(record.rule_no == "ORG.MEM.1" for record in runtime.active_records)
    assert any(record.rule_no == "R.11" for record in runtime.excluded_records)


def test_invalid_public_manifest_fails_fast(fixture_settings, tmp_path) -> None:
    bad_root = tmp_path / "bad-public-root"
    _write(
        bad_root / "manifest.yaml",
        """
        schema_version: 1
        language_id: cpp
        policy_files:
          - policies/bad.yaml
        """,
    )
    _write(
        bad_root / "policies" / "bad.yaml",
        """
        schema_version: 1
        language_id: cpp
        pack_weights:
          cpp_core: 0.72
        """,
    )

    with pytest.raises(Exception):
        load_rule_runtime(replace(fixture_settings, public_rule_root=bad_root))


def test_invalid_filesystem_extension_manifest_fails_fast_even_when_strict_is_disabled(
    fixture_settings,
    tmp_path,
) -> None:
    bad_root = tmp_path / "bad-extension-root"
    _write(
        bad_root / "manifest.yaml",
        """
        schema_version: 1
        language_id: cpp
        policy_files:
          - policies/bad.yaml
        """,
    )
    _write(
        bad_root / "policies" / "bad.yaml",
        """
        schema_version: 1
        language_id: cpp
        pack_weights:
          cpp_core: 0.72
        """,
    )

    with pytest.raises(Exception):
        load_rule_runtime(
            replace(
                fixture_settings,
                extension_rule_roots=(bad_root,),
                strict_extension_loading=False,
            )
        )


def test_broken_extension_import_warns_and_falls_back_in_strict_mode(
    fixture_settings,
    monkeypatch,
    caplog,
) -> None:
    class BrokenEntryPoint:
        name = "broken-extension"

        def load(self):
            raise ImportError("boom")

    monkeypatch.setattr(
        "review_engine.extensions.entry_points",
        lambda group: [BrokenEntryPoint()],
    )

    with caplog.at_level(logging.WARNING):
        runtime = load_rule_runtime(fixture_settings)

    assert runtime.active_records
    assert "Failed to import rule extension entry point broken-extension" in caplog.text


def test_invalid_extension_spec_fails_fast_in_strict_mode(
    fixture_settings,
    monkeypatch,
) -> None:
    class InvalidEntryPoint:
        name = "invalid-extension"

        def load(self):
            return lambda: object()

    monkeypatch.setattr(
        "review_engine.extensions.entry_points",
        lambda group: [InvalidEntryPoint()],
    )

    with pytest.raises(ValueError):
        load_rule_runtime(fixture_settings)


def test_invalid_extension_spec_warns_and_falls_back_when_strict_is_disabled(
    fixture_settings,
    monkeypatch,
    caplog,
) -> None:
    class InvalidEntryPoint:
        name = "invalid-extension"

        def load(self):
            return lambda: object()

    monkeypatch.setattr(
        "review_engine.extensions.entry_points",
        lambda group: [InvalidEntryPoint()],
    )

    with caplog.at_level(logging.WARNING):
        runtime = load_rule_runtime(replace(fixture_settings, strict_extension_loading=False))

    assert runtime.active_records
    assert "Ignoring invalid extension spec from invalid-extension" in caplog.text


def test_prompt_composer_stacks_public_layers_and_extension_overlay(
    fixture_settings,
    tmp_path,
) -> None:
    prompt_root = fixture_settings.project_root / "prompts"
    overlay_root = tmp_path / "prompt-overlays"
    _write(
        overlay_root / "overlays" / "org.md",
        """
        조직 overlay: 프로젝트별 래퍼와 ownership abstraction을 우선한다.
        """,
    )
    composer = PromptComposer(
        replace(
            fixture_settings,
            prompt_root=prompt_root,
            extension_prompt_roots=(overlay_root,),
        )
    )

    prompt = composer.compose(language_id="cpp", profile_id="default", overlay_refs=["org"])

    assert "공개 멀티 랭귀지 가이드라인" in prompt
    assert "RAII와 표준 라이브러리 기반 자원 관리" in prompt
    assert "shared_security" in prompt
    assert "조직 overlay" in prompt


def test_rerank_prefers_priority_tier_and_pack_weight_over_legacy_authority(
    fixture_settings,
) -> None:
    analysis = QueryAnalysis(
        input_kind="code",
        query_text="raw ownership issue",
        patterns=[
            QueryPattern(
                name="manual_delete",
                description="Explicit delete detected; review ownership guidance.",
                weight=1.0,
            )
        ],
    )
    policy = PriorityPolicy(
        policy_id="test-priority",
        tier_order=["override", "high", "default", "reference"],
        tie_breakers=[
            "explicit_override",
            "higher_tier",
            "higher_specificity",
            "higher_base_score",
            "higher_pack_weight",
            "lexical_rule_id",
        ],
    )
    public_candidate = CandidateHit(
        record=GuidelineRecord(
            id="cpp_core:R.11",
            rule_no="R.11",
            source="fixture",
            pack_id="cpp_core",
            source_kind="public_standard",
            source_family="cpp_core",
            authority="internal",
            section="R",
            title="Avoid calling new and delete explicitly",
            text="Prefer managed ownership.",
            summary="Avoid explicit new/delete.",
            keywords=["new", "delete"],
            base_score=0.92,
            priority_tier="default",
            pack_weight=0.72,
            specificity=0.85,
            severity_default=0.95,
            conflict_action="compatible",
        ),
        distance=0.4,
        similarity_score=0.60,
    )
    org_candidate = CandidateHit(
        record=GuidelineRecord(
            id="org_cpp:ORG.MEM.1",
            rule_no="ORG.MEM.1",
            source="fixture",
            pack_id="org_cpp",
            source_kind="organization_policy",
            source_family="org_cpp",
            authority="external",
            section="ORG",
            title="Use the organization owner wrapper",
            text="Prefer the owner wrapper over raw ownership.",
            summary="Organization owner wrapper guidance.",
            keywords=["owner", "wrapper", "ownership"],
            base_score=0.85,
            priority_tier="override",
            pack_weight=0.97,
            specificity=0.99,
            explicit_override=True,
            severity_default=0.90,
            conflict_action="compatible",
        ),
        distance=0.4,
        similarity_score=0.60,
    )

    ranked = rerank_candidates(
        [public_candidate, org_candidate],
        analysis,
        fixture_settings,
        top_k=2,
        policy=policy,
    )

    assert [candidate.record.rule_no for candidate in ranked] == ["ORG.MEM.1", "R.11"]
    assert ranked[0].pack_weight_score == pytest.approx(0.97)


def test_rerank_prefers_direct_hint_before_static_specificity_within_same_tier(
    fixture_settings,
) -> None:
    analysis = QueryAnalysis(
        input_kind="code",
        query_text="react hook stale capture and deps suppression",
        language_id="typescript",
        query_plugin_id="typescript",
        patterns=[
            QueryPattern(
                name="hooks_exhaustive_deps_disable",
                description="React hooks exhaustive-deps suppression detected.",
                weight=1.0,
            )
        ],
    )
    policy = PriorityPolicy(policy_id="typescript_default", language_id="typescript")
    generic_candidate = CandidateHit(
        record=GuidelineRecord(
            id="ts_api_design:TS.API.REF.2",
            rule_no="TS.API.REF.2",
            source="fixture",
            pack_id="ts_api_design",
            source_kind="public_standard",
            source_family="ts_api_design",
            authority="external",
            section="TS.API",
            title="Use stable list identity in React rendering",
            text="Stable list keys keep render state predictable.",
            summary="Stable list keys improve rendering consistency.",
            keywords=["react", "list", "key"],
            base_score=0.9,
            priority_tier="default",
            pack_weight=0.84,
            specificity=0.97,
            severity_default=0.7,
            conflict_action="compatible",
            category="state_management",
            trigger_patterns=["jsx_index_key"],
        ),
        distance=0.18,
        similarity_score=0.61,
    )
    hinted_candidate = CandidateHit(
        record=GuidelineRecord(
            id="ts_api_design:TS.API.8",
            rule_no="TS.API.8",
            source="fixture",
            pack_id="ts_api_design",
            source_kind="public_standard",
            source_family="ts_api_design",
            authority="external",
            section="TS.API",
            title="Do not suppress exhaustive-deps without a local ownership argument",
            text="Suppressing exhaustive-deps can hide stale captures and effect ownership bugs.",
            summary="React effect dependencies should stay explicit.",
            keywords=["react", "effect", "deps", "stale"],
            base_score=0.82,
            priority_tier="default",
            pack_weight=0.84,
            specificity=0.68,
            severity_default=0.86,
            conflict_action="compatible",
            category="process",
            trigger_patterns=["hooks_exhaustive_deps_disable"],
        ),
        distance=0.31,
        similarity_score=0.73,
    )

    ranked = rerank_candidates(
        [generic_candidate, hinted_candidate],
        analysis,
        fixture_settings,
        top_k=2,
        policy=policy,
    )

    assert [candidate.record.rule_no for candidate in ranked] == ["TS.API.8", "TS.API.REF.2"]
    assert ranked[0].pattern_boost == pytest.approx(1.0)


def test_rerank_prefers_similarity_before_specificity_when_no_direct_hint_exists(
    fixture_settings,
) -> None:
    analysis = QueryAnalysis(
        input_kind="code",
        query_text="validated request contract at the HTTP boundary",
        language_id="python",
        query_plugin_id="python",
        patterns=[],
    )
    policy = PriorityPolicy(policy_id="python_default", language_id="python")
    more_specific_but_less_similar = CandidateHit(
        record=GuidelineRecord(
            id="pep8_python:PY.4",
            rule_no="PY.4",
            source="fixture",
            pack_id="pep8_python",
            source_kind="public_standard",
            source_family="pep8_python",
            authority="external",
            section="PY",
            title="Prefer clear and direct control flow",
            text="Control flow should stay obvious.",
            summary="Direct control flow is easier to maintain.",
            keywords=["clarity", "control-flow"],
            base_score=0.9,
            priority_tier="default",
            pack_weight=0.82,
            specificity=0.96,
            severity_default=0.7,
            conflict_action="compatible",
            category="process",
        ),
        distance=0.17,
        similarity_score=0.43,
    )
    less_specific_but_more_similar = CandidateHit(
        record=GuidelineRecord(
            id="fastapi_service:PY.FAPI.2",
            rule_no="PY.FAPI.2",
            source="fixture",
            pack_id="fastapi_service",
            source_kind="public_standard",
            source_family="fastapi_service",
            authority="external",
            section="PY.FAPI",
            title="Validate FastAPI request payloads with typed models",
            text="FastAPI request boundaries should stay schema-driven.",
            summary="Typed request models keep handler contracts explicit.",
            keywords=["fastapi", "request", "schema", "validation", "boundary"],
            base_score=0.82,
            priority_tier="default",
            pack_weight=0.92,
            specificity=0.74,
            severity_default=0.82,
            conflict_action="compatible",
            category="security",
        ),
        distance=0.23,
        similarity_score=0.79,
    )

    ranked = rerank_candidates(
        [more_specific_but_less_similar, less_specific_but_more_similar],
        analysis,
        fixture_settings,
        top_k=2,
        policy=policy,
    )

    assert [candidate.record.rule_no for candidate in ranked] == ["PY.FAPI.2", "PY.4"]


def test_rerank_prefers_exact_trigger_pattern_match_before_keyword_overlap(
    fixture_settings,
) -> None:
    analysis = QueryAnalysis(
        input_kind="code",
        query_text="django html escaping bypass at the render boundary",
        language_id="python",
        query_plugin_id="python",
        patterns=[
            QueryPattern(
                name="django_mark_safe",
                description="mark_safe bypasses template escaping",
                weight=0.96,
            )
        ],
    )
    policy = PriorityPolicy(policy_id="python_default", language_id="python")
    exact_trigger_candidate = CandidateHit(
        record=GuidelineRecord(
            id="django_service:PY.DJ.4",
            rule_no="PY.DJ.4",
            source="fixture",
            pack_id="django_service",
            source_kind="public_standard",
            source_family="django_service",
            authority="external",
            section="PYDJ",
            title="mark_safe should stay exceptional",
            text="mark_safe bypasses escaping at an HTML trust boundary.",
            summary="mark_safe widens XSS review scope.",
            keywords=["django", "template", "escaping", "xss"],
            base_score=0.82,
            priority_tier="default",
            pack_weight=0.82,
            specificity=0.72,
            severity_default=0.86,
            conflict_action="compatible",
            category="security",
            trigger_patterns=["django_mark_safe"],
        ),
        distance=0.28,
        similarity_score=0.62,
    )
    keyword_overlap_candidate = CandidateHit(
        record=GuidelineRecord(
            id="project_python:PY.PROJ.8",
            rule_no="PY.PROJ.8",
            source="fixture",
            pack_id="project_python",
            source_kind="public_standard",
            source_family="project_python",
            authority="external",
            section="PYPROJ",
            title="Document explicit trust boundaries",
            text="Trust boundaries should stay obvious in Python services.",
            summary="Keep boundary ownership explicit near rendering and parsing code.",
            keywords=["trust", "boundary", "escaping", "rendering"],
            base_score=0.9,
            priority_tier="default",
            pack_weight=0.88,
            specificity=0.94,
            severity_default=0.8,
            conflict_action="compatible",
            category="process",
        ),
        distance=0.19,
        similarity_score=0.77,
    )

    ranked = rerank_candidates(
        [keyword_overlap_candidate, exact_trigger_candidate],
        analysis,
        fixture_settings,
        top_k=2,
        policy=policy,
    )

    assert [candidate.record.rule_no for candidate in ranked] == ["PY.DJ.4", "PY.PROJ.8"]
    assert ranked[0].pattern_boost > 0.9
    assert ranked[0].pattern_boost > ranked[1].pattern_boost


def test_prompt_composer_loads_profile_and_context_overlays_for_new_multilang_profiles() -> None:
    composer = PromptComposer()

    prompt = composer.compose(
        language_id="typescript",
        profile_id="nextjs_frontend",
        context_id="app_router",
    )

    assert "TypeScript 검토 시 특히 아래를 중요하게 봅니다." in prompt
    assert "Next.js 프론트엔드 검토 시 특히 아래를 중요하게 봅니다." in prompt
    assert "이 파일은 Next.js `app router` 컨텍스트입니다." in prompt
