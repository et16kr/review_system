from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

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
