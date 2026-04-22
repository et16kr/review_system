from __future__ import annotations

from review_engine.languages import get_language_registry


def test_language_registry_defaults_header_files_to_cpp() -> None:
    match = get_language_registry().resolve(file_path="include/sample.h")

    assert match.language_id == "cpp"
    assert match.profile_id == "default"


def test_language_registry_detects_special_yaml_contexts() -> None:
    registry = get_language_registry()

    github_actions = registry.resolve(file_path=".github/workflows/build.yml")
    gitlab_ci = registry.resolve(file_path=".gitlab-ci.yml")
    helm_values = registry.resolve(file_path="charts/app/values-prod.yaml")
    kubernetes = registry.resolve(file_path="k8s/deployment.yaml")

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


def test_language_registry_detects_dockerfile_and_sql_hints() -> None:
    registry = get_language_registry()

    dockerfile = registry.resolve(file_path="Dockerfile.prod")
    sql = registry.resolve(file_path="warehouse/postgres/report.sql")

    assert dockerfile.language_id == "dockerfile"
    assert dockerfile.profile_id == "default"
    assert sql.language_id == "sql"
    assert sql.profile_id == "analytics_warehouse"
    assert sql.context_id == "analytics"
    assert sql.dialect_id == "postgresql"


def test_language_registry_detects_shebang_shell_scripts() -> None:
    match = get_language_registry().resolve(
        file_path="scripts/deploy",
        source_text="#!/usr/bin/env bash\nset -eu\n",
    )

    assert match.language_id == "bash"
    assert match.profile_id == "default"


def test_language_registry_marks_markdown_as_unreviewable() -> None:
    match = get_language_registry().resolve(file_path="docs/README.md")

    assert match.language_id == "unknown"
    assert match.reviewable is False
    assert match.match_source == "unmatched"
