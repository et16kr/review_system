from __future__ import annotations

import json
from pathlib import Path

from review_bot.cli import review_unit_split_audit as review_unit_split_audit_cli
from review_bot.quality.review_unit_split_audit import (
    evaluate_review_unit_split_cases,
    load_review_unit_split_cases,
)
from review_bot.review_units import DEFAULT_MAX_LINES_PER_REVIEW_UNIT, iter_review_units


def _large_added_patch(total_lines: int) -> str:
    header = f"@@ -0,0 +1,{total_lines} @@"
    return "\n".join([header, *[f"+line {index:03d}" for index in range(1, total_lines + 1)]])


def test_iter_review_units_splits_large_add_only_hunk() -> None:
    units = iter_review_units(
        _large_added_patch(DEFAULT_MAX_LINES_PER_REVIEW_UNIT + 5),
        max_lines_per_review_unit=DEFAULT_MAX_LINES_PER_REVIEW_UNIT,
    )

    assert len(units) == 2
    assert units[0].candidate_line_nos[0] == 1
    assert len(units[0].candidate_line_nos) == DEFAULT_MAX_LINES_PER_REVIEW_UNIT
    assert units[1].candidate_line_nos[0] == DEFAULT_MAX_LINES_PER_REVIEW_UNIT + 1
    assert len(units[1].candidate_line_nos) == 5


def test_review_unit_split_audit_prioritizes_tree_and_indentation_languages() -> None:
    report = evaluate_review_unit_split_cases(load_review_unit_split_cases())

    assert report["summary"]["selected_languages"] == ["python", "typescript", "yaml"]

    results = {
        result["case_id"]: result
        for result in report["results"]
    }
    assert (
        results["python_fastapi_long_handler"]["recommendation"]
        == "prioritize_syntax_aware_split"
    )
    assert (
        results["typescript_react_long_component"]["recommendation"]
        == "prioritize_syntax_aware_split"
    )
    assert (
        results["yaml_k8s_long_container_env"]["recommendation"]
        == "prioritize_syntax_aware_split"
    )
    assert results["go_http_long_handler"]["recommendation"] == "monitor_current_hunk_split"


def test_review_unit_split_audit_cli_writes_report(tmp_path: Path) -> None:
    output_path = tmp_path / "review_unit_split_audit.md"
    json_output_path = tmp_path / "review_unit_split_audit.json"

    exit_code = review_unit_split_audit_cli.main(
        [
            "--output",
            str(output_path),
            "--json-output",
            str(json_output_path),
        ]
    )

    assert exit_code == 0
    markdown = output_path.read_text(encoding="utf-8")
    payload = json.loads(json_output_path.read_text(encoding="utf-8"))

    assert "# Review Unit Split Audit" in markdown
    assert "- selected_languages: `python`, `typescript`, `yaml`" in markdown
    assert payload["summary"]["selected_languages"] == ["python", "typescript", "yaml"]
