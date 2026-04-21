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


def test_public_ingest_uses_canonical_yaml_without_internal_markdown(fixture_settings, tmp_path) -> None:
    settings = replace(
        fixture_settings,
        internal_guideline_path=tmp_path / "missing" / "legacy-test-fixture.md",
    )

    summary = ingest_all_sources(settings)

    assert summary.total_parsed == summary.cpp_core_records
    assert summary.active_records > 0
    assert Path(summary.active_dataset_path).exists()
    assert summary.public_rule_root.endswith("/rules/cpp")


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

    assert "공개 C++ 가이드라인" in prompt
    assert "RAII와 표준 라이브러리 기반 자원 관리" in prompt
    assert "기본 프로필은 공개 `cpp_core` pack만 사용합니다." in prompt
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
