from __future__ import annotations

import json

import pytest

from review_engine.cli import rule_lifecycle


def _run_cli(argv, fixture_settings, monkeypatch, capsys):
    monkeypatch.setattr(rule_lifecycle, "get_settings", lambda: fixture_settings)
    rule_lifecycle.main(argv)
    return json.loads(capsys.readouterr().out)


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
