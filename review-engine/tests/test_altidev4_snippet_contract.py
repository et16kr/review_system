from __future__ import annotations

import json
from pathlib import Path

import pytest

from review_engine.query.code_to_query import build_query_analysis
from review_engine.query.repository_scan import scan_repository

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _repo_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def _load_manifest() -> list[dict[str, object]]:
    return json.loads(_repo_path("examples/altidev4_snippets.json").read_text(encoding="utf-8"))


def _load_expected_examples() -> list[dict[str, object]]:
    return json.loads(
        _repo_path("examples/expected_retrieval_examples.json").read_text(encoding="utf-8")
    )


SNIPPET_CASES = _load_manifest()


@pytest.mark.parametrize(
    ("example_path", "focus_patterns"),
    [
        (str(item["example_path"]), tuple(item["focus_patterns"]))
        for item in SNIPPET_CASES
    ],
)
def test_altidev4_manifest_focus_patterns_are_detected(
    example_path: str,
    focus_patterns: tuple[str, ...],
) -> None:
    payload = _repo_path(example_path).read_text(encoding="utf-8")
    analysis = build_query_analysis(payload, input_kind="code")
    detected = {pattern.name for pattern in analysis.patterns}

    for pattern_name in focus_patterns:
        assert pattern_name in detected, f"{example_path} missing focus pattern {pattern_name}"


@pytest.mark.parametrize(
    ("example_path", "expected_rules"),
    [
        (str(item["example_path"]), tuple(item["expected_rules"]))
        for item in SNIPPET_CASES
    ],
)
def test_altidev4_manifest_expected_rules_are_present_in_top6(
    real_search_service,
    example_path: str,
    expected_rules: tuple[str, ...],
) -> None:
    payload = _repo_path(example_path).read_text(encoding="utf-8")
    response = real_search_service.review_code(payload, top_k=6)
    returned_rules = {result.rule_no for result in response.results}

    for rule_no in expected_rules:
        assert rule_no in returned_rules, f"{example_path} missing {rule_no} in top-6"


def test_altidev4_manifest_examples_are_registered_in_expected_examples_spec() -> None:
    manifest_paths = {str(item["example_path"]) for item in _load_manifest()}
    expected_paths = {str(item["input"]) for item in _load_expected_examples()}

    assert manifest_paths <= expected_paths


def test_repository_scan_reports_exact_repo_local_altidev4_files() -> None:
    report = scan_repository(
        _repo_path("examples"),
        include_dirs=["altidev4"],
        ignore_patterns=["identifier_underscore", "ownership_ambiguity", "line_comment"],
    )

    scanned_names = {Path(finding.path).name for finding in report.findings}
    expected_names = {Path(str(item["example_path"])).name for item in _load_manifest()}

    assert report.scanned_files == len(expected_names)
    assert report.matched_files == len(expected_names)
    assert scanned_names == expected_names
