from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def _load_script_module(module_name: str, relative_path: str) -> ModuleType:
    module_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture_wrong_language_telemetry = _load_script_module(
    "capture_wrong_language_telemetry",
    "ops/scripts/capture_wrong_language_telemetry.py",
)
build_wrong_language_backlog = _load_script_module(
    "build_wrong_language_backlog",
    "ops/scripts/build_wrong_language_backlog.py",
)


def _wrong_language_report() -> dict[str, object]:
    return {
        "total_events": 4,
        "smoke_events": 1,
        "production_events": 3,
        "unknown_provenance_events": 0,
        "distinct_threads": 3,
        "distinct_findings": 3,
        "top_language_pairs": [
            {
                "detected_language_id": "python",
                "expected_language_id": "markdown",
                "count": 3,
            },
            {
                "detected_language_id": "yaml",
                "expected_language_id": "markdown",
                "count": 1,
            },
        ],
        "top_profiles": [
            {
                "detected_language_id": "python",
                "expected_language_id": "markdown",
                "profile_id": "fastapi",
                "context_id": "generic",
                "count": 3,
            }
        ],
        "top_paths": [
            {
                "detected_language_id": "python",
                "expected_language_id": "markdown",
                "path_pattern": "docs/api.py",
                "count": 3,
            }
        ],
        "triage_candidates": [
            {
                "priority": "high",
                "provenance": "production",
                "triage_cause": "detector_miss",
                "actionability": "fix_detector",
                "detected_language_id": "python",
                "expected_language_id": "markdown",
                "profile_id": "fastapi",
                "context_id": "generic",
                "path_pattern": "docs/api.py",
                "count": 3,
                "suggested_action": "Add a docs-like path regression for FastAPI examples.",
            },
            {
                "priority": "low",
                "provenance": "smoke",
                "triage_cause": "synthetic_smoke",
                "actionability": "ignore_for_detector_backlog",
                "detected_language_id": "yaml",
                "expected_language_id": "markdown",
                "profile_id": "default",
                "context_id": "generic",
                "path_pattern": ".github/workflows/review.yml",
                "count": 1,
                "suggested_action": "Keep as telemetry-only smoke validation.",
            },
        ],
    }


def test_wrong_language_telemetry_snapshot_flags_smoke_feedback() -> None:
    markdown = capture_wrong_language_telemetry.render_markdown(
        bot_base_url="http://127.0.0.1:18081",
        project_ref=None,
        window="28d",
        report=_wrong_language_report(),
    )

    assert "## Interpretation Note" in markdown
    assert "detector backlog로 바로 옮기지 마세요." in markdown
    assert "- smoke_events: `1`" in markdown
    assert "synthetic_smoke" in markdown


def test_wrong_language_backlog_keeps_synthetic_smoke_out_of_detector_fixes() -> None:
    markdown = build_wrong_language_backlog.render_markdown(
        bot_base_url="http://127.0.0.1:18081",
        project_ref=None,
        window="28d",
        report=_wrong_language_report(),
        min_count=1,
        max_items=12,
    )

    detector_section = markdown.split("## Detector Fix Candidates", maxsplit=1)[1].split(
        "## Likely Wrong Thread Target",
        maxsplit=1,
    )[0]
    smoke_section = markdown.split("## Synthetic Smoke Events", maxsplit=1)[1].split(
        "## Raw JSON",
        maxsplit=1,
    )[0]

    assert "- synthetic_smoke_candidates: `1`" in markdown
    assert "`python` -> `markdown` x3" in detector_section
    assert "`yaml` -> `markdown` x1" not in detector_section
    assert "`yaml` -> `markdown` x1" in smoke_section
