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
            "examples/multilang_safe/Dockerfile",
            {"DOCKER.1", "DOCKER.SEC.1", "DOCKER.SEC.5"},
            "dockerfile",
            None,
        ),
        (
            "examples/multilang_safe/.github/workflows/workflow_readonly.yml",
            {"YAML.CI.1", "YAML.CI.5"},
            "yaml",
            "github_actions",
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
