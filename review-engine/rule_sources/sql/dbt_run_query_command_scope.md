---
rule_source_id: sql.dbt_run_query_command_scope
language_id: sql
dialect_id: generic
profile_hints: [dbt_warehouse]
pack_targets: [dbt_sql]
source_type: public_guideline_summary
source_ref:
  title: dbt run_query reference
  url: https://docs.getdbt.com/reference/dbt-jinja-functions/run_query
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [sql, dbt, warehouse, jinja, command-scope]
status: drafted
---

# dbt run_query Command Scope

## Scope

- This bundle deepens dbt macro review for `run_query` calls whose SQL can mutate or maintain warehouse state.
- It focuses on command scoping that is visible in the changed SQL/Jinja snippet itself.

## Candidate Canonical Rule Groups

- Side-effecting run_query command scope: DML, DDL, or maintenance SQL inside `run_query` should make the intended dbt command boundary explicit when the call is visible in the patch.

## Reference-Only Guidance

No additional reference-only guidance in this source.
