---
rule_source_id: java.spring_backend_deepening
language_id: java
dialect_id: null
profile_hints: [spring_backend]
pack_targets: [spring_backend]
source_type: public_guideline_summary
source_ref:
  title: Spring Backend Deepening
  url: https://spring.io/projects/spring-framework
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [java, spring, transactions, validation]
status: drafted
---

# Spring Backend Deepening

## Scope

- This bundle deepens Java review for Spring request paths, service boundaries, and configuration binding.
- It focuses on boundary mistakes that are both common in production services and locally reviewable from annotations, wiring style, and repository usage.

## Candidate Canonical Rule Groups

- Dependency and wiring boundaries: constructor injection, dependency visibility, and immutable service wiring.
- Request and transaction boundaries: controller ownership, repository-wide reads, and request-path data shaping.
- Configuration binding safety: typed properties, startup validation, and explicit failure at bind time.

## Reference-Only Guidance

- Keep DTO, entity, exception translation, and validation ownership obvious so reviewers do not have to infer which Spring layer owns the contract.
