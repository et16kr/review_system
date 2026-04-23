from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("relative_path", "forbidden_rules", "expected_language", "expected_context"),
    [
        (
            "examples/multilang_safe/bash_strict.sh",
            {"BASH.1", "BASH.2", "BASH.4", "BASH.SAFE.2", "BASH.SAFE.5"},
            "bash",
            None,
        ),
        (
            "examples/multilang_safe/python_context_manager.py",
            {"PY.1", "PY.5", "PY.PROJ.1", "PY.PROJ.6", "PY.PROJ.7"},
            "python",
            None,
        ),
        (
            "examples/multilang_safe/typescript_validated_parse.ts",
            {"TS.1", "TS.API.5", "TS.API.6", "TS.API.7"},
            "typescript",
            None,
        ),
        (
            "examples/multilang_safe/typescript_react_safe.tsx",
            {"TS.6", "TS.7", "TS.API.8"},
            "typescript",
            None,
        ),
        (
            "examples/multilang_safe/Dockerfile",
            {"DOCKER.1", "DOCKER.7", "DOCKER.SEC.1", "DOCKER.SEC.5"},
            "dockerfile",
            None,
        ),
        (
            "examples/multilang_safe/.github/workflows/workflow_readonly.yml",
            {"YAML.CI.1", "YAML.CI.5"},
            "yaml",
            "github_actions",
        ),
        (
            "examples/multilang_safe/next_client_public_env.tsx",
            {"TS.NEXT.3"},
            "typescript",
            None,
        ),
        (
            "examples/multilang_safe/schema_closed.yaml",
            {"YAML.SCHEMA.1", "YAML.SCHEMA.2"},
            "yaml",
            "generic",
        ),
        (
            "examples/multilang_safe/cuda_async_stream_safe.cu",
            {"CUDA.ASYNC.1", "CUDA.ASYNC.2", "CUDA.ASYNC.3"},
            "cuda",
            None,
        ),
        (
            "examples/multilang_safe/cuda_pipeline_async_safe.cu",
            {"CUDA.PIPE.1", "CUDA.PIPE.2", "CUDA.PIPE.3"},
            "cuda",
            None,
        ),
        (
            "examples/multilang_safe/cuda_thread_block_cluster_safe.cu",
            {"CUDA.CLUSTER.1", "CUDA.CLUSTER.2", "CUDA.CLUSTER.3"},
            "cuda",
            None,
        ),
        (
            "examples/multilang_safe/cuda_tma_tensor_map_safe.cu",
            {"CUDA.TMA.1", "CUDA.TMA.2", "CUDA.TMA.3"},
            "cuda",
            None,
        ),
        (
            "examples/multilang_safe/cuda_wgmma_safe.cu",
            {"CUDA.WGMMA.1", "CUDA.WGMMA.2", "CUDA.WGMMA.3"},
            "cuda",
            None,
        ),
    ],
)
def test_safe_multilang_examples_do_not_trigger_high_signal_findings(
    real_search_service,
    relative_path: str,
    forbidden_rules: set[str],
    expected_language: str,
    expected_context: str | None,
) -> None:
    input_path = PROJECT_ROOT / relative_path
    payload = input_path.read_text(encoding="utf-8")

    response = real_search_service.review_code(
        payload,
        top_k=12,
        file_path=relative_path,
    )

    returned_rules = {result.rule_no for result in response.results}
    assert response.language_id == expected_language
    assert response.context_id == expected_context
    assert forbidden_rules.isdisjoint(returned_rules)


@pytest.mark.parametrize(
    ("file_path", "payload", "required_rule", "forbidden_pack"),
    [
        (
            ".gitlab-ci.yml",
            "image: python:latest\njob:\n  script:\n    - pytest\n",
            "YAML.CI.2",
            "helm_values",
        ),
        (
            "charts/app/values-prod.yaml",
            "image: demo/app:latest\nextraEnv: []\n",
            "YAML.HELM.2",
            "ci_yaml",
        ),
    ],
)
def test_yaml_context_specific_rules_do_not_leak_across_profiles(
    real_search_service,
    file_path: str,
    payload: str,
    required_rule: str,
    forbidden_pack: str,
) -> None:
    response = real_search_service.review_code(
        payload,
        top_k=8,
        file_path=file_path,
    )

    returned_rules = {result.rule_no for result in response.results}
    returned_packs = {result.pack_id for result in response.results}

    assert required_rule in returned_rules
    assert forbidden_pack not in returned_packs


def test_sql_dialect_specific_rules_do_not_leak_into_generic_sql_results(
    real_search_service,
) -> None:
    response = real_search_service.review_code(
        "select id, name from users order by 1;\n",
        top_k=8,
        file_path="queries/report.sql",
    )

    returned_rules = {result.rule_no for result in response.results}

    assert "SQL.5" in returned_rules
    assert not any(rule.startswith("SQL.PG.") for rule in returned_rules)


def test_analytics_warehouse_rules_do_not_leak_into_generic_sql_results(
    real_search_service,
) -> None:
    generic = real_search_service.review_code(
        "select user_id, count(*) from events group by 1 limit 10;\n",
        top_k=8,
        file_path="queries/report.sql",
    )
    analytics = real_search_service.review_code(
        "select user_id, count(*) from events group by 1 limit 10;\n",
        top_k=8,
        file_path="warehouse/daily_rollup.sql",
    )

    generic_rules = {result.rule_no for result in generic.results}
    analytics_rules = {result.rule_no for result in analytics.results}

    assert not any(rule.startswith("SQL.WH.") for rule in generic_rules)
    assert {"SQL.WH.1", "SQL.WH.2"} <= analytics_rules


def test_generic_app_and_models_paths_do_not_inherit_nextjs_or_dbt_rules(
    real_search_service,
) -> None:
    generic_app = real_search_service.review_code(
        "export async function POST(request: Request) {\n  const payload = await request.json();\n  return Response.json(payload);\n}\n",
        top_k=8,
        file_path="app/server.ts",
    )
    generic_models = real_search_service.review_code(
        "select user_id, count(*) from events group by 1 limit 10;\n",
        top_k=8,
        file_path="models/report.sql",
    )

    app_rules = {result.rule_no for result in generic_app.results}
    model_rules = {result.rule_no for result in generic_models.results}

    assert (generic_app.profile_id, generic_app.context_id) == ("default", None)
    assert not any(rule.startswith("TS.NEXT.") for rule in app_rules)
    assert (generic_models.profile_id, generic_models.context_id) == ("default", "generic")
    assert not any(rule.startswith("SQL.DBT.") for rule in model_rules)
    assert not any(rule.startswith("SQL.WH.") for rule in model_rules)


def test_ci_deepening_rules_apply_to_gitlab_ci_context(
    real_search_service,
) -> None:
    response = real_search_service.review_code(
        "image: python:3.12\nservices:\n  - postgres:latest\njob:\n  script:\n    - curl --insecure https://example.com/install.sh | bash\n",
        top_k=10,
        file_path="pipelines/.gitlab-ci.yml",
    )

    returned_rules = {result.rule_no for result in response.results}

    assert response.language_id == "yaml"
    assert response.profile_id == "gitlab_ci"
    assert response.context_id == "gitlab_ci"
    assert {"YAML.CI.6", "YAML.CI.7", "YAML.CI.8"} <= returned_rules


def test_typescript_react_rules_apply_to_tsx_files(
    real_search_service,
) -> None:
    response = real_search_service.review_code(
        "import { useEffect } from 'react';\n// eslint-disable-next-line react-hooks/exhaustive-deps\nuseEffect(async () => {\n  await fetch(url);\n}, []);\nreturn <div dangerouslySetInnerHTML={{ __html: html }} />;\n",
        top_k=10,
        file_path="src/AuditPanel.tsx",
    )

    returned_rules = {result.rule_no for result in response.results}

    assert response.language_id == "typescript"
    assert {"TS.6", "TS.7", "TS.API.8"} <= returned_rules


def test_framework_and_context_specific_rules_apply_to_new_profiles(
    real_search_service,
) -> None:
    spring = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/java_spring_controller.java").read_text(encoding="utf-8"),
        top_k=10,
        file_path="services/src/main/java/com/example/UserController.java",
    )
    django = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/python_django_service.py").read_text(encoding="utf-8"),
        top_k=10,
        file_path="service/settings.py",
    )
    fastapi = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/python_fastapi_service.py").read_text(encoding="utf-8"),
        top_k=10,
        file_path="api/routes/items.py",
    )
    tokio = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/rust_tokio_async.rs").read_text(encoding="utf-8"),
        top_k=10,
        file_path="src/main.rs",
    )
    nextjs = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/next_app_route.ts").read_text(encoding="utf-8"),
        top_k=10,
        file_path="app/api/users/route.ts",
    )
    product_yaml = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/product_config.yaml").read_text(encoding="utf-8"),
        top_k=8,
        file_path="config/app/settings.yaml",
    )
    schema_yaml = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/schema_config.yaml").read_text(encoding="utf-8"),
        top_k=8,
        file_path="schemas/openapi.yaml",
    )
    dbt_sql = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/dbt_model.sql").read_text(encoding="utf-8"),
        top_k=8,
        file_path="dbt/models/orders.sql",
    )
    migration_sql = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/migration_ddl.sql").read_text(encoding="utf-8"),
        top_k=10,
        file_path="db/migrations/postgres/V5__cleanup.sql",
    )

    assert spring.profile_id == "spring_backend"
    assert {"JAVA.SPRING.1", "JAVA.SPRING.2", "JAVA.SPRING.4"} <= {
        result.rule_no for result in spring.results
    }
    assert django.profile_id == "django_service"
    assert {"PY.DJ.1", "PY.DJ.2", "PY.DJ.3", "PY.DJ.4"} <= {result.rule_no for result in django.results}
    assert fastapi.profile_id == "fastapi_service"
    assert {"PY.FAPI.1", "PY.FAPI.2"} <= {result.rule_no for result in fastapi.results}
    assert tokio.profile_id == "tokio_async"
    assert {"RUST.TOKIO.1", "RUST.TOKIO.2", "RUST.TOKIO.3"} <= {
        result.rule_no for result in tokio.results
    }
    assert (nextjs.profile_id, nextjs.context_id) == ("nextjs_frontend", "app_router")
    assert "TS.NEXT.1" in {result.rule_no for result in nextjs.results}
    assert (product_yaml.profile_id, product_yaml.context_id) == ("product_config", "product_config")
    assert "YAML.PROD.1" in {result.rule_no for result in product_yaml.results}
    assert (schema_yaml.profile_id, schema_yaml.context_id) == ("schema_config", "schema_config")
    assert {"YAML.SCHEMA.1", "YAML.SCHEMA.2"} <= {result.rule_no for result in schema_yaml.results}
    assert (dbt_sql.profile_id, dbt_sql.context_id) == ("dbt_warehouse", "analytics")
    assert {"SQL.DBT.1", "SQL.DBT.2"} <= {result.rule_no for result in dbt_sql.results}
    assert (migration_sql.profile_id, migration_sql.dialect_id) == ("migration_sql", "postgresql")
    assert {"SQL.MIG.1", "SQL.MIG.2", "SQL.MIG.3", "SQL.MIG.4", "SQL.MIG.5"} <= {
        result.rule_no for result in migration_sql.results
    }


def test_cuda_rules_apply_to_cuda_files(
    real_search_service,
) -> None:
    response = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_divergent_sync.cu").read_text(encoding="utf-8"),
        top_k=10,
        file_path="kernels/cuda_divergent_sync.cu",
    )

    returned_rules = {result.rule_no for result in response.results}

    assert response.language_id == "cuda"
    assert response.profile_id == "default"
    assert {"CUDA.3", "CUDA.4", "CUDA.PERF.1"} <= returned_rules


def test_cuda_followup_profiles_apply_to_cuda_files(
    real_search_service,
) -> None:
    cuda_async = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_async_default_stream.cu").read_text(encoding="utf-8"),
        top_k=10,
        file_path="kernels/cuda_async_default_stream.cu",
    )
    cuda_pipeline_async = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_pipeline_async_stage_drift.cu").read_text(
            encoding="utf-8"
        ),
        top_k=10,
        file_path="kernels/cuda_pipeline_async_stage_drift.cu",
    )
    cuda_thread_block_cluster = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_thread_block_cluster_dsm.cu").read_text(
            encoding="utf-8"
        ),
        top_k=10,
        file_path="kernels/cuda_thread_block_cluster_dsm.cu",
    )
    cuda_tma = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_tma_tensor_map_contract.cu").read_text(
            encoding="utf-8"
        ),
        top_k=10,
        file_path="kernels/cuda_tma_tensor_map_contract.cu",
    )
    cuda_wgmma = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_wgmma_async_group_drift.cu").read_text(
            encoding="utf-8"
        ),
        top_k=10,
        file_path="kernels/cuda_wgmma_async_group_drift.cu",
    )
    cuda_multigpu = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_multigpu_nccl.cu").read_text(encoding="utf-8"),
        top_k=10,
        file_path="distributed/cuda_multigpu_nccl.cu",
    )
    cuda_tensor_core = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_tensor_core_wmma.cu").read_text(encoding="utf-8"),
        top_k=10,
        file_path="kernels/cuda_tensor_core_wmma.cu",
    )
    cuda_cooperative_groups = real_search_service.review_code(
        (PROJECT_ROOT / "examples/multilang/cuda_cooperative_groups_grid_sync.cu").read_text(encoding="utf-8"),
        top_k=10,
        file_path="kernels/cuda_cooperative_groups_grid_sync.cu",
    )

    assert cuda_async.profile_id == "cuda_async_runtime"
    assert {"CUDA.ASYNC.1", "CUDA.ASYNC.2", "CUDA.ASYNC.3"} <= {
        result.rule_no for result in cuda_async.results
    }
    assert cuda_pipeline_async.profile_id == "cuda_pipeline_async"
    assert {"CUDA.PIPE.1", "CUDA.PIPE.2", "CUDA.PIPE.3"} <= {
        result.rule_no for result in cuda_pipeline_async.results
    }
    assert cuda_thread_block_cluster.profile_id == "cuda_thread_block_cluster"
    assert {"CUDA.CLUSTER.1", "CUDA.CLUSTER.2", "CUDA.CLUSTER.3"} <= {
        result.rule_no for result in cuda_thread_block_cluster.results
    }
    assert cuda_tma.profile_id == "cuda_tma"
    assert {"CUDA.TMA.1", "CUDA.TMA.2", "CUDA.TMA.3"} <= {
        result.rule_no for result in cuda_tma.results
    }
    assert cuda_wgmma.profile_id == "cuda_wgmma"
    assert {"CUDA.WGMMA.1", "CUDA.WGMMA.2", "CUDA.WGMMA.3"} <= {
        result.rule_no for result in cuda_wgmma.results
    }
    assert cuda_multigpu.profile_id == "cuda_multigpu"
    assert {"CUDA.MG.1", "CUDA.MG.2", "CUDA.MG.3"} <= {
        result.rule_no for result in cuda_multigpu.results
    }
    assert cuda_tensor_core.profile_id == "cuda_tensor_core"
    assert {"CUDA.TC.1", "CUDA.TC.2", "CUDA.TC.3"} <= {
        result.rule_no for result in cuda_tensor_core.results
    }
    assert cuda_cooperative_groups.profile_id == "cuda_cooperative_groups"
    assert {"CUDA.CG.1", "CUDA.CG.2", "CUDA.CG.3"} <= {
        result.rule_no for result in cuda_cooperative_groups.results
    }
