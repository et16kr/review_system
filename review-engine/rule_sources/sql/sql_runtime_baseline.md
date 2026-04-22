---
rule_source_id: sql.sql_runtime_baseline
language_id: sql
dialect_id: generic
profile_hints: [default, analytics_warehouse]
pack_targets: [ansi_sql, postgres_sql, project_sql]
source_type: public_guideline_summary
source_ref:
  title: SQL Runtime Review Baseline
  url: https://example.invalid/review-engine/sql
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [sql, joins, mutation, parameterization]
status: drafted
---

# SQL Runtime Baseline

## Scope

- This bundle covers shared SQL review themes plus PostgreSQL-flavored structural guidance used by the current runtime.
- The focus is on query contracts, destructive statements, and dynamic SQL boundaries.

## High-Signal Review Areas

- Prefer explicit joins and explicit column lists.
- Treat full-table UPDATE or DELETE statements as high-risk operations.
- Keep dynamic SQL structural and tightly bounded, with values still parameterized.
- Review ordinal sort positions, `NOT IN` subqueries, and similar concise SQL forms when they hide correctness assumptions.

## Candidate Canonical Rule Groups

- Result-set contracts: `SELECT *`, projection drift, and schema-coupled consumers.
- Join clarity: comma joins, relationship-local predicates, and accidental cartesian products.
- Destructive mutations: missing predicates, admin-only maintenance paths, and explicit operational boundaries.
- Dynamic SQL: allow-listed structure, bound values, dialect-specific helpers, and query builder boundaries.

## Reference-Only Guidance

- Use reference-only rules for warehouse modeling, naming, and readability guidance unless the diff shows a concrete correctness or safety hazard.
- Review SQL through the question "what exact data set or mutation set does this text define, and how obvious is that from the query itself?"
