---
rule_source_id: sql.migration_sql_deepening
language_id: sql
dialect_id: generic
profile_hints: [migration_sql]
pack_targets: [migration_sql]
source_type: public_guideline_summary
source_ref:
  title: Migration SQL Deepening
  url: https://example.invalid/review-engine/migration-sql
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [sql, migration, ddl, rollout]
status: drafted
---

# Migration SQL Deepening

## Scope

- This bundle deepens SQL review for schema migrations that run against live or semi-live systems.
- It focuses on destructive DDL, lock-heavy operations, and rollout sequencing that are visible from migration text.

## Candidate Canonical Rule Groups

- Destructive schema changes: DROP TABLE, DROP COLUMN, `CASCADE`, and staged compatibility removal.
- Constraint and index rollout: NOT NULL tightening, concurrent index strategy, and lock-aware migration shape.

## Reference-Only Guidance

- Keep transaction, rollback, and lock-window expectations explicit so reviewers do not have to infer operational safety from the DDL alone.
