from __future__ import annotations

import json
from pathlib import Path

from review_engine.query.code_to_query import build_query_analysis
from review_engine.query.repository_scan import scan_repository

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _repo_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_manifest() -> list[dict[str, object]]:
    manifest_path = _repo_path("examples/altidev4_snippets.json")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def test_altidev4_snippet_manifest_points_to_existing_non_empty_examples() -> None:
    manifest = _load_manifest()

    for item in manifest:
        example_path = _repo_path(str(item["example_path"]))
        assert example_path.exists(), f"Missing snippet file: {example_path}"
        assert example_path.stat().st_size > 0, f"Empty snippet file: {example_path}"
        assert not Path(str(item["example_path"])).is_absolute(), (
            f"Snippet path must be repo-local: {example_path}"
        )


def test_altidev4_queue_perf_patterns_are_detected_from_local_snippet() -> None:
    queue_perf = _read_text(_repo_path("examples/altidev4/queue_perf_memory_and_rc.cpp"))

    analysis = build_query_analysis(queue_perf, input_kind="code")
    names = {pattern.name for pattern in analysis.patterns}

    assert {"raw_new", "malloc_free", "manual_delete", "direct_system_call"} <= names
    assert "ide_rc_flow" not in names


def test_altidev4_stackwalker_excerpt_detects_switch_and_free_patterns() -> None:
    excerpt = _read_text(_repo_path("examples/altidev4/stackwalker_switch_and_free.cpp"))

    analysis = build_query_analysis(excerpt, input_kind="code")
    names = {pattern.name for pattern in analysis.patterns}

    assert "switch_without_default" in names
    assert "malloc_free" in names
    assert "direct_system_call" in names


def test_repository_scan_handles_repo_local_altidev4_snippets() -> None:
    report = scan_repository(
        _repo_path("examples"),
        include_dirs=["altidev4"],
        ignore_patterns=["identifier_underscore", "ownership_ambiguity", "line_comment"],
    )

    assert report.scanned_files == 7
    assert report.matched_files == 7
    assert "raw_new" in report.aggregate_patterns
    assert "switch_without_default" in report.aggregate_patterns
    assert "direct_system_header" in report.aggregate_patterns


def test_altidev4_snippet_manifest_expected_rules_are_returned(real_search_service) -> None:
    manifest = _load_manifest()

    for item in manifest:
        example_path = _repo_path(str(item["example_path"]))
        payload = example_path.read_text(encoding="utf-8")
        response = real_search_service.review_code(payload, top_k=12)
        returned_rules = {result.rule_no for result in response.results}

        for expected_rule in item["expected_rules"]:
            assert expected_rule in returned_rules, (
                f"{example_path} missing expected rule {expected_rule}"
            )
