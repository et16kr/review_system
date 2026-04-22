from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path


@dataclass(frozen=True)
class LanguageMatch:
    language_id: str
    profile_id: str
    context_id: str | None = None
    dialect_id: str | None = None
    reviewable: bool = True
    match_source: str = "default"


class LanguageRegistry:
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
            return self._finalize(
                language_id=language_id,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
                match_source="explicit",
            )

        path = (file_path or "").replace("\\", "/")
        lowered = path.lower()
        source = source_text or ""
        if "/.github/workflows/" in lowered or lowered.startswith(".github/workflows/"):
            return LanguageMatch(
                "yaml",
                profile_id or "github_actions",
                "github_actions",
                dialect_id,
                match_source="classified",
            )
        if lowered.endswith(".gitlab-ci.yml") or lowered.endswith(".gitlab-ci.yaml"):
            return LanguageMatch(
                "yaml",
                profile_id or "gitlab_ci",
                "gitlab_ci",
                dialect_id,
                match_source="classified",
            )
        if "charts/" in lowered and "/values" in lowered:
            return LanguageMatch(
                "yaml",
                profile_id or "helm_values",
                "helm_values",
                dialect_id,
                match_source="classified",
            )
        if (
            lowered.startswith("k8s/")
            or lowered.startswith("manifests/")
            or "/k8s/" in lowered
            or "/manifests/" in lowered
        ):
            return LanguageMatch(
                "yaml",
                profile_id or "kubernetes_manifests",
                "kubernetes",
                dialect_id,
                match_source="classified",
            )
        if (
            Path(path).name == "Dockerfile"
            or fnmatch(Path(path).name, "Dockerfile.*")
            or lowered.endswith(".dockerfile")
        ):
            return LanguageMatch(
                "dockerfile",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )

        suffix = Path(path).suffix.lower()
        if suffix == ".c":
            return LanguageMatch(
                "c",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix in {".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".h"}:
            return LanguageMatch(
                "cpp",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix == ".py":
            return LanguageMatch(
                "python",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix in {".ts", ".tsx"}:
            return LanguageMatch(
                "typescript",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
            return LanguageMatch(
                "javascript",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix == ".java":
            return LanguageMatch(
                "java",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix == ".go":
            return LanguageMatch(
                "go",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix == ".rs":
            return LanguageMatch(
                "rust",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix in {".sh", ".bash"} or Path(path).name in {".bashrc", ".bash_profile", ".profile"}:
            return LanguageMatch(
                "bash",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix == ".sql":
            inferred_profile = profile_id or "default"
            inferred_context = context_id or "generic"
            inferred_dialect = dialect_id or "generic"
            if any(
                fragment in lowered or lowered.startswith(fragment.removeprefix("/"))
                for fragment in ("/analytics/", "/warehouse/", "/dbt/")
            ):
                inferred_profile = profile_id or "analytics_warehouse"
                inferred_context = context_id or "analytics"
            if any(token in lowered for token in ("postgres", "postgresql", "/pg/")):
                inferred_dialect = dialect_id or "postgresql"
            return LanguageMatch(
                "sql",
                inferred_profile,
                inferred_context,
                inferred_dialect,
                match_source="classified",
            )
        if suffix in {".yaml", ".yml"}:
            return LanguageMatch(
                "yaml",
                profile_id or "default",
                context_id or "generic",
                dialect_id,
                match_source="classified",
            )

        first_line = source.splitlines()[0].strip() if source else ""
        if any(
            first_line.startswith(prefix)
            for prefix in ("#!/bin/bash", "#!/usr/bin/env bash", "#!/bin/sh", "#!/usr/bin/env sh")
        ):
            return LanguageMatch(
                "bash",
                profile_id or "default",
                context_id,
                dialect_id,
                match_source="classified",
            )

        if file_path:
            return LanguageMatch(
                language_id="unknown",
                profile_id=profile_id or "default",
                context_id=context_id,
                dialect_id=dialect_id,
                reviewable=False,
                match_source="unmatched",
            )

        return self._finalize(
            language_id=default_language_id,
            profile_id=profile_id,
            context_id=context_id,
            dialect_id=dialect_id,
            match_source="default",
        )

    def _finalize(
        self,
        *,
        language_id: str,
        profile_id: str | None,
        context_id: str | None,
        dialect_id: str | None,
        match_source: str,
    ) -> LanguageMatch:
        if language_id == "sql":
            return LanguageMatch(
                language_id=language_id,
                profile_id=profile_id or "default",
                context_id=context_id or "generic",
                dialect_id=dialect_id or "generic",
                match_source=match_source,
            )
        if language_id == "yaml":
            return LanguageMatch(
                language_id=language_id,
                profile_id=profile_id or "default",
                context_id=context_id or "generic",
                dialect_id=dialect_id,
                match_source=match_source,
            )
        return LanguageMatch(
            language_id=language_id,
            profile_id=profile_id or "default",
            context_id=context_id,
            dialect_id=dialect_id,
            match_source=match_source,
        )


_REGISTRY = LanguageRegistry()


def get_language_registry() -> LanguageRegistry:
    return _REGISTRY
