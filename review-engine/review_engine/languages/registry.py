from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path

from review_engine.models import LanguageMatch, LanguageRegistryEntry

_SPRING_TOKENS = (
    "org.springframework",
    "@restcontroller",
    "@controller",
    "@service",
    "@repository",
    "@component",
    "@configuration",
    "@transactional",
    "@controlleradvice",
    "@configurationproperties",
    "springapplication.run",
)
_FASTAPI_TOKENS = (
    "from fastapi import",
    "import fastapi",
    "fastapi(",
    "apirouter(",
    "@app.get(",
    "@app.post(",
    "@app.put(",
    "@app.patch(",
    "@app.delete(",
    "@router.get(",
    "@router.post(",
    "@router.put(",
    "@router.patch(",
    "@router.delete(",
)
_DJANGO_TOKENS = (
    "from django",
    "import django",
    "from rest_framework",
    "import rest_framework",
)
_TOKIO_TOKENS = (
    "tokio::",
    "#[tokio::",
    "tokio_stream",
    "tokio_util",
)
_CUDA_ASYNC_TOKENS = (
    "cudamemcpyasync",
    "cudamemsetasync",
    "cudamemprefetchasync",
    "cudastreamcreate",
    "cudastreamwaitevent",
    "cudaeventrecord",
    "cudalaunchhostfunc",
    "cudagraph",
)
_CUDA_PIPELINE_ASYNC_TOKENS = (
    "#include <cuda/pipeline>",
    "#include <cuda/barrier>",
    "cuda::pipeline",
    "cuda::make_pipeline",
    "cuda::pipeline_shared_state",
    "cuda::memcpy_async",
    "cuda::barrier",
    "__pipeline_memcpy_async",
    "__pipeline_commit",
    "__pipeline_wait_prior",
    "producer_acquire",
    "producer_commit",
    "consumer_wait",
    "consumer_release",
    "cp.async",
    "mbarrier",
)
_CUDA_THREAD_BLOCK_CLUSTER_TOKENS = (
    "__cluster_dims__",
    "cluster_group",
    "this_cluster",
    "cluster.sync",
    "cluster.barrier_arrive",
    "cluster.barrier_wait",
    "map_shared_rank",
    "query_shared_rank",
    "cudalaunchkernelex",
    "cudalaunchattributeclusterdimension",
    "distributed shared memory",
)
_CUDA_TMA_TOKENS = (
    "cutensormap",
    "cutensormapencode",
    "cp.async.bulk.tensor",
    "cp.reduce.async.bulk.tensor",
    "cp.async.bulk.prefetch.tensor",
    "cp_async_bulk_tensor",
    "cp_reduce_async_bulk_tensor",
    "tensormap_replace",
    "tensormap_cp_fenceproxy",
    "tensormap_copy_fenceproxy",
    "fence_proxy_tensormap_generic",
)
_CUDA_MULTI_GPU_TOKENS = (
    "cudasetdevice",
    "cudagetdevicecount",
    "cudadeviceenablepeeraccess",
    "cudamemcpypeer",
    "cudamemcpypeerasync",
    "cudaipc",
    "nccl",
)
_CUDA_TENSOR_CORE_TOKENS = (
    "nvcuda::wmma",
    "wmma::fragment",
    "wmma::mma_sync",
    "wmma::load_matrix_sync",
    "wmma::store_matrix_sync",
    "mma.sync",
    "ldmatrix",
)
_CUDA_WGMMA_TOKENS = (
    "wgmma.mma_async",
    "wgmma.commit_group",
    "wgmma.wait_group",
    "wgmma.fence",
)
_CUDA_COOPERATIVE_GROUPS_TOKENS = (
    "cooperative_groups",
    "cg::this_thread_block",
    "cg::this_grid",
    "tiled_partition",
    "labeled_partition",
    "binary_partition",
    "thread_block_tile",
    "grid.sync",
    "coalesced_group",
)
_NEXT_IMPORT_TOKENS = (
    "from 'next",
    'from "next',
    "from 'next/",
    'from "next/',
    "next/",
)
_REACT_TYPESCRIPT_TOKENS = (
    "from 'react'",
    'from "react"',
    "from 'react/",
    'from "react/',
    "useeffect(",
    "usestate(",
    "usememo(",
    "usecallback(",
    "useref(",
    "jsx",
    "tsx",
)
_SCHEMA_PATH_TOKENS = (
    "/schema/",
    "/schemas/",
    "schema.",
    "openapi",
    "swagger",
)
_PRODUCT_CONFIG_TOKENS = (
    "/config/",
    "/configs/",
    "/settings/",
    "/environments/",
    "/deploy/",
    "/deployment/",
    "application.yml",
    "application.yaml",
    "config.yml",
    "config.yaml",
    "settings.yml",
    "settings.yaml",
)
_DBT_PATH_TOKENS = (
    "/dbt/",
    "/snapshots/",
    "/macros/",
    "/seeds/",
)
_DBT_SOURCE_TOKENS = (
    "{{ ref(",
    '{{ ref("',
    "{{ source(",
    '{{ source("',
    "{{ config(",
    '{{ config("',
    "is_incremental()",
)
_MIGRATION_PATH_TOKENS = (
    "/migration/",
    "/migrations/",
    "/alembic/",
    "/flyway/",
    "/liquibase/",
    "/db/migrate/",
)


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
        default_profile_id: str | None = None,
    ) -> LanguageMatch:
        if language_id:
            entry = self._entries.get(language_id, self._entries[default_language_id])
            return self._finalize_match(
                entry,
                match_source="explicit",
                file_path=file_path,
                source_text=source_text,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
                default_language_id=default_language_id,
                default_profile_id=default_profile_id,
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
                source_text=source_text,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
                default_language_id=default_language_id,
                default_profile_id=default_profile_id,
            )

        if file_path:
            return self._finalize_match(
                self._entries["unknown"],
                match_source="unmatched",
                file_path=file_path,
                source_text=source_text,
                profile_id=profile_id,
                context_id=context_id,
                dialect_id=dialect_id,
                default_language_id=default_language_id,
                default_profile_id=default_profile_id,
            )

        entry = self._entries[default_language_id]
        return self._finalize_match(
            entry,
            match_source="default",
            file_path=file_path,
            source_text=source_text,
            profile_id=profile_id,
            context_id=context_id,
            dialect_id=dialect_id,
            default_language_id=default_language_id,
            default_profile_id=default_profile_id,
        )

    def _finalize_match(
        self,
        entry: LanguageRegistryEntry,
        *,
        match_source: str,
        file_path: str | None,
        source_text: str | None,
        profile_id: str | None,
        context_id: str | None,
        dialect_id: str | None,
        default_language_id: str,
        default_profile_id: str | None,
    ) -> LanguageMatch:
        inferred_profile = entry.default_profile
        inferred_context = entry.default_context_id
        inferred_dialect = entry.default_dialect_id
        lowered_path = _normalize_path(file_path)
        lowered_source = (source_text or "").lower()

        if entry.language_id == "yaml":
            yaml_profile, yaml_context = _infer_yaml_runtime(lowered_path, lowered_source)
            inferred_profile = yaml_profile
            inferred_context = yaml_context
        elif entry.language_id == "sql":
            inferred_profile, inferred_context, inferred_dialect = _infer_sql_runtime(
                lowered_path,
                lowered_source,
                default_profile=inferred_profile,
                default_context=inferred_context,
                default_dialect=inferred_dialect,
            )
        elif entry.language_id == "java" and _looks_like_spring_java(lowered_path, lowered_source):
            inferred_profile = "spring_backend"
        elif entry.language_id == "python":
            inferred_profile = _infer_python_profile(
                lowered_path,
                lowered_source,
                default_profile=inferred_profile,
            )
        elif entry.language_id == "cuda":
            inferred_profile = _infer_cuda_profile(
                lowered_source,
                default_profile=inferred_profile,
            )
        elif entry.language_id in {"typescript", "javascript"}:
            next_context = _infer_nextjs_context(lowered_path, lowered_source)
            if next_context is not None:
                inferred_profile = "nextjs_frontend"
                inferred_context = next_context
            elif entry.language_id == "typescript" and _looks_like_react_typescript(
                lowered_path,
                lowered_source,
            ):
                inferred_profile = "frontend_strict"
        elif entry.language_id == "rust" and _looks_like_tokio_rust(lowered_source):
            inferred_profile = "tokio_async"

        selected_profile = profile_id or _apply_configured_default_profile(
            entry=entry,
            inferred_profile=inferred_profile,
            default_language_id=default_language_id,
            default_profile_id=default_profile_id,
        )
        return LanguageMatch(
            language_id=entry.language_id,
            profile_id=selected_profile,
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
        best_match: tuple[int, LanguageRegistryEntry] | None = None
        for entry in self._entries.values():
            for ext in entry.file_extensions:
                if not lowered_name.endswith(ext):
                    continue
                if best_match is None or len(ext) > best_match[0]:
                    best_match = (len(ext), entry)
        return best_match[1] if best_match is not None else None

    def _match_by_shebang(self, source_text: str) -> LanguageRegistryEntry | None:
        first_line = source_text.splitlines()[0].strip() if source_text else ""
        for entry in self._entries.values():
            if any(first_line.startswith(prefix) for prefix in entry.shebangs):
                return entry
        return None


def _normalize_path(file_path: str | None) -> str:
    return (file_path or "").replace("\\", "/").lower()


def _apply_configured_default_profile(
    *,
    entry: LanguageRegistryEntry,
    inferred_profile: str,
    default_language_id: str,
    default_profile_id: str | None,
) -> str:
    if (
        default_profile_id
        and entry.language_id == default_language_id
        and inferred_profile == entry.default_profile
    ):
        return default_profile_id
    return inferred_profile


def _has_any_token(value: str, tokens: tuple[str, ...]) -> bool:
    return any(token in value for token in tokens)


def _path_parts(lowered_path: str) -> tuple[str, ...]:
    return tuple(part for part in lowered_path.strip("/").split("/") if part)


def _looks_like_spring_java(lowered_path: str, lowered_source: str) -> bool:
    if not lowered_path.endswith(".java"):
        return False
    if _has_any_token(lowered_source, _SPRING_TOKENS):
        return True
    return any(part in lowered_path for part in ("/controller/", "/service/", "/repository/"))


def _infer_python_profile(
    lowered_path: str,
    lowered_source: str,
    *,
    default_profile: str,
) -> str:
    if _has_any_token(lowered_source, _FASTAPI_TOKENS):
        return "fastapi_service"
    if _has_any_token(lowered_source, _DJANGO_TOKENS):
        return "django_service"
    if Path(lowered_path).name in {"manage.py", "settings.py", "urls.py", "wsgi.py", "asgi.py"}:
        return "django_service"
    return default_profile


def _looks_like_tokio_rust(lowered_source: str) -> bool:
    return _has_any_token(lowered_source, _TOKIO_TOKENS)


def _infer_cuda_profile(
    lowered_source: str,
    *,
    default_profile: str,
) -> str:
    if _has_any_token(lowered_source, _CUDA_MULTI_GPU_TOKENS):
        return "cuda_multigpu"
    if _has_any_token(lowered_source, _CUDA_TMA_TOKENS):
        return "cuda_tma"
    if _has_any_token(lowered_source, _CUDA_WGMMA_TOKENS):
        return "cuda_wgmma"
    if _has_any_token(lowered_source, _CUDA_TENSOR_CORE_TOKENS):
        return "cuda_tensor_core"
    if _has_any_token(lowered_source, _CUDA_PIPELINE_ASYNC_TOKENS):
        return "cuda_pipeline_async"
    if _has_any_token(lowered_source, _CUDA_THREAD_BLOCK_CLUSTER_TOKENS):
        return "cuda_thread_block_cluster"
    if _has_any_token(lowered_source, _CUDA_COOPERATIVE_GROUPS_TOKENS):
        return "cuda_cooperative_groups"
    if _has_any_token(lowered_source, _CUDA_ASYNC_TOKENS):
        return "cuda_async_runtime"
    return default_profile


def _looks_like_react_typescript(lowered_path: str, lowered_source: str) -> bool:
    if not lowered_path.endswith((".tsx", ".ts")):
        return False
    if _has_any_token(lowered_source, _REACT_TYPESCRIPT_TOKENS):
        return True
    return any(part in lowered_path for part in ("/components/", "/pages/", "/ui/"))


def _infer_nextjs_context(lowered_path: str, lowered_source: str) -> str | None:
    filename = Path(lowered_path).name
    is_next_path = filename.startswith("next.config.") or _has_any_token(lowered_source, _NEXT_IMPORT_TOKENS)
    app_router_path = any(
        token in lowered_path
        for token in (
            "/app/",
            "/src/app/",
            "/middleware.",
        )
    ) or lowered_path.startswith("app/")
    pages_router_path = any(
        token in lowered_path
        for token in (
            "/pages/",
            "/src/pages/",
            "/pages/api/",
        )
    ) or lowered_path.startswith("pages/")
    app_router_filename = filename in {
        "page.tsx",
        "page.jsx",
        "page.ts",
        "page.js",
        "layout.tsx",
        "layout.jsx",
        "layout.ts",
        "layout.js",
        "route.ts",
        "route.js",
        "middleware.ts",
        "middleware.js",
    }
    pages_router_filename = filename in {
        "_app.tsx",
        "_app.jsx",
        "_app.ts",
        "_app.js",
        "_document.tsx",
        "_document.jsx",
        "_document.ts",
        "_document.js",
        "_error.tsx",
        "_error.jsx",
        "_error.ts",
        "_error.js",
    }

    if not is_next_path and not app_router_filename and not pages_router_filename:
        return None
    if app_router_filename or (is_next_path and app_router_path):
        return "app_router"
    if pages_router_filename or (is_next_path and pages_router_path):
        return "pages_router"
    return None


def _infer_yaml_runtime(lowered_path: str, lowered_source: str) -> tuple[str, str | None]:
    if "/.github/workflows/" in lowered_path or lowered_path.startswith(".github/workflows/"):
        return "github_actions", "github_actions"
    if lowered_path.endswith(".gitlab-ci.yml") or lowered_path.endswith(".gitlab-ci.yaml"):
        return "gitlab_ci", "gitlab_ci"
    if "charts/" in lowered_path and "/values" in lowered_path:
        return "helm_values", "helm_values"
    if (
        lowered_path.startswith("k8s/")
        or lowered_path.startswith("manifests/")
        or "/k8s/" in lowered_path
        or "/manifests/" in lowered_path
    ):
        return "kubernetes_manifests", "kubernetes"
    if _has_any_token(lowered_path, _SCHEMA_PATH_TOKENS) or "openapi:" in lowered_source:
        return "schema_config", "schema_config"
    if _has_any_token(lowered_path, _PRODUCT_CONFIG_TOKENS):
        return "product_config", "product_config"
    return "default", "generic"


def _infer_sql_runtime(
    lowered_path: str,
    lowered_source: str,
    *,
    default_profile: str,
    default_context: str | None,
    default_dialect: str | None,
) -> tuple[str, str | None, str | None]:
    profile = default_profile
    context = default_context
    dialect = default_dialect
    path_parts = _path_parts(lowered_path)

    if (
        _has_any_token(lowered_path, _DBT_PATH_TOKENS)
        or _has_any_token(lowered_source, _DBT_SOURCE_TOKENS)
        or any(part in {"dbt", "snapshots", "macros", "seeds"} for part in path_parts)
    ):
        profile = "dbt_warehouse"
        context = "analytics"
    elif any(part in {"analytics", "warehouse"} for part in path_parts):
        profile = "analytics_warehouse"
        context = "analytics"
    elif (
        _has_any_token(lowered_path, _MIGRATION_PATH_TOKENS)
        or any(part in {"migration", "migrations", "alembic", "flyway", "liquibase"} for part in path_parts)
        or "db/migrate/" in lowered_path
        or re.search(r"(^|/)(v\d+__|[\d_]+.*migration).*\.sql$", lowered_path)
    ):
        profile = "migration_sql"
        context = "generic"

    if any(token in lowered_path for token in ("postgres", "postgresql", "/pg/")) or any(
        token in lowered_source for token in ("ilike", "jsonb", "returning", "on conflict", "::")
    ):
        dialect = "postgresql"
    elif any(token in lowered_path for token in ("mysql", "mariadb")) or any(
        token in lowered_source for token in ("auto_increment", "engine=", "unsigned", "`")
    ):
        dialect = "mysql"
    elif "sqlite" in lowered_path or any(
        token in lowered_source for token in ("pragma ", "without rowid", "sqlite_")
    ):
        dialect = "sqlite"
    elif "oracle" in lowered_path or any(
        token in lowered_source for token in ("varchar2", "number(", " from dual", "sequence ")
    ):
        dialect = "oracle"
    else:
        dialect = dialect or "generic"

    return profile, context, dialect


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
        "markdown": LanguageRegistryEntry(
            language_id="markdown",
            display_name="Markdown",
            query_plugin_id="shared",
            file_extensions=[".md", ".mdx", ".markdown", ".rst", ".adoc"],
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
        "cuda": LanguageRegistryEntry(
            language_id="cuda",
            display_name="CUDA",
            query_plugin_id="cuda",
            file_extensions=[".cu", ".cuh"],
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
