---
rule_source_id: typescript.typescript_runtime_baseline
language_id: typescript
dialect_id: null
profile_hints: [default, frontend_strict]
pack_targets: [project_typescript, ts_api_design]
source_type: public_guideline_summary
source_ref:
  title: TypeScript Runtime Review Baseline
  url: https://www.typescriptlang.org/docs/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [typescript, typing, async, validation]
status: drafted
---

# TypeScript Runtime Baseline

## Scope

- This bundle covers TypeScript boundary typing, runtime validation, async ownership, and localized suppression of the type checker.
- The main target is reviewable application code where compile-time proof and runtime validation are meant to work together.

## High-Signal Review Areas

- Avoid `any` at API boundaries and treat non-null assertions as proof obligations.
- Keep `@ts-ignore` and `@ts-expect-error` temporary and localized.
- Validate parsed or external JSON before trusting its shape.
- Review double casts through `unknown` as likely evidence that runtime validation is missing at the boundary.

## Candidate Canonical Rule Groups

- Boundary typing: `any`, double-cast escape hatches, DTO contracts, and public API drift.
- Suppression hygiene: ignore directives, expect-error scope, and temporary compatibility debt.
- Runtime validation: JSON.parse, unknown-to-domain conversion, and schema checks.
- Async ownership: promise chains, detached work, and rejection visibility.

## Reference-Only Guidance

- Use reference-only rules for broader topics such as discriminated unions, exhaustive switches, and state modeling unless the diff exposes a concrete failure mode.
- Review TypeScript changes through the question "where does unchecked runtime data become a trusted domain type?"
