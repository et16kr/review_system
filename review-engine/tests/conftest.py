from __future__ import annotations

from pathlib import Path

import pytest

from review_engine.config import Settings
from review_engine.ingest.build_records import ingest_all_sources
from review_engine.retrieve.search import GuidelineSearchService


@pytest.fixture
def fixture_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixture_settings(tmp_path, fixture_root: Path) -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        examples_dir=project_root / "examples",
        internal_guideline_path=fixture_root / "altibase_sample.md",
        cpp_core_html_cache=fixture_root / "cpp_core_sample.html",
        parsed_altibase_path=data_dir / "altibase_rules.json",
        parsed_cpp_core_path=data_dir / "cpp_core_rules.json",
        active_dataset_path=data_dir / "active_rules.json",
        source_priority_path=project_root / "data" / "source_priority.json",
        conflict_rules_path=project_root / "data" / "conflict_rules.json",
        disabled_cpp_rules_path=project_root / "data" / "disabled_cpp_core_rules.json",
        chroma_path=data_dir / "chroma",
        collection_name="test_guideline_records",
        review_profiles_path=project_root / "data" / "review_profiles.json",
    )


@pytest.fixture(scope="session")
def real_settings(tmp_path_factory) -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = tmp_path_factory.mktemp("real_guidelines")
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        examples_dir=project_root / "examples",
        internal_guideline_path=project_root / "CODING_CONVENTION.md",
        cpp_core_html_cache=project_root / "data" / "cpp_core_guidelines.html",
        parsed_altibase_path=data_dir / "altibase_rules.json",
        parsed_cpp_core_path=data_dir / "cpp_core_rules.json",
        active_dataset_path=data_dir / "active_rules.json",
        source_priority_path=project_root / "data" / "source_priority.json",
        conflict_rules_path=project_root / "data" / "conflict_rules.json",
        disabled_cpp_rules_path=project_root / "data" / "disabled_cpp_core_rules.json",
        chroma_path=data_dir / "chroma",
        collection_name="real_test_guideline_records",
        review_profiles_path=project_root / "data" / "review_profiles.json",
    )


@pytest.fixture(scope="session")
def real_search_service(real_settings: Settings) -> GuidelineSearchService:
    ingest_all_sources(real_settings)
    return GuidelineSearchService(real_settings)
