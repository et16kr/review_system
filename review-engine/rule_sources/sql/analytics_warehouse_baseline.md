---
rule_source_id: sql.analytics_warehouse_baseline
language_id: sql
dialect_id: generic
profile_hints: [analytics_warehouse]
pack_targets: [analytics_sql, ansi_sql, project_sql]
source_type: public_guideline_summary
source_ref:
  title: Analytics Warehouse SQL Baseline
  url: https://example.invalid/review-engine/analytics-warehouse
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [sql, analytics, warehouse, reporting]
status: drafted
---

# Analytics Warehouse SQL Baseline

## Scope

- This bundle covers committed analytics and warehouse SQL where query text acts as a durable reporting, transformation, or model contract.
- The main review lens is result stability, grouping clarity, and boundary visibility around incremental or reporting-oriented queries.

## High-Signal Review Areas

- Prefer explicit grouping references over ordinal grouping in committed reporting SQL.
- Treat `LIMIT` without explicit ordering as unstable when the query result is meant to be reused, inspected, or published.
- Make deduplication and freshness boundaries explicit in warehouse models instead of leaving them implicit in terse SQL forms.

## Candidate Canonical Rule Groups

- Stable grouping contracts: ordinal `GROUP BY`, projection drift, and long-lived report evolution.
- Result stability under sampling or paging: `LIMIT` without `ORDER BY` in committed warehouse/reporting queries.
- Warehouse model semantics: deduplication intent, incremental freshness filters, and model boundary clarity.

## Reference-Only Guidance

- Warehouse queries should make `UNION` versus `UNION ALL` intent explicit when deduplication cost and semantics matter to downstream consumers.
- Review analytics SQL through the question "what stable reporting or model contract does this query define, and which grouping, ordering, or freshness assumption does it hide?"
