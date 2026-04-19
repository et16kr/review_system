from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    examples_dir: Path
    internal_guideline_path: Path
    cpp_core_html_cache: Path
    parsed_altibase_path: Path
    parsed_cpp_core_path: Path
    active_dataset_path: Path
    source_priority_path: Path
    conflict_rules_path: Path
    disabled_cpp_rules_path: Path
    chroma_path: Path
    collection_name: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        examples_dir=project_root / "examples",
        internal_guideline_path=project_root / "CODING_CONVENTION.md",
        cpp_core_html_cache=data_dir / "cpp_core_guidelines.html",
        parsed_altibase_path=data_dir / "altibase_coding_convention_rules.json",
        parsed_cpp_core_path=data_dir / "cpp_core_guidelines_rules.json",
        active_dataset_path=data_dir / "active_guideline_records.json",
        source_priority_path=data_dir / "source_priority.json",
        conflict_rules_path=data_dir / "conflict_rules.json",
        disabled_cpp_rules_path=data_dir / "disabled_cpp_core_rules.json",
        chroma_path=data_dir / "chroma",
        collection_name="guideline_records",
    )


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
