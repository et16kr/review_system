from __future__ import annotations

import json
from pathlib import Path

from review_engine.languages import get_language_registry

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = WORKSPACE_ROOT / "ops" / "fixtures" / "review_smoke"


def _fixture_dirs() -> list[Path]:
    return sorted(
        path
        for path in FIXTURES_ROOT.iterdir()
        if path.is_dir() and (path / "expected_smoke.json").exists()
    )


def _relative_file_paths(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_review_smoke_fixtures_have_contract_layout() -> None:
    assert (FIXTURES_ROOT / "README.md").exists()
    assert (FIXTURES_ROOT / "external_sources.yaml").exists()

    fixture_dirs = _fixture_dirs()
    assert fixture_dirs, "Expected at least one review smoke fixture."

    for fixture_dir in fixture_dirs:
        expected = json.loads((fixture_dir / "expected_smoke.json").read_text(encoding="utf-8"))
        feature_files = _relative_file_paths(fixture_dir / "feature")

        assert (fixture_dir / "manifest.yaml").exists()
        assert (fixture_dir / "base").is_dir()
        assert (fixture_dir / "feature").is_dir()
        assert expected["fixture_id"] == fixture_dir.name
        assert expected["minimum_review_comments"] >= 1
        assert set(expected.get("required_paths", [])).issubset(feature_files)

        serialized = json.dumps(expected, ensure_ascii=False).lower()
        assert "altibase" not in serialized
        assert "altidev4" not in serialized


def test_review_smoke_expected_tags_match_feature_languages() -> None:
    registry = get_language_registry()

    for fixture_dir in _fixture_dirs():
        expected = json.loads((fixture_dir / "expected_smoke.json").read_text(encoding="utf-8"))
        reviewable_languages: set[str] = set()
        non_reviewable_languages: set[str] = set()

        for relative_path in _relative_file_paths(fixture_dir / "feature"):
            file_path = fixture_dir / "feature" / relative_path
            match = registry.resolve(
                file_path=relative_path,
                source_text=file_path.read_text(encoding="utf-8"),
            )
            if match.reviewable:
                reviewable_languages.add(match.language_id)
            else:
                non_reviewable_languages.add(match.language_id)

        expected_tags = set(expected.get("expected_language_tags", []))
        expected_engine_languages = set(expected.get("expected_engine_languages", []))
        forbidden_tags = set(expected.get("forbidden_language_tags", []))
        expected_engine_rules = expected.get("expected_engine_rules", {})

        assert expected_tags <= reviewable_languages
        assert expected_engine_languages <= reviewable_languages
        assert expected_tags.isdisjoint(non_reviewable_languages)
        assert expected_tags.isdisjoint(forbidden_tags)
        assert expected_engine_languages
        assert isinstance(expected_engine_rules, dict)
        assert expected_engine_rules


def test_cuda_targeted_smoke_fixture_keeps_cuda_contract() -> None:
    expected = json.loads(
        (FIXTURES_ROOT / "cuda-targeted" / "expected_smoke.json").read_text(
            encoding="utf-8"
        )
    )

    assert "cuda" in expected["expected_engine_languages"]
    assert "kernels/stream_ops.cu" in expected["required_paths"]


def test_review_smoke_expected_engine_rules_match_retrieval(real_search_service) -> None:
    for fixture_dir in _fixture_dirs():
        expected = json.loads((fixture_dir / "expected_smoke.json").read_text(encoding="utf-8"))
        expected_engine_rules = expected.get("expected_engine_rules", {})
        assert isinstance(expected_engine_rules, dict)

        for relative_path, rule_nos in expected_engine_rules.items():
            assert isinstance(rule_nos, list)
            assert rule_nos
            assert all(isinstance(rule_no, str) and rule_no for rule_no in rule_nos)
            file_path = fixture_dir / "feature" / relative_path
            assert file_path.exists(), f"Missing expected engine rule fixture file: {file_path}"

            response = real_search_service.review_code(
                file_path.read_text(encoding="utf-8"),
                top_k=12,
                file_path=str(relative_path),
            )
            returned_rules = {result.rule_no for result in response.results}

            for rule_no in rule_nos:
                assert rule_no in returned_rules, (
                    f"{fixture_dir.name}:{relative_path} missing expected rule {rule_no}"
                )
