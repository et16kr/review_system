---
rule_source_id: yaml.schema_config_deepening
language_id: yaml
dialect_id: null
profile_hints: [schema_config]
pack_targets: [schema_yaml]
source_type: public_guideline_summary
source_ref:
  title: Schema Config YAML Deepening
  url: https://spec.openapis.org/oas/latest.html
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [yaml, schema, openapi, contract]
status: drafted
---

# Schema Config YAML Deepening

## Scope

- This bundle deepens YAML review for schema and API-contract files such as OpenAPI and configuration schemas.
- It focuses on contract width, default ambiguity, and producer-consumer drift that remain visible from the schema text itself.

## Candidate Canonical Rule Groups

- Contract width: additionalProperties and overly open extension points.
- Default clarity: boolean-like defaults, parser ambiguity, and explicit type intent.

## Reference-Only Guidance

- Keep required, nullable, and default semantics aligned so the schema tells one clear story to both producers and consumers.
