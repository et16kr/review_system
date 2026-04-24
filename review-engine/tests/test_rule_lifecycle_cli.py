from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

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
