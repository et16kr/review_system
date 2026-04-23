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
    cpp_core_html_cache: Path | None = None
    parsed_cpp_core_path: Path | None = None
    active_dataset_path: Path | None = None
    chroma_path: Path | None = None
    collection_name: str = "guideline_records"
    reference_dataset_path: Path | None = None
    excluded_dataset_path: Path | None = None
    active_collection_name: str | None = None
    reference_collection_name: str | None = None
    excluded_collection_name: str | None = None
    chroma_host: str | None = None
    chroma_port: int | None = None
    embedding_provider: str = "hashing"
    public_rule_root: Path | None = None
    rule_source_root: Path | None = None
    extension_rule_roots: tuple[Path, ...] = ()
    default_profile_id: str = "default"
    default_language_id: str = "cpp"
    strict_extension_loading: bool = True
    prompt_root: Path | None = None
    extension_prompt_roots: tuple[Path, ...] = ()
    extension_entry_point_group: str = "review_engine.rule_extensions"

    def dataset_path(self, kind: str, language_id: str | None = None) -> Path:
        language_key = language_id or self.default_language_id
        if kind == "active" and (language_id is None or language_key == self.default_language_id):
            return self.active_dataset_path or (self.data_dir / "active_guideline_records.json")
        if kind == "reference" and (language_id is None or language_key == self.default_language_id):
            return self.reference_dataset_path or (
                self.data_dir / "reference_guideline_records.json"
            )
        if kind == "excluded" and (language_id is None or language_key == self.default_language_id):
            return self.excluded_dataset_path or (
                self.data_dir / "excluded_guideline_records.json"
            )
        if kind not in {"active", "reference", "excluded"}:
            raise ValueError(f"Unsupported dataset kind: {kind}")
        return self.data_dir / f"{language_key}_{kind}_guideline_records.json"

    def collection_for(self, kind: str, language_id: str | None = None) -> str:
        language_key = language_id or self.default_language_id
        if kind == "active" and (language_id is None or language_key == self.default_language_id):
            return self.active_collection_name or f"{self.collection_name}_active_{language_key}"
        if kind == "reference" and (language_id is None or language_key == self.default_language_id):
            return self.reference_collection_name or f"{self.collection_name}_reference_{language_key}"
        if kind == "excluded" and (language_id is None or language_key == self.default_language_id):
            return self.excluded_collection_name or f"{self.collection_name}_excluded_{language_key}"
        if kind not in {"active", "reference", "excluded"}:
            raise ValueError(f"Unsupported collection kind: {kind}")
        return f"{self.collection_name}_{kind}_{language_key}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[1]
    data_dir = project_root / "data"
    public_rule_root = Path(
        os.getenv("REVIEW_ENGINE_PUBLIC_RULE_ROOT", project_root / "rules")
    ).expanduser().resolve()
    rule_source_root = Path(
        os.getenv("REVIEW_ENGINE_RULE_SOURCE_ROOT", project_root / "rule_sources")
    ).expanduser().resolve()
    prompt_root = Path(
        os.getenv("REVIEW_ENGINE_PROMPT_ROOT", project_root / "prompts")
    ).expanduser().resolve()
    default_language_id = os.getenv("REVIEW_ENGINE_DEFAULT_LANGUAGE", "cpp")
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        examples_dir=project_root / "examples",
        cpp_core_html_cache=data_dir / "cpp_core_guidelines.html",
        parsed_cpp_core_path=data_dir / "cpp_core_guidelines_rules.json",
        active_dataset_path=data_dir / "active_guideline_records.json",
        chroma_path=data_dir / "chroma",
        collection_name="guideline_records",
        reference_dataset_path=data_dir / "reference_guideline_records.json",
        excluded_dataset_path=data_dir / "excluded_guideline_records.json",
        active_collection_name=f"guideline_rules_active_{default_language_id}",
        reference_collection_name=f"guideline_rules_reference_{default_language_id}",
        excluded_collection_name=f"guideline_rules_excluded_{default_language_id}",
        chroma_host=os.getenv("REVIEW_ENGINE_CHROMA_HOST"),
        chroma_port=int(os.getenv("REVIEW_ENGINE_CHROMA_PORT", "8000")),
        embedding_provider=os.getenv("REVIEW_ENGINE_EMBEDDING_PROVIDER", "hashing"),
        public_rule_root=public_rule_root,
        rule_source_root=rule_source_root,
        extension_rule_roots=_split_path_env("REVIEW_ENGINE_EXTENSION_RULE_ROOTS"),
        default_profile_id=os.getenv("REVIEW_ENGINE_DEFAULT_PROFILE", "default"),
        default_language_id=default_language_id,
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
