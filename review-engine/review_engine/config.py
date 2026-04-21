from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _split_path_env(name: str) -> tuple[Path, ...]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return ()
    return tuple(
        Path(item).expanduser().resolve()
        for item in raw.split(os.pathsep)
        if item.strip()
    )


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    examples_dir: Path
    internal_guideline_path: Path | None = None
    cpp_core_html_cache: Path | None = None
    parsed_altibase_path: Path | None = None
    parsed_cpp_core_path: Path | None = None
    active_dataset_path: Path | None = None
    source_priority_path: Path | None = None
    conflict_rules_path: Path | None = None
    disabled_cpp_rules_path: Path | None = None
    chroma_path: Path | None = None
    collection_name: str = "guideline_records"
    reference_dataset_path: Path | None = None
    excluded_dataset_path: Path | None = None
    review_profiles_path: Path | None = None
    active_collection_name: str | None = None
    reference_collection_name: str | None = None
    excluded_collection_name: str | None = None
    chroma_host: str | None = None
    chroma_port: int | None = None
    embedding_provider: str = "hashing"
    public_rule_root: Path | None = None
    extension_rule_roots: tuple[Path, ...] = ()
    default_profile_id: str = "default"
    default_language_id: str = "cpp"
    strict_extension_loading: bool = True
    prompt_root: Path | None = None
    extension_prompt_roots: tuple[Path, ...] = ()
    extension_entry_point_group: str = "review_engine.rule_extensions"

    def dataset_path(self, kind: str) -> Path:
        if kind == "active":
            return self.active_dataset_path or (self.data_dir / "active_guideline_records.json")
        if kind == "reference":
            return self.reference_dataset_path or (
                self.data_dir / "reference_guideline_records.json"
            )
        if kind == "excluded":
            return self.excluded_dataset_path or (
                self.data_dir / "excluded_guideline_records.json"
            )
        raise ValueError(f"Unsupported dataset kind: {kind}")

    def collection_for(self, kind: str) -> str:
        if kind == "active":
            return self.active_collection_name or f"{self.collection_name}_active"
        if kind == "reference":
            return self.reference_collection_name or f"{self.collection_name}_reference"
        if kind == "excluded":
            return self.excluded_collection_name or f"{self.collection_name}_excluded"
        raise ValueError(f"Unsupported collection kind: {kind}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    public_rule_root = Path(
        os.getenv("REVIEW_ENGINE_PUBLIC_RULE_ROOT", project_root / "rules" / "cpp")
    ).expanduser().resolve()
    prompt_root = Path(
        os.getenv("REVIEW_ENGINE_PROMPT_ROOT", project_root / "prompts")
    ).expanduser().resolve()
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        examples_dir=project_root / "examples",
        internal_guideline_path=None,
        cpp_core_html_cache=data_dir / "cpp_core_guidelines.html",
        parsed_altibase_path=data_dir / "altibase_coding_convention_rules.json",
        parsed_cpp_core_path=data_dir / "cpp_core_guidelines_rules.json",
        active_dataset_path=data_dir / "active_guideline_records.json",
        source_priority_path=data_dir / "source_priority.json",
        conflict_rules_path=data_dir / "conflict_rules.json",
        disabled_cpp_rules_path=data_dir / "disabled_cpp_core_rules.json",
        chroma_path=data_dir / "chroma",
        collection_name="guideline_records",
        reference_dataset_path=data_dir / "reference_guideline_records.json",
        excluded_dataset_path=data_dir / "excluded_guideline_records.json",
        review_profiles_path=data_dir / "review_profiles.json",
        active_collection_name="guideline_rules_active",
        reference_collection_name="guideline_rules_reference",
        excluded_collection_name="guideline_rules_excluded",
        chroma_host=os.getenv("REVIEW_ENGINE_CHROMA_HOST"),
        chroma_port=int(os.getenv("REVIEW_ENGINE_CHROMA_PORT", "8000")),
        embedding_provider=os.getenv("REVIEW_ENGINE_EMBEDDING_PROVIDER", "hashing"),
        public_rule_root=public_rule_root,
        extension_rule_roots=_split_path_env("REVIEW_ENGINE_EXTENSION_RULE_ROOTS"),
        default_profile_id=os.getenv("REVIEW_ENGINE_DEFAULT_PROFILE", "default"),
        default_language_id="cpp",
        strict_extension_loading=os.getenv("REVIEW_ENGINE_STRICT_EXTENSION_LOADING", "1")
        not in {"0", "false", "False"},
        prompt_root=prompt_root,
        extension_prompt_roots=_split_path_env("REVIEW_ENGINE_EXTENSION_PROMPT_ROOTS"),
    )


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
