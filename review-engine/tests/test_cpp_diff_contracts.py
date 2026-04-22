from __future__ import annotations

import json
from pathlib import Path

import pytest

from review_engine.query.code_to_query import build_query_analysis

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _repo_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def _load_manifest() -> list[dict[str, object]]:
    return json.loads(_repo_path("examples/cpp_diff_contracts.json").read_text(encoding="utf-8"))


DIFF_CASES = _load_manifest()


def test_cpp_diff_contract_manifest_uses_repo_local_non_altibase_examples() -> None:
    for item in DIFF_CASES:
        example_path = _repo_path(str(item["example_path"]))
        assert example_path.exists(), f"Missing diff file: {example_path}"
        assert example_path.stat().st_size > 0, f"Empty diff file: {example_path}"
        assert not Path(str(item["example_path"])).is_absolute(), (
            f"Diff path must be repo-local: {example_path}"
        )
        assert "altidev4" not in str(item["example_path"]).lower()
        assert "altibase" not in str(item.get("source_path", "")).lower()


@pytest.mark.parametrize(
    ("example_path", "focus_patterns"),
    [
        (str(item["example_path"]), tuple(item["focus_patterns"]))
        for item in DIFF_CASES
    ],
)
def test_cpp_diff_contract_focus_patterns_are_detected(
    example_path: str,
    focus_patterns: tuple[str, ...],
) -> None:
    payload = _repo_path(example_path).read_text(encoding="utf-8")
    analysis = build_query_analysis(payload, input_kind="diff")
    detected = {pattern.name for pattern in analysis.patterns}

    for pattern_name in focus_patterns:
        assert pattern_name in detected, f"{example_path} missing focus pattern {pattern_name}"


@pytest.mark.parametrize(
    ("example_path", "expected_rules"),
    [
        (str(item["example_path"]), tuple(item["expected_rules"]))
        for item in DIFF_CASES
    ],
)
def test_cpp_diff_contract_expected_rules_are_present_in_top6(
    real_search_service,
    example_path: str,
    expected_rules: tuple[str, ...],
) -> None:
    payload = _repo_path(example_path).read_text(encoding="utf-8")
    response = real_search_service.review_diff(payload, top_k=6)
    returned_rules = {result.rule_no for result in response.results}

    for rule_no in expected_rules:
        assert rule_no in returned_rules, f"{example_path} missing {rule_no} in top-6"
