---
rule_source_id: sql.dbt_warehouse_deepening
language_id: sql
dialect_id: generic
profile_hints: [dbt_warehouse]
pack_targets: [dbt_sql]
source_type: public_guideline_summary
source_ref:
  title: dbt Warehouse SQL Deepening
  url: https://docs.getdbt.com/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [sql, dbt, warehouse, jinja]
status: drafted
---

# dbt Warehouse SQL Deepening

## Scope

- This bundle deepens SQL review for dbt models and macros where Jinja adds another layer between code review and executed SQL.
- It focuses on model contracts and macro-driven SQL boundaries that are still visible locally.

## Candidate Canonical Rule Groups

- Model contract stability: ref/source boundaries, explicit projections, and projection drift.
- Macro execution boundaries: run_query, dynamic SQL generation, and explicit structure around warehouse-side effects.

## Reference-Only Guidance

- Keep incremental, freshness, and unique-key assumptions visible enough that reviewers can reason about model idempotency without reconstructing the whole project.
