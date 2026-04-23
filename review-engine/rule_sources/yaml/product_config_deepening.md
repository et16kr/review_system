---
rule_source_id: yaml.product_config_deepening
language_id: yaml
dialect_id: null
profile_hints: [product_config]
pack_targets: [product_yaml]
source_type: public_guideline_summary
source_ref:
  title: Product Config YAML Deepening
  url: https://example.invalid/review-engine/product-config-yaml
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [yaml, config, secrets, overrides]
status: drafted
---

# Product Config YAML Deepening

## Scope

- This bundle deepens YAML review for product and application configuration files outside CI and Kubernetes manifests.
- It focuses on secret material, override clarity, and environment drift rather than generic syntax concerns.

## Candidate Canonical Rule Groups

- Secret material in committed config: direct credentials, tokens, and runtime secrets.
- Layered config clarity: merge keys, inherited defaults, and environment-specific overrides.

## Reference-Only Guidance

- Keep override precedence obvious enough that reviewers can tell which environment or deployment layer actually owns the effective value.
