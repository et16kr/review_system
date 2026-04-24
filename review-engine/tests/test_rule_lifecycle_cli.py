from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from review_engine.cli import rule_lifecycle
from review_engine.ingest.rule_loader import load_rule_runtime


def _run_cli(argv, fixture_settings, monkeypatch, capsys):
    monkeypatch.setattr(rule_lifecycle, "get_settings", lambda: fixture_settings)
    rule_lifecycle.main(argv)
    return json.loads(capsys.readouterr().out)


def _copy_rule_root(project_root: Path, tmp_path: Path) -> Path:
    copied_root = tmp_path / "rules"
    shutil.copytree(project_root / "rules" / "python", copied_root / "python")
    shutil.copytree(project_root / "rules" / "shared", copied_root / "shared")
    return copied_root


def _insert_after(text: str, anchor: str, addition: str) -> str:
    return text.replace(anchor, f"{anchor}{addition}", 1)


def test_rule_lifecycle_list_reads_selected_runtime_from_canonical_yaml(
    fixture_settings,
    monkeypatch,
    capsys,
) -> None:
    payload = _run_cli(
        ["list", "--language-id", "python", "--profile-id", "fastapi_service"],
        fixture_settings,
        monkeypatch,
        capsys,
    )

    rules = {rule["rule_no"]: rule for rule in payload["rules"]}

    assert payload["source_of_truth"] == "canonical_yaml"
    assert payload["language_id"] == "python"
    assert payload["profile_id"] == "fastapi_service"
    assert "fastapi_service" in payload["selected_pack_ids"]
    assert rules["PY.FAPI.1"]["runtime_state"] == "active"
    assert rules["PY.FAPI.REF.1"]["runtime_state"] == "reference"
    assert rules["PY.FAPI.1"]["source_path"].endswith(
        "review-engine/rules/python/packs/fastapi_service.yaml"
    )
    assert not any(fixture_settings.data_dir.iterdir())


def test_rule_lifecycle_show_returns_rule_details_without_ingest(
    fixture_settings,
    monkeypatch,
    capsys,
) -> None:
    payload = _run_cli(
        [
            "show",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--rule",
            "PY.FAPI.1",
        ],
        fixture_settings,
        monkeypatch,
        capsys,
    )

    rule = payload["rule"]

    assert payload["source_of_truth"] == "canonical_yaml"
    assert rule["rule_no"] == "PY.FAPI.1"
    assert rule["runtime_state"] == "active"
    assert rule["summary"].startswith("Blocking work inside async request paths")
    assert rule["source_path"].endswith("review-engine/rules/python/packs/fastapi_service.yaml")
    assert not any(fixture_settings.data_dir.iterdir())


def test_rule_lifecycle_show_fails_when_rule_is_absent_from_selected_runtime(
    fixture_settings,
    monkeypatch,
) -> None:
    monkeypatch.setattr(rule_lifecycle, "get_settings", lambda: fixture_settings)

    with pytest.raises(SystemExit, match=r"Rule not found in selected runtime: R\.11"):
        rule_lifecycle.main([
            "show",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--rule",
            "R.11",
        ])


def test_rule_lifecycle_preview_validates_authoring_runtime_without_ingest(
    fixture_settings,
    monkeypatch,
    capsys,
) -> None:
    payload = _run_cli(
        ["preview", "--language-id", "python", "--profile-id", "fastapi_service"],
        fixture_settings,
        monkeypatch,
        capsys,
    )

    pack_ids = {pack["pack_id"] for pack in payload["pack_resolution"]["selected_packs"]}

    assert payload["command"] == "preview"
    assert payload["source_of_truth"] == "canonical_yaml"
    assert payload["validation_status"] == "passed"
    assert payload["profile_resolution"]["profile_id"] == "fastapi_service"
    assert payload["source_coverage"]["status"] == "passed"
    assert "python.fastapi_service_deepening" in payload["source_coverage"][
        "relevant_source_ids"
    ]
    assert "fastapi_service" in pack_ids
    assert payload["ingest_retrieval_impact"]["reads_generated_artifacts"] is False
    assert payload["ingest_retrieval_impact"]["writes_generated_artifacts"] is False
    assert payload["ingest_retrieval_impact"]["writes_vector_store"] is False
    assert payload["ingest_retrieval_impact"]["record_counts"]["active"] > 0
    assert payload["validation_plan"]["scope"] == "rule_authoring_preview"
    assert not any(fixture_settings.data_dir.iterdir())


def test_rule_lifecycle_preview_reports_typoed_metadata(
    fixture_settings,
    monkeypatch,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    pack_path = copied_rule_root / "python" / "packs" / "fastapi_service.yaml"
    pack_path.write_text(
        pack_path.read_text(encoding="utf-8").replace(
            "    fix_guidance: Move blocking work",
            "    fix_guidence: Move blocking work",
            1,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rule_lifecycle, "get_settings", lambda: settings)

    with pytest.raises(
        SystemExit,
        match=r"canonical YAML validation failed: entries\.0\.fix_guidence",
    ):
        rule_lifecycle.main([
            "preview",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
        ])

    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_preview_reports_unknown_selected_pack(
    fixture_settings,
    monkeypatch,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    profile_path = copied_rule_root / "python" / "profiles" / "fastapi_service.yaml"
    profile_path.write_text(
        _insert_after(
            profile_path.read_text(encoding="utf-8"),
            "  - fastapi_service\n",
            "  - missing_authoring_pack\n",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rule_lifecycle, "get_settings", lambda: settings)

    with pytest.raises(
        SystemExit,
        match=r"selected runtime validation failed: .*missing_authoring_pack",
    ):
        rule_lifecycle.main([
            "preview",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
        ])

    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_preview_reports_source_coverage_miss(
    fixture_settings,
    monkeypatch,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    pack_path = copied_rule_root / "python" / "packs" / "fastapi_service.yaml"
    pack_path.write_text(
        pack_path.read_text(encoding="utf-8")
        + (
            "\n"
            "  - rule_no: PY.FAPI.NEW\n"
            "    section: PYFAPI\n"
            "    title: New FastAPI rule without source coverage\n"
            "    summary: New authoring preview fixtures must be covered by a source atom.\n"
            "    text: A new canonical rule should not pass authoring preview until "
            "source coverage names it.\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(rule_lifecycle, "get_settings", lambda: settings)

    with pytest.raises(
        SystemExit,
        match=r"source coverage missing for selected runtime rules: PY\.FAPI\.NEW",
    ):
        rule_lifecycle.main([
            "preview",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
        ])

    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_list_includes_disabled_entries_from_selected_packs(
    fixture_settings,
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    pack_path = copied_rule_root / "python" / "packs" / "fastapi_service.yaml"
    pack_path.write_text(
        pack_path.read_text(encoding="utf-8").replace(
            "  - rule_no: PY.FAPI.1\n",
            "  - rule_no: PY.FAPI.1\n    enabled: false\n",
            1,
        ),
        encoding="utf-8",
    )

    payload = _run_cli(
        [
            "list",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--state",
            "disabled",
        ],
        settings,
        monkeypatch,
        capsys,
    )

    rules = {rule["rule_no"]: rule for rule in payload["rules"]}

    assert payload["source_of_truth"] == "canonical_yaml"
    assert payload["state_filter"] == "disabled"
    assert rules["PY.FAPI.1"]["runtime_state"] == "disabled"
    assert rules["PY.FAPI.1"]["source_path"] == str(pack_path)
    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_show_returns_disabled_rule_details_from_canonical_pack_yaml(
    fixture_settings,
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    pack_path = copied_rule_root / "python" / "packs" / "fastapi_service.yaml"
    pack_path.write_text(
        pack_path.read_text(encoding="utf-8").replace(
            "  - rule_no: PY.FAPI.1\n",
            "  - rule_no: PY.FAPI.1\n    enabled: false\n",
            1,
        ),
        encoding="utf-8",
    )

    payload = _run_cli(
        [
            "show",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--rule",
            "PY.FAPI.1",
        ],
        settings,
        monkeypatch,
        capsys,
    )

    rule = payload["rule"]

    assert payload["source_of_truth"] == "canonical_yaml"
    assert rule["rule_no"] == "PY.FAPI.1"
    assert rule["runtime_state"] == "disabled"
    assert rule["active"] is False
    assert rule["source_path"] == str(pack_path)
    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_disable_updates_canonical_pack_yaml_only(
    fixture_settings,
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)

    payload = _run_cli(
        [
            "disable",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--rule",
            "PY.FAPI.1",
        ],
        settings,
        monkeypatch,
        capsys,
    )

    pack_path = copied_rule_root / "python" / "packs" / "fastapi_service.yaml"
    runtime = load_rule_runtime(
        settings,
        language_id="python",
        profile_id="fastapi_service",
    )
    validation_commands = {
        entry["name"]: entry["command"] for entry in payload["validation_plan"]["commands"]
    }

    assert payload["command"] == "disable"
    assert payload["source_of_truth"] == "canonical_yaml"
    assert payload["write_boundary"] == "canonical_pack_yaml"
    assert payload["pack_id"] == "fastapi_service"
    assert payload["previous_enabled"] is True
    assert payload["updated_enabled"] is False
    assert payload["changed"] is True
    assert payload["source_path"] == str(pack_path.resolve())
    assert payload["validation_plan"]["scope"] == "rule_lifecycle_mutation"
    assert payload["validation_plan"]["runtime_selector"]["language_id"] == "python"
    assert payload["validation_plan"]["runtime_selector"]["profile_id"] == "fastapi_service"
    assert payload["validation_plan"]["runtime_selector"]["context_id"] is None
    assert payload["validation_plan"]["runtime_selector"]["dialect_id"] is None
    assert payload["validation_plan"]["runtime_selector"]["all_packs"] is False
    assert payload["validation_plan"]["runtime_selector"]["pack_id"] == "fastapi_service"
    assert "fastapi_service" in payload["validation_plan"]["runtime_selector"]["selected_pack_ids"]
    assert (
        validation_commands["show_rule"]
        == "uv run --project review-engine python -m review_engine.cli.rule_lifecycle "
        "show --language-id python --profile-id fastapi_service --rule PY.FAPI.1 "
        "--pack-id fastapi_service"
    )
    assert (
        validation_commands["ingest_guidelines"]
        == "uv run --project review-engine python -m review_engine.cli.ingest_guidelines"
    )
    assert (
        validation_commands["targeted_pytest"]
        == "uv run --project review-engine pytest "
        "review-engine/tests/test_rule_lifecycle_cli.py "
        "review-engine/tests/test_rule_runtime.py -q"
    )
    assert "enabled: false" in pack_path.read_text(encoding="utf-8")
    assert "PY.FAPI.1" not in {record.rule_no for record in runtime.active_records}
    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_enable_reloads_disabled_rule_from_canonical_pack_yaml(
    fixture_settings,
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    pack_path = copied_rule_root / "python" / "packs" / "fastapi_service.yaml"
    pack_path.write_text(
        pack_path.read_text(encoding="utf-8").replace(
            "  - rule_no: PY.FAPI.1\n",
            "  - rule_no: PY.FAPI.1\n    enabled: false\n",
            1,
        ),
        encoding="utf-8",
    )

    payload = _run_cli(
        [
            "enable",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--rule",
            "PY.FAPI.1",
        ],
        settings,
        monkeypatch,
        capsys,
    )

    runtime = load_rule_runtime(
        settings,
        language_id="python",
        profile_id="fastapi_service",
    )

    assert payload["command"] == "enable"
    assert payload["pack_id"] == "fastapi_service"
    assert payload["previous_enabled"] is False
    assert payload["updated_enabled"] is True
    assert payload["changed"] is True
    assert payload["validation_plan"]["scope"] == "rule_lifecycle_mutation"
    assert "enabled: false" not in pack_path.read_text(encoding="utf-8")
    assert "PY.FAPI.1" in {record.rule_no for record in runtime.active_records}
    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_disable_requires_pack_id_when_rule_no_is_ambiguous(
    fixture_settings,
    monkeypatch,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    manifest_path = copied_rule_root / "python" / "manifest.yaml"
    profile_path = copied_rule_root / "python" / "profiles" / "fastapi_service.yaml"
    shadow_pack_path = copied_rule_root / "python" / "packs" / "fastapi_shadow.yaml"
    shadow_pack_path.write_text(
        (copied_rule_root / "python" / "packs" / "fastapi_service.yaml")
        .read_text(encoding="utf-8")
        .replace("pack_id: fastapi_service\n", "pack_id: fastapi_shadow\n", 1),
        encoding="utf-8",
    )
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "  - packs/fastapi_service.yaml\n",
            "  - packs/fastapi_service.yaml\n  - packs/fastapi_shadow.yaml\n",
            1,
        ),
        encoding="utf-8",
    )
    profile_path.write_text(
        profile_path.read_text(encoding="utf-8").replace(
            "  - fastapi_service\n",
            "  - fastapi_service\n  - fastapi_shadow\n",
            1,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(rule_lifecycle, "get_settings", lambda: settings)

    with pytest.raises(
        SystemExit,
        match=r"provide --pack-id to disambiguate: fastapi_service, fastapi_shadow",
    ):
        rule_lifecycle.main([
            "disable",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--rule",
            "PY.FAPI.1",
        ])


def test_rule_lifecycle_disable_pack_updates_canonical_profile_yaml_only(
    fixture_settings,
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)

    payload = _run_cli(
        [
            "disable-pack",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--pack-id",
            "fastapi_service",
        ],
        settings,
        monkeypatch,
        capsys,
    )

    profile_path = copied_rule_root / "python" / "profiles" / "fastapi_service.yaml"
    profile_payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    runtime = load_rule_runtime(
        settings,
        language_id="python",
        profile_id="fastapi_service",
    )
    validation_commands = {
        entry["name"]: entry["command"] for entry in payload["validation_plan"]["commands"]
    }

    assert payload["command"] == "disable-pack"
    assert payload["write_boundary"] == "canonical_profile_yaml"
    assert payload["profile_source_path"] == str(profile_path.resolve())
    assert payload["pack_membership_field"] == "enabled_packs"
    assert payload["selection_origin"] == "profile_explicit"
    assert payload["materialized_default_enabled_fallback"] is False
    assert payload["previous_enabled"] is True
    assert payload["updated_enabled"] is False
    assert payload["changed"] is True
    assert payload["validation_plan"]["scope"] == "rule_lifecycle_profile_pack_mutation"
    assert validation_commands["list_target_pack"] == (
        "uv run --project review-engine python -m review_engine.cli.rule_lifecycle "
        "list --language-id python --profile-id fastapi_service --pack-id fastapi_service"
    )
    assert profile_payload["enabled_packs"] == [
        "pep8_python",
        "pep257_docstrings",
        "project_python",
    ]
    assert profile_payload["shared_packs"] == ["shared_security"]
    assert "fastapi_service" not in runtime.selected_pack_ids
    assert "shared_security" in runtime.selected_pack_ids
    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_disable_pack_materializes_default_enabled_fallback(
    fixture_settings,
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    profile_path = copied_rule_root / "python" / "profiles" / "fastapi_service.yaml"
    profile_path.write_text(
        profile_path.read_text(encoding="utf-8").replace(
            (
                "enabled_packs:\n"
                "  - pep8_python\n"
                "  - pep257_docstrings\n"
                "  - project_python\n"
                "  - fastapi_service\n"
                "shared_packs:\n"
                "  - shared_security\n"
            ),
            "enabled_packs: []\nshared_packs: []\n",
            1,
        ),
        encoding="utf-8",
    )

    payload = _run_cli(
        [
            "disable-pack",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--pack-id",
            "fastapi_service",
        ],
        settings,
        monkeypatch,
        capsys,
    )

    profile_payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    runtime = load_rule_runtime(
        settings,
        language_id="python",
        profile_id="fastapi_service",
    )

    assert payload["selection_origin"] == "default_enabled_fallback"
    assert payload["materialized_default_enabled_fallback"] is True
    assert payload["previous_enabled"] is True
    assert payload["updated_enabled"] is False
    assert profile_payload["enabled_packs"] == [
        "pep8_python",
        "pep257_docstrings",
        "project_python",
        "django_service",
    ]
    assert profile_payload["shared_packs"] == ["shared_security", "review_process"]
    assert "fastapi_service" not in runtime.selected_pack_ids
    assert runtime.selected_pack_ids == [
        "pep8_python",
        "pep257_docstrings",
        "project_python",
        "django_service",
        "shared_security",
        "review_process",
    ]
    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_enable_pack_updates_canonical_profile_yaml_only(
    fixture_settings,
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    manifest_path = copied_rule_root / "python" / "manifest.yaml"
    profile_path = copied_rule_root / "python" / "profiles" / "fastapi_service.yaml"
    shadow_pack_path = copied_rule_root / "python" / "packs" / "fastapi_shadow.yaml"
    shadow_pack_path.write_text(
        (copied_rule_root / "python" / "packs" / "fastapi_service.yaml")
        .read_text(encoding="utf-8")
        .replace("pack_id: fastapi_service\n", "pack_id: fastapi_shadow\n", 1)
        .replace("default_enabled: true\n", "default_enabled: false\n", 1),
        encoding="utf-8",
    )
    manifest_path.write_text(
        _insert_after(
            manifest_path.read_text(encoding="utf-8"),
            "  - packs/fastapi_service.yaml\n",
            "  - packs/fastapi_shadow.yaml\n",
        ),
        encoding="utf-8",
    )

    payload = _run_cli(
        [
            "enable-pack",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--pack-id",
            "fastapi_shadow",
        ],
        settings,
        monkeypatch,
        capsys,
    )

    profile_payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    runtime = load_rule_runtime(
        settings,
        language_id="python",
        profile_id="fastapi_service",
    )

    assert payload["command"] == "enable-pack"
    assert payload["write_boundary"] == "canonical_profile_yaml"
    assert payload["pack_membership_field"] == "enabled_packs"
    assert payload["selection_origin"] == "profile_explicit"
    assert payload["materialized_default_enabled_fallback"] is False
    assert payload["previous_enabled"] is False
    assert payload["updated_enabled"] is True
    assert payload["changed"] is True
    assert profile_payload["enabled_packs"] == [
        "pep8_python",
        "pep257_docstrings",
        "project_python",
        "fastapi_service",
        "fastapi_shadow",
    ]
    assert "fastapi_shadow" in runtime.selected_pack_ids
    assert not any(settings.data_dir.iterdir())


def test_rule_lifecycle_disable_pack_rejects_merged_profile_yaml_write_boundary(
    fixture_settings,
    monkeypatch,
    tmp_path,
) -> None:
    copied_rule_root = _copy_rule_root(fixture_settings.project_root, tmp_path)
    settings = replace(fixture_settings, public_rule_root=copied_rule_root)
    manifest_path = copied_rule_root / "python" / "manifest.yaml"
    merged_profile_path = copied_rule_root / "python" / "profiles" / "fastapi_service_api.yaml"
    merged_profile_path.write_text(
        (
            (copied_rule_root / "python" / "profiles" / "fastapi_service.yaml")
            .read_text(encoding="utf-8")
            .replace(
                "priority_policy_ref: python_default\n",
                "priority_policy_ref: python_default\ncontext_id: api\n",
                1,
            )
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        _insert_after(
            manifest_path.read_text(encoding="utf-8"),
            "  - profiles/fastapi_service.yaml\n",
            "  - profiles/fastapi_service_api.yaml\n",
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(rule_lifecycle, "get_settings", lambda: settings)

    with pytest.raises(SystemExit, match=r"merges multiple profile YAML files"):
        rule_lifecycle.main([
            "disable-pack",
            "--language-id",
            "python",
            "--profile-id",
            "fastapi_service",
            "--context-id",
            "api",
            "--pack-id",
            "fastapi_service",
        ])
