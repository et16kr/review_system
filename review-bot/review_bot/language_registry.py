from __future__ import annotations

import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

_MARKDOWN_EXTENSIONS = {".md", ".mdx", ".markdown", ".rst", ".adoc"}
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

        path = _normalize_path(file_path)
        source = source_text or ""
        source_lower = source.lower()
        name = Path(path).name

        if "/.github/workflows/" in path or path.startswith(".github/workflows/"):
            return LanguageMatch(
                "yaml",
                profile_id or "github_actions",
                context_id or "github_actions",
                dialect_id,
                match_source="classified",
            )
        if path.endswith(".gitlab-ci.yml") or path.endswith(".gitlab-ci.yaml"):
            return LanguageMatch(
                "yaml",
                profile_id or "gitlab_ci",
                context_id or "gitlab_ci",
                dialect_id,
                match_source="classified",
            )
        if "charts/" in path and "/values" in path:
            return LanguageMatch(
                "yaml",
                profile_id or "helm_values",
                context_id or "helm_values",
                dialect_id,
                match_source="classified",
            )
        if (
            path.startswith("k8s/")
            or path.startswith("manifests/")
            or "/k8s/" in path
            or "/manifests/" in path
        ):
            return LanguageMatch(
                "yaml",
                profile_id or "kubernetes_manifests",
                context_id or "kubernetes",
                dialect_id,
                match_source="classified",
            )
        if name == "dockerfile" or fnmatch(name, "dockerfile.*") or path.endswith(".dockerfile"):
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
        if suffix in {".cu", ".cuh"}:
            inferred_profile = profile_id or _infer_cuda_profile(source_lower)
            return LanguageMatch(
                "cuda",
                inferred_profile,
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix in _MARKDOWN_EXTENSIONS:
            return LanguageMatch(
                "markdown",
                profile_id or "default",
                context_id,
                dialect_id,
                reviewable=False,
                match_source="classified",
            )
        if suffix == ".py":
            inferred_profile = profile_id or _infer_python_profile(path, source_lower)
            return LanguageMatch(
                "python",
                inferred_profile,
                context_id,
                dialect_id,
                match_source="classified",
            )
        if suffix in {".ts", ".tsx"}:
            inferred_profile = profile_id or "default"
            inferred_context = context_id
            next_context = _infer_nextjs_context(path, source_lower)
            if next_context is not None:
                inferred_profile = profile_id or "nextjs_frontend"
                inferred_context = context_id or next_context
            elif _looks_like_react_typescript(path, source_lower):
                inferred_profile = profile_id or "frontend_strict"
            return LanguageMatch(
                "typescript",
                inferred_profile,
                inferred_context,
                dialect_id,
                match_source="classified",
            )
        if suffix in {".js", ".jsx", ".mjs", ".cjs"}:
            inferred_profile = profile_id or "default"
            inferred_context = context_id
            next_context = _infer_nextjs_context(path, source_lower)
            if next_context is not None:
                inferred_profile = profile_id or "nextjs_frontend"
                inferred_context = context_id or next_context
            return LanguageMatch(
                "javascript",
                inferred_profile,
                inferred_context,
                dialect_id,
                match_source="classified",
            )
        if suffix == ".java":
            inferred_profile = profile_id or "default"
            if _looks_like_spring_java(path, source_lower):
                inferred_profile = profile_id or "spring_backend"
            return LanguageMatch(
                "java",
                inferred_profile,
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
            inferred_profile = profile_id or "default"
            if _looks_like_tokio_rust(source_lower):
                inferred_profile = profile_id or "tokio_async"
            return LanguageMatch(
                "rust",
                inferred_profile,
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
            inferred_profile, inferred_context, inferred_dialect = _infer_sql_runtime(
                path,
                source_lower,
            )
            return LanguageMatch(
                "sql",
                profile_id or inferred_profile,
                context_id or inferred_context,
                dialect_id or inferred_dialect,
                match_source="classified",
            )
        if suffix in {".yaml", ".yml"}:
            inferred_profile, inferred_context = _infer_yaml_runtime(path, source_lower)
            return LanguageMatch(
                "yaml",
                profile_id or inferred_profile,
                context_id or inferred_context,
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
        if language_id == "markdown":
            return LanguageMatch(
                language_id=language_id,
                profile_id=profile_id or "default",
                context_id=context_id,
                dialect_id=dialect_id,
                reviewable=False,
                match_source=match_source,
            )
        return LanguageMatch(
            language_id=language_id,
            profile_id=profile_id or "default",
            context_id=context_id,
            dialect_id=dialect_id,
            match_source=match_source,
        )


def _normalize_path(file_path: str | None) -> str:
    return (file_path or "").replace("\\", "/").lower()


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


def _infer_python_profile(lowered_path: str, lowered_source: str) -> str:
    if _has_any_token(lowered_source, _FASTAPI_TOKENS):
        return "fastapi_service"
    if _has_any_token(lowered_source, _DJANGO_TOKENS):
        return "django_service"
    if Path(lowered_path).name in {"manage.py", "settings.py", "urls.py", "wsgi.py", "asgi.py"}:
        return "django_service"
    return "default"


def _looks_like_tokio_rust(lowered_source: str) -> bool:
    return _has_any_token(lowered_source, _TOKIO_TOKENS)


def _infer_cuda_profile(lowered_source: str) -> str:
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
    return "default"


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


def _infer_yaml_runtime(lowered_path: str, lowered_source: str) -> tuple[str, str]:
    if _has_any_token(lowered_path, _SCHEMA_PATH_TOKENS) or "openapi:" in lowered_source:
        return "schema_config", "schema_config"
    if _has_any_token(lowered_path, _PRODUCT_CONFIG_TOKENS):
        return "product_config", "product_config"
    return "default", "generic"


def _infer_sql_runtime(lowered_path: str, lowered_source: str) -> tuple[str, str, str]:
    profile = "default"
    context = "generic"
    dialect = "generic"
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

    return profile, context, dialect


_REGISTRY = LanguageRegistry()


def get_language_registry() -> LanguageRegistry:
    return _REGISTRY
