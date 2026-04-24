from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from review_engine.cli import rule_package
from review_engine.ingest.build_records import ingest_all_sources
from review_engine.ingest.rule_loader import load_rule_runtime
from review_engine.rule_package import RulePackageValidationError, validate_rule_package


def _sample_extension_root(project_root: Path) -> Path:
    return project_root / "examples" / "extensions" / "private_org_cpp"


def _copy_sample_package(project_root: Path, tmp_path: Path) -> Path:
    copied_root = tmp_path / "private_org_cpp"
    shutil.copytree(_sample_extension_root(project_root), copied_root)
    return copied_root


def _mutate_package_yaml(package_root: Path, mutate) -> None:
    package_path = package_root / "package.yaml"
    payload = yaml.safe_load(package_path.read_text(encoding="utf-8"))
    mutate(payload)
    package_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


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


def test_repo_sample_private_package_manifest_validates_runtime_boundary(
    fixture_settings,
) -> None:
    package_root = _sample_extension_root(fixture_settings.project_root)

    payload = validate_rule_package(package_root)

    assert payload["source_of_truth"] == "package_yaml"
    assert payload["validation_mode"] == "read_only"
    assert payload["package_id"] == "com.example.private_org_cpp"
    assert payload["package_version"] == "0.1.0"
    assert payload["package_kind"] == "review_engine_rule_extension"
    assert payload["schema_version"] == 1
    assert payload["compatible_review_engine"]["rule_schema_version"] == 1
    assert payload["extension_roots"][0]["path"] == "."
    assert payload["extension_roots"][0]["language_id"] == "cpp"
    assert payload["extension_roots"][0]["pack_files"] == ["packs/org_cpp.yaml"]
    assert payload["included"]["pack_files"] == ["packs/org_cpp.yaml"]
    assert payload["included"]["profile_files"] == ["profiles/default.yaml"]
    assert payload["included"]["policy_files"] == ["policies/org_default.yaml"]
    assert payload["included"]["source_manifest_files"] == []
    assert payload["mutated_files"] == []


def test_rule_package_validate_cli_emits_deterministic_json(
    fixture_settings,
    capsys,
) -> None:
    package_root = _sample_extension_root(fixture_settings.project_root)

    rule_package.main(["validate", "--package-root", str(package_root)])

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "validate"
    assert payload["package_manifest_path"].endswith(
        "review-engine/examples/extensions/private_org_cpp/package.yaml"
    )
    assert payload["provenance"]["source_revision"] == "fixture"
    assert payload["mutated_files"] == []


@pytest.mark.parametrize(
    ("mutate", "error_pattern"),
    [
        (
            lambda payload: payload.update({"unexpected_key": True}),
            "unexpected_key",
        ),
        (
            lambda payload: payload.update({"schema_version": 2}),
            "schema_version",
        ),
        (
            lambda payload: payload.update({"package_kind": "unsupported_kind"}),
            "package_kind",
        ),
        (
            lambda payload: payload["included"]["pack_files"].__setitem__(
                0,
                "packs/missing.yaml",
            ),
            "Included package file does not exist: packs/missing.yaml",
        ),
        (
            lambda payload: payload["included"]["pack_files"].__setitem__(
                0,
                "../outside.yaml",
            ),
            "path must not contain path traversal",
        ),
        (
            lambda payload: payload["included"]["pack_files"].__setitem__(
                0,
                "/tmp/outside.yaml",
            ),
            "path must be package-relative",
        ),
    ],
)
def test_private_package_manifest_rejects_invalid_metadata_and_paths(
    fixture_settings,
    tmp_path,
    mutate,
    error_pattern,
) -> None:
    package_root = _copy_sample_package(fixture_settings.project_root, tmp_path)
    _mutate_package_yaml(package_root, mutate)

    with pytest.raises(RulePackageValidationError, match=error_pattern):
        validate_rule_package(package_root)
