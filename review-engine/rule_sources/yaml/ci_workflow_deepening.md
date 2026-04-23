---
rule_source_id: yaml.ci_workflow_deepening
language_id: yaml
dialect_id: null
profile_hints: [github_actions, gitlab_ci]
pack_targets: [ci_yaml]
source_type: public_guideline_summary
source_ref:
  title: CI Workflow Deepening Baseline
  url: https://docs.gitlab.com/ee/ci/yaml/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [yaml, ci, provenance, bootstrap]
status: drafted
---

# CI Workflow Deepening Baseline

## Scope

- This bundle deepens the existing CI workflow coverage for checked-in automation that runs shell bootstrap, helper services, or deployment-oriented steps.
- It focuses on executable provenance and failure visibility inside CI configuration rather than general pipeline style.

## High-Signal Review Areas

- Treat shell-piped bootstrap inside CI scripts as a strong trust-boundary exception.
- Treat insecure download flags in CI as a provenance gap, not just a convenience option.
- Keep service and helper container images pinned tightly enough that job behavior remains reproducible.

## Candidate Canonical Rule Groups

- Remote bootstrap in CI script steps: `curl | bash`, `wget | sh`, and similar executable download boundaries.
- CI download verification: `curl --insecure`, `wget --no-check-certificate`, and similar provenance bypasses.
- Helper/service image provenance: floating `latest` tags in CI service containers and helper images.
- GitHub Actions trigger trust boundaries: `pull_request_target` and similarly privileged PR execution paths.

## Reference-Only Guidance

- Deployment and migration jobs should make approval, retry, and failure boundaries obvious even when the exact workflow contract spans multiple stages.
- Review CI changes through the question "what new executable artifact or mutable runtime enters the pipeline here, and how obvious is its trust boundary?"
