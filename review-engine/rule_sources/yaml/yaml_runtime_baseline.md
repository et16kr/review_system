---
rule_source_id: yaml.yaml_runtime_baseline
language_id: yaml
dialect_id: null
profile_hints: [default, kubernetes_manifests, github_actions, gitlab_ci, helm_values]
pack_targets: [generic_yaml, kubernetes_yaml, ci_yaml, helm_values]
source_type: public_guideline_summary
source_ref:
  title: YAML Runtime Review Baseline
  url: https://yaml.org/spec/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [yaml, kubernetes, ci, helm]
status: drafted
---

# YAML Runtime Baseline

## Scope

- This bundle covers generic YAML plus the current runtime contexts: Kubernetes, GitHub Actions, GitLab CI, and Helm values.
- Review should be context-aware; the same key can carry very different risk depending on whether the file is CI, deployment, or chart configuration.

## High-Signal Review Areas

- Review YAML through the schema and operational context, not syntax alone.
- Kubernetes manifests should default to least privilege.
- CI workflows should minimize token scope and pin mutable runtime images deliberately.
- Treat privilege-expanding fields such as `privileged`, `allowPrivilegeEscalation`, `hostNetwork`, and `runAsUser: 0` as strong security signals.
- Treat branch-ref action usage and mutable runtime images as provenance and rollback concerns in CI.

## Candidate Canonical Rule Groups

- Generic configuration: schema-aligned values, explicit image tags, and contract clarity.
- Kubernetes security: privileged mode, root identity, privilege escalation, and host network sharing.
- CI security and provenance: token scope, mutable images, and unpinned action refs.
- Helm values: deployable image versioning, environment contracts, and chart-input clarity.

## Reference-Only Guidance

- Use reference-only rules for chart ergonomics, generic schema readability, and operational runbook guidance unless the diff shows a concrete unsafe change.
- Review YAML through the question "what environment or control plane consumes this, and what privilege or provenance boundary does this field affect?"
