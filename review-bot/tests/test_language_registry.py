from __future__ import annotations

from review_bot.language_registry import get_language_registry


def test_language_registry_marks_markdown_as_unreviewable() -> None:
    match = get_language_registry().resolve(file_path="docs/README.md")
    root_match = get_language_registry().resolve(file_path="README.md")

    assert match.language_id == "markdown"
    assert match.reviewable is False
    assert match.match_source == "classified"
    assert root_match.language_id == "markdown"
    assert root_match.reviewable is False
    assert root_match.match_source == "classified"


def test_language_registry_keeps_cpp_header_detection() -> None:
    match = get_language_registry().resolve(file_path="include/sample.h")

    assert match.language_id == "cpp"
    assert match.reviewable is True
    assert match.match_source == "classified"


def test_language_registry_detects_cuda_sources() -> None:
    registry = get_language_registry()

    cu = registry.resolve(file_path="kernels/vector_add.cu")
    cuh = registry.resolve(file_path="include/vector_add.cuh")
    cuda_async = registry.resolve(
        file_path="kernels/overlap.cu",
        source_text="cudaStreamCreate(&stream);\ncudaMemcpyAsync(dst, src, bytes, cudaMemcpyHostToDevice, 0);\n",
    )
    cuda_pipeline_async = registry.resolve(
        file_path="kernels/pipeline_stage.cu",
        source_text=(
            "#include <cuda/pipeline>\n"
            "auto pipe = cuda::make_pipeline(block, &pipe_state);\n"
            "pipe.producer_acquire();\n"
            "cuda::memcpy_async(block, dst, src, cuda::aligned_size_t<4>(bytes), pipe);\n"
            "pipe.producer_commit();\n"
            "pipe.consumer_wait();\n"
        ),
    )
    cuda_thread_block_cluster = registry.resolve(
        file_path="kernels/cluster_histogram.cu",
        source_text=(
            "#include <cooperative_groups.h>\n"
            "namespace cg = cooperative_groups;\n"
            "auto cluster = cg::this_cluster();\n"
            "int* remote_hist = cluster.map_shared_rank(smem, 1);\n"
            "cluster.sync();\n"
        ),
    )
    cuda_tma = registry.resolve(
        file_path="kernels/tma_tile.cu",
        source_text=(
            "#include <cuda.h>\n"
            "#include <cuda/ptx>\n"
            "namespace ptx = cuda::ptx;\n"
            "__global__ void load_tile(CUtensorMap* tensor_map) {\n"
            "  ptx::tensormap_replace_global_address(ptx::space_shared, &smem_tmap, out);\n"
            "  ptx::cp_async_bulk_tensor(ptx::space_shared, ptx::space_global, &tile, tensor_map, coords, handle);\n"
            "}\n"
        ),
    )
    cuda_wgmma = registry.resolve(
        file_path="kernels/warpgroup_gemm.cu",
        source_text=(
            "if (warpgroup == 0) { asm volatile(\"wgmma.mma_async.sync.aligned.m64n128k16.f32.f16.f16\"); }\n"
            "asm volatile(\"wgmma.commit_group.sync.aligned;\");\n"
            "asm volatile(\"wgmma.wait_group.sync.aligned 0;\");\n"
        ),
    )
    cuda_multigpu = registry.resolve(
        file_path="distributed/all_reduce.cu",
        source_text="for (int device = 0; device < count; ++device) { cudaSetDevice(device); }\nncclAllReduce(send, recv, count, ncclFloat, ncclSum, comm, stream);\n",
    )
    cuda_tensor_core = registry.resolve(
        file_path="kernels/tensor_core.cu",
        source_text="#include <mma.h>\nwmma::fragment<wmma::accumulator, 16, 16, 16, float> acc;\nwmma::mma_sync(acc, a, b, acc);\n",
    )
    cuda_cooperative_groups = registry.resolve(
        file_path="kernels/persistent_reduce.cu",
        source_text="#include <cooperative_groups.h>\nauto grid = cg::this_grid();\ngrid.sync();\n",
    )

    assert cu.language_id == "cuda"
    assert cu.profile_id == "default"
    assert cuh.language_id == "cuda"
    assert cuh.profile_id == "default"
    assert cuda_async.profile_id == "cuda_async_runtime"
    assert cuda_pipeline_async.profile_id == "cuda_pipeline_async"
    assert cuda_thread_block_cluster.profile_id == "cuda_thread_block_cluster"
    assert cuda_tma.profile_id == "cuda_tma"
    assert cuda_wgmma.profile_id == "cuda_wgmma"
    assert cuda_multigpu.profile_id == "cuda_multigpu"
    assert cuda_tensor_core.profile_id == "cuda_tensor_core"
    assert cuda_cooperative_groups.profile_id == "cuda_cooperative_groups"


def test_language_registry_detects_yaml_contexts_and_sql_hints() -> None:
    registry = get_language_registry()

    github_actions = registry.resolve(file_path=".github/workflows/build.yml")
    gitlab_ci = registry.resolve(file_path=".gitlab-ci.yml")
    helm_values = registry.resolve(file_path="charts/app/values-prod.yaml")
    kubernetes = registry.resolve(file_path="k8s/deployment.yaml")
    sql = registry.resolve(file_path="warehouse/postgres/report.sql")

    assert (github_actions.language_id, github_actions.profile_id, github_actions.context_id) == (
        "yaml",
        "github_actions",
        "github_actions",
    )
    assert (gitlab_ci.language_id, gitlab_ci.profile_id, gitlab_ci.context_id) == (
        "yaml",
        "gitlab_ci",
        "gitlab_ci",
    )
    assert (helm_values.language_id, helm_values.profile_id, helm_values.context_id) == (
        "yaml",
        "helm_values",
        "helm_values",
    )
    assert (kubernetes.language_id, kubernetes.profile_id, kubernetes.context_id) == (
        "yaml",
        "kubernetes_manifests",
        "kubernetes",
    )
    assert (sql.language_id, sql.profile_id, sql.context_id, sql.dialect_id) == (
        "sql",
        "analytics_warehouse",
        "analytics",
        "postgresql",
    )


def test_language_registry_detects_dockerfile_and_shebang_shell() -> None:
    registry = get_language_registry()

    dockerfile = registry.resolve(file_path="Dockerfile.prod")
    shell = registry.resolve(
        file_path="scripts/deploy",
        source_text="#!/usr/bin/env bash\nset -euo pipefail\n",
    )

    assert dockerfile.language_id == "dockerfile"
    assert dockerfile.profile_id == "default"
    assert shell.language_id == "bash"
    assert shell.profile_id == "default"


def test_language_registry_detects_framework_profiles_and_new_contexts() -> None:
    registry = get_language_registry()

    spring = registry.resolve(
        file_path="services/src/main/java/com/example/UserController.java",
        source_text="@RestController\n@Service\nclass UserController {}\n",
    )
    django = registry.resolve(
        file_path="service/settings.py",
        source_text="DEBUG = True\nfrom django.conf import settings\n",
    )
    fastapi = registry.resolve(
        file_path="api/routes/items.py",
        source_text="from fastapi import APIRouter\nrouter = APIRouter()\n@router.post('/items')\nasync def create_item():\n    return {}\n",
    )
    tokio = registry.resolve(
        file_path="src/main.rs",
        source_text="#[tokio::main]\nasync fn main() {}\n",
    )
    nextjs = registry.resolve(
        file_path="app/api/users/route.ts",
        source_text="export async function POST(request) { return Response.json(await request.json()) }\n",
    )
    product_yaml = registry.resolve(file_path="config/app/settings.yaml")
    schema_yaml = registry.resolve(file_path="schemas/openapi.yaml")
    dbt_sql = registry.resolve(
        file_path="dbt/models/orders.sql",
        source_text="select * from {{ ref('events') }}\n",
    )
    migration_sql = registry.resolve(
        file_path="db/migrations/postgres/V5__cleanup.sql",
        source_text="create index idx_orders_created_at on orders(created_at);\n",
    )
    react_typescript = registry.resolve(
        file_path="frontend/components/AuditPanel.tsx",
        source_text=(
            "import { useEffect } from 'react';\n"
            "export function AuditPanel() {\n"
            "  useEffect(async () => {}, []);\n"
            "  return null;\n"
            "}\n"
        ),
    )

    assert spring.profile_id == "spring_backend"
    assert django.profile_id == "django_service"
    assert fastapi.profile_id == "fastapi_service"
    assert tokio.profile_id == "tokio_async"
    assert (nextjs.profile_id, nextjs.context_id) == ("nextjs_frontend", "app_router")
    assert react_typescript.profile_id == "frontend_strict"
    assert (product_yaml.profile_id, product_yaml.context_id) == ("product_config", "product_config")
    assert (schema_yaml.profile_id, schema_yaml.context_id) == ("schema_config", "schema_config")
    assert (dbt_sql.profile_id, dbt_sql.context_id) == ("dbt_warehouse", "analytics")
    assert (migration_sql.profile_id, migration_sql.dialect_id) == ("migration_sql", "postgresql")


def test_language_registry_does_not_promote_generic_app_or_models_paths() -> None:
    registry = get_language_registry()

    generic_app = registry.resolve(
        file_path="app/server.ts",
        source_text="export async function bootstrap() { return 1 }\n",
    )
    generic_src_app = registry.resolve(
        file_path="src/app/service.ts",
        source_text="export const service = 1\n",
    )
    generic_pages = registry.resolve(
        file_path="pages/service.ts",
        source_text="export const service = 1\n",
    )
    generic_models = registry.resolve(
        file_path="models/report.sql",
        source_text="select id, name from users;\n",
    )
    generic_src_models = registry.resolve(
        file_path="src/models/report.sql",
        source_text="select id, name from users;\n",
    )

    assert (generic_app.profile_id, generic_app.context_id) == ("default", None)
    assert (generic_src_app.profile_id, generic_src_app.context_id) == ("default", None)
    assert (generic_pages.profile_id, generic_pages.context_id) == ("default", None)
    assert (generic_models.profile_id, generic_models.context_id, generic_models.dialect_id) == (
        "default",
        "generic",
        "generic",
    )
    assert (
        generic_src_models.profile_id,
        generic_src_models.context_id,
        generic_src_models.dialect_id,
    ) == ("default", "generic", "generic")
