from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from review_bot.language_registry import get_language_registry

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = WORKSPACE_ROOT / "ops" / "scripts" / "smoke_local_gitlab_multilang_review.py"


def _load_smoke_script():
    scripts_dir = SCRIPT_PATH.parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    spec = importlib.util.spec_from_file_location(
        "smoke_local_gitlab_multilang_review",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_smoke_fixture_loader_accepts_default_alias() -> None:
    script = _load_smoke_script()

    fixture = script.load_smoke_fixture("default")
    script.validate_fixture_contract(fixture)

    assert fixture.fixture_id == "synthetic-mixed-language"
    assert ".gitlab-ci.yml" in fixture.base_files
    assert "api/routes/items.py" in fixture.feature_files


def test_all_smoke_fixtures_satisfy_contract() -> None:
    script = _load_smoke_script()
    fixture_ids = script._available_fixture_ids()

    assert {"synthetic-mixed-language", "curated-polyglot", "cuda-targeted"}.issubset(
        fixture_ids
    )
    for fixture_id in fixture_ids:
        fixture = script.load_smoke_fixture(fixture_id)
        script.validate_fixture_contract(fixture)


def test_smoke_fixture_contract_rejects_unchanged_required_path() -> None:
    script = _load_smoke_script()
    fixture = script.load_smoke_fixture("cuda-targeted")
    feature_files = dict(fixture.feature_files)
    feature_files[".gitlab-ci.yml"] = fixture.base_files[".gitlab-ci.yml"]

    with pytest.raises(SystemExit, match="required fixture paths are not changed"):
        script.validate_fixture_contract(replace(fixture, feature_files=feature_files))


def test_smoke_fixture_contract_requires_engine_rule_paths_to_be_required() -> None:
    script = _load_smoke_script()
    fixture = script.load_smoke_fixture("cuda-targeted")
    expected = dict(fixture.expected)
    expected["required_paths"] = ["kernels/stream_ops.cu"]

    with pytest.raises(SystemExit, match="expected engine rule paths must also be required"):
        script.validate_fixture_contract(replace(fixture, expected=expected))


def test_smoke_comment_contract_reports_missing_and_forbidden_tags() -> None:
    script = _load_smoke_script()
    fixture = script.load_smoke_fixture("synthetic-mixed-language")

    validation = script.validate_bot_comments(
        [
            "[봇 리뷰][yaml] YAML issue",
            "[봇 리뷰][sql] SQL issue",
            "[봇 리뷰][python] Python issue",
        ],
        fixture.expected,
    )

    assert validation["bot_comment_count"] == 3
    with pytest.raises(RuntimeError, match="Missing expected"):
        script.validate_bot_comments(
            [
                "[봇 리뷰][yaml] YAML issue",
                "[봇 리뷰][sql] SQL issue",
                "[봇 리뷰][yaml] Another YAML issue",
            ],
            fixture.expected,
        )
    with pytest.raises(RuntimeError, match="forbidden language"):
        script.validate_bot_comments(
            [
                "[봇 리뷰][yaml] YAML issue",
                "[봇 리뷰][sql] SQL issue",
                "[봇 리뷰][python] Python issue",
                "[봇 리뷰][cpp] C++ issue",
            ],
            fixture.expected,
        )


def test_prepare_local_repo_materializes_selected_fixture(tmp_path: Path) -> None:
    script = _load_smoke_script()
    fixture = script.load_smoke_fixture("cuda-targeted")
    repo_path = tmp_path / "repo"

    script._prepare_local_repo(
        repo_path=repo_path,
        target_branch="smoke_base",
        source_branch="smoke_feature",
        fixture=fixture,
    )
    changed_files = subprocess.run(
        ["git", "diff", "--name-only", "smoke_base..smoke_feature"],
        cwd=repo_path,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()

    assert "kernels/stream_ops.cu" in changed_files
    assert ".gitlab-ci.yml" in changed_files
    assert set(changed_files) == {
        ".gitlab-ci.yml",
        "docs/release_notes.md",
        "kernels/stream_ops.cu",
    }


def test_cuda_targeted_fixture_routes_languages_and_profiles() -> None:
    script = _load_smoke_script()
    fixture = script.load_smoke_fixture("cuda-targeted")
    registry = get_language_registry()

    cuda = registry.resolve(
        file_path="kernels/stream_ops.cu",
        source_text=fixture.feature_files["kernels/stream_ops.cu"],
    )
    gitlab_ci = registry.resolve(
        file_path=".gitlab-ci.yml",
        source_text=fixture.feature_files[".gitlab-ci.yml"],
    )
    markdown = registry.resolve(
        file_path="docs/release_notes.md",
        source_text=fixture.feature_files["docs/release_notes.md"],
    )

    assert (cuda.language_id, cuda.profile_id) == ("cuda", "cuda_async_runtime")
    assert cuda.reviewable is True
    assert (gitlab_ci.language_id, gitlab_ci.profile_id, gitlab_ci.context_id) == (
        "yaml",
        "gitlab_ci",
        "gitlab_ci",
    )
    assert markdown.language_id == "markdown"
    assert markdown.reviewable is False


def test_smoke_fixture_expected_engine_rule_ids_exist() -> None:
    script = _load_smoke_script()
    rule_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((WORKSPACE_ROOT / "review-engine" / "rules").rglob("*.yaml"))
    )
    available_rule_nos = set(
        re.findall(r"^\s*-?\s*rule_no:\s*([A-Za-z0-9_.-]+)\s*$", rule_text, re.MULTILINE)
    )
    expected_rule_nos: set[str] = set()

    for fixture_id in script._available_fixture_ids():
        fixture = script.load_smoke_fixture(fixture_id)
        for rule_nos in fixture.expected.get("expected_engine_rules", {}).values():
            expected_rule_nos.update(str(rule_no) for rule_no in rule_nos)

    assert expected_rule_nos
    assert sorted(expected_rule_nos - available_rule_nos) == []
