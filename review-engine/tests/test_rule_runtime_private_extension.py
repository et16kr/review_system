from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from review_engine.ingest.build_records import ingest_all_sources
from review_engine.ingest.rule_loader import load_rule_runtime


def _sample_extension_root(project_root: Path) -> Path:
    return project_root / "examples" / "extensions" / "private_org_cpp"


def test_repo_sample_extension_root_can_override_and_exclude_public_rules(
    fixture_settings,
) -> None:
    extension_root = _sample_extension_root(fixture_settings.project_root)
    settings = replace(fixture_settings, extension_rule_roots=(extension_root,))

    runtime = load_rule_runtime(settings)

    active_rules = {record.rule_no for record in runtime.active_records}
    reference_rules = {record.rule_no for record in runtime.reference_records}
    excluded_rules = {record.rule_no for record in runtime.excluded_records}
    by_rule = {
        record.rule_no: record
        for record in [*runtime.active_records, *runtime.reference_records, *runtime.excluded_records]
    }

    assert extension_root.exists()
    assert "ORG.MEM.1" in active_rules
    assert "ORG.REF.1" in reference_rules
    assert "R.11" in excluded_rules
    assert "ES.6" in excluded_rules
    assert runtime.extension_rule_roots == [str(extension_root.resolve())]
    assert by_rule["ORG.MEM.1"].pack_weight == pytest.approx(0.97)
    assert by_rule["ORG.MEM.1"].conflict_action == "compatible"
    assert by_rule["ORG.REF.1"].reviewability == "reference_only"
    assert by_rule["ORG.REF.1"].priority_tier == "reference"
    assert by_rule["ORG.REF.1"].conflict_action == "compatible"


def test_repo_sample_extension_root_contributes_org_records_to_ingest_summary(
    fixture_settings,
) -> None:
    extension_root = _sample_extension_root(fixture_settings.project_root)
    settings = replace(fixture_settings, extension_rule_roots=(extension_root,))

    summary = ingest_all_sources(settings)

    assert extension_root.exists()
    assert summary.organization_policy_records > 0
    assert summary.extension_rule_roots == [str(extension_root.resolve())]
