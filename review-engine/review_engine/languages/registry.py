from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from review_engine.models import LanguageMatch, LanguageRegistryEntry


class LanguageRegistry:
    def __init__(self) -> None:
        self._entries = _build_entries()

    def entries(self) -> dict[str, LanguageRegistryEntry]:
        return dict(self._entries)

    def reviewable_languages(self) -> list[str]:
        return sorted(
            language_id
            for language_id, entry in self._entries.items()
            if entry.reviewable and language_id != "shared"
        )

    def get(self, language_id: str) -> LanguageRegistryEntry:
        return self._entries[language_id]

    def is_reviewable_file(self, file_path: str, source_text: str | None = None) -> bool:
        return self.resolve(file_path=file_path, source_text=source_text).reviewable

    def resolve(
        self,
        *,
        file_path: str | None = None,
        source_text: str | None = None,
        language_id: str | None = None,
        profile_id: str | None = None,
        context_id: str | None = None,
        dialect_id: str | None = None,
        default_language_id: str = "cpp",
    ) -> LanguageMatch:
        if language_id:
            entry = self._entries.get(language_id, self._entries[default_language_id])
            return self._finalize_match(
                entry,
                match_source="explicit",
                file_path=file_path,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
            )

        path = file_path or ""
        source = source_text or ""
        explicit = (
            self._match_special_path(path)
            or self._match_by_filename(path)
            or self._match_by_extension(path)
            or self._match_by_shebang(source)
        )
        if explicit is not None:
            return self._finalize_match(
                explicit,
                match_source="classified",
                file_path=file_path,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
            )

        if file_path:
            return self._finalize_match(
                self._entries["unknown"],
                match_source="unmatched",
                file_path=file_path,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
            )

        entry = self._entries[default_language_id]
        return self._finalize_match(
            entry,
            match_source="default",
            file_path=file_path,
            profile_id=profile_id,
            context_id=context_id,
            dialect_id=dialect_id,
        )

    def _finalize_match(
        self,
        entry: LanguageRegistryEntry,
        *,
        match_source: str,
        file_path: str | None,
        profile_id: str | None,
        context_id: str | None,
        dialect_id: str | None,
    ) -> LanguageMatch:
        inferred_profile = entry.default_profile
        inferred_context = entry.default_context_id
        inferred_dialect = entry.default_dialect_id
        lowered_path = (file_path or "").replace("\\", "/").lower()

        if entry.language_id == "yaml":
            if "/.github/workflows/" in lowered_path or lowered_path.startswith(".github/workflows/"):
                inferred_profile = "github_actions"
                inferred_context = "github_actions"
            elif lowered_path.endswith(".gitlab-ci.yml") or lowered_path.endswith(".gitlab-ci.yaml"):
                inferred_profile = "gitlab_ci"
                inferred_context = "gitlab_ci"
            elif "charts/" in lowered_path and "/values" in lowered_path:
                inferred_profile = "helm_values"
                inferred_context = "helm_values"
            elif (
                lowered_path.startswith("k8s/")
                or lowered_path.startswith("manifests/")
                or "/k8s/" in lowered_path
                or "/manifests/" in lowered_path
            ):
                inferred_profile = "kubernetes_manifests"
                inferred_context = "kubernetes"
        elif entry.language_id == "sql":
            if any(
                fragment in lowered_path or lowered_path.startswith(fragment.removeprefix("/"))
                for fragment in ("/analytics/", "/warehouse/", "/dbt/")
            ):
                inferred_profile = "analytics_warehouse"
                inferred_context = "analytics"
            if any(token in lowered_path for token in ("postgres", "postgresql", "/pg/")):
                inferred_dialect = "postgresql"

        return LanguageMatch(
            language_id=entry.language_id,
            profile_id=profile_id or inferred_profile,
            context_id=context_id if context_id is not None else inferred_context,
            dialect_id=dialect_id if dialect_id is not None else inferred_dialect,
            reviewable=entry.reviewable,
            query_plugin_id=entry.query_plugin_id,
            match_source=match_source,
        )

    def _match_special_path(self, file_path: str) -> LanguageRegistryEntry | None:
        if not file_path:
            return None
        normalized = file_path.replace("\\", "/")
        for entry in self._entries.values():
            for pattern in entry.path_globs:
                if fnmatch(normalized, pattern):
                    return entry
        return None

    def _match_by_filename(self, file_path: str) -> LanguageRegistryEntry | None:
        if not file_path:
            return None
        name = Path(file_path).name
        for entry in self._entries.values():
            if name in entry.filenames:
                return entry
        return None

    def _match_by_extension(self, file_path: str) -> LanguageRegistryEntry | None:
        if not file_path:
            return None
        name = Path(file_path).name
        lowered_name = name.lower()
        for entry in self._entries.values():
            if any(lowered_name.endswith(ext) for ext in entry.file_extensions):
                return entry
        return None

    def _match_by_shebang(self, source_text: str) -> LanguageRegistryEntry | None:
        first_line = source_text.splitlines()[0].strip() if source_text else ""
        for entry in self._entries.values():
            if any(first_line.startswith(prefix) for prefix in entry.shebangs):
                return entry
        return None


def _build_entries() -> dict[str, LanguageRegistryEntry]:
    return {
        "shared": LanguageRegistryEntry(
            language_id="shared",
            display_name="Shared",
            query_plugin_id="shared",
            default_profile="default",
            reviewable=False,
        ),
        "unknown": LanguageRegistryEntry(
            language_id="unknown",
            display_name="Unknown",
            query_plugin_id="shared",
            default_profile="default",
            reviewable=False,
        ),
        "cpp": LanguageRegistryEntry(
            language_id="cpp",
            display_name="C++",
            query_plugin_id="cpp",
            file_extensions=[".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".h"],
            default_profile="default",
        ),
        "c": LanguageRegistryEntry(
            language_id="c",
            display_name="C",
            query_plugin_id="c",
            file_extensions=[".c"],
            default_profile="default",
        ),
        "python": LanguageRegistryEntry(
            language_id="python",
            display_name="Python",
            query_plugin_id="python",
            file_extensions=[".py"],
            default_profile="default",
        ),
        "typescript": LanguageRegistryEntry(
            language_id="typescript",
            display_name="TypeScript",
            query_plugin_id="typescript",
            file_extensions=[".ts", ".tsx"],
            default_profile="default",
        ),
        "javascript": LanguageRegistryEntry(
            language_id="javascript",
            display_name="JavaScript",
            query_plugin_id="javascript",
            file_extensions=[".js", ".jsx", ".mjs", ".cjs"],
            default_profile="default",
        ),
        "java": LanguageRegistryEntry(
            language_id="java",
            display_name="Java",
            query_plugin_id="java",
            file_extensions=[".java"],
            default_profile="default",
        ),
        "go": LanguageRegistryEntry(
            language_id="go",
            display_name="Go",
            query_plugin_id="go",
            file_extensions=[".go"],
            default_profile="default",
        ),
        "rust": LanguageRegistryEntry(
            language_id="rust",
            display_name="Rust",
            query_plugin_id="rust",
            file_extensions=[".rs"],
            default_profile="default",
        ),
        "bash": LanguageRegistryEntry(
            language_id="bash",
            display_name="Bash",
            query_plugin_id="bash",
            file_extensions=[".sh", ".bash"],
            filenames=[".bashrc", ".bash_profile", ".profile"],
            shebangs=["#!/bin/bash", "#!/usr/bin/env bash", "#!/bin/sh", "#!/usr/bin/env sh"],
            default_profile="default",
        ),
        "sql": LanguageRegistryEntry(
            language_id="sql",
            display_name="SQL",
            query_plugin_id="sql",
            file_extensions=[".sql"],
            default_profile="default",
            default_context_id="generic",
            default_dialect_id="generic",
        ),
        "yaml": LanguageRegistryEntry(
            language_id="yaml",
            display_name="YAML",
            query_plugin_id="yaml",
            file_extensions=[".yaml", ".yml"],
            filenames=[".gitlab-ci.yml", ".gitlab-ci.yaml"],
            path_globs=[
                ".github/workflows/*.yml",
                ".github/workflows/*.yaml",
                "*/.github/workflows/*.yml",
                "*/.github/workflows/*.yaml",
                "charts/**/values*.yaml",
                "charts/**/values*.yml",
                "*/charts/**/values*.yaml",
                "*/charts/**/values*.yml",
                "k8s/**/*.yaml",
                "k8s/**/*.yml",
                "manifests/**/*.yaml",
                "manifests/**/*.yml",
                "*/k8s/**/*.yaml",
                "*/k8s/**/*.yml",
                "*/manifests/**/*.yaml",
                "*/manifests/**/*.yml",
            ],
            default_profile="default",
            default_context_id="generic",
        ),
        "dockerfile": LanguageRegistryEntry(
            language_id="dockerfile",
            display_name="Dockerfile",
            query_plugin_id="dockerfile",
            file_extensions=[".dockerfile"],
            filenames=["Dockerfile"],
            path_globs=["Dockerfile.*", "*/Dockerfile.*", "*.dockerfile", "*/*.dockerfile"],
            default_profile="default",
        ),
    }


_REGISTRY = LanguageRegistry()


def get_language_registry() -> LanguageRegistry:
    return _REGISTRY
