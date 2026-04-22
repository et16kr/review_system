---
rule_source_id: java.java_runtime_baseline
language_id: java
dialect_id: null
profile_hints: [default]
pack_targets: [effective_java, project_java]
source_type: public_guideline_summary
source_ref:
  title: Java Runtime Review Baseline
  url: https://example.invalid/review-engine/java
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [java, resources, concurrency, sql]
status: drafted
---

# Java Runtime Baseline

## Scope

- This bundle covers Java resource ownership, null/absence contracts, SQL construction, and concurrency boundaries.
- The review target is production Java application code, not exhaustive language-style coverage.

## High-Signal Review Areas

- Prefer try-with-resources and explicit absence modeling.
- Parameterize SQL and keep thread-safety contracts explicit.
- Review null, concurrency, and resource ownership as API design questions, not local syntax alone.
- Treat broad `catch (Exception ...)` handlers as a contract boundary that needs strong justification.
- Prefer executors or structured concurrency ownership over ad hoc `new Thread(...)` usage in application code.

## Candidate Canonical Rule Groups

- Resource lifetime: closeable ownership, lexical scope, and try-with-resources.
- API contracts: null returns, empty collections, Optional, and absence semantics.
- Data access: SQL concatenation, prepared statements, and structural query control.
- Concurrency: synchronized collections, executor ownership, and broad exception boundaries.

## Reference-Only Guidance

- Use reference-only rules for collection immutability, API ergonomics, and broad class-design guidance that the patch alone cannot prove defective.
- Review Java changes through the question "what does this API promise about resource lifetime, absence, and concurrency?"
