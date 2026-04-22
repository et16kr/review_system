from __future__ import annotations

from review_bot.language_registry import get_language_registry


def test_language_registry_marks_markdown_as_unreviewable() -> None:
    match = get_language_registry().resolve(file_path="docs/README.md")

    assert match.language_id == "unknown"
    assert match.reviewable is False
    assert match.match_source == "unmatched"


def test_language_registry_keeps_cpp_header_detection() -> None:
    match = get_language_registry().resolve(file_path="include/sample.h")

    assert match.language_id == "cpp"
    assert match.reviewable is True
    assert match.match_source == "classified"


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
