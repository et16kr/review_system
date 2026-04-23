---
rule_source_id: python.django_service_deepening
language_id: python
dialect_id: null
profile_hints: [django_service]
pack_targets: [django_service]
source_type: public_guideline_summary
source_ref:
  title: Django Service Deepening
  url: https://docs.djangoproject.com/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [python, django, csrf, orm]
status: drafted
---

# Django Service Deepening

## Scope

- This bundle deepens Python review for Django request handling, runtime settings, and ORM escape hatches.
- It prefers signals that indicate widened trust boundaries or hidden contract drift rather than general style guidance.

## Candidate Canonical Rule Groups

- Runtime settings and request trust boundaries: DEBUG, CSRF exemptions, and environment-specific behavior.
- ORM escape hatches: raw SQL, extra clauses, and boundaries that step outside ordinary queryset reviewability.
- Template trust boundaries: `mark_safe` and other HTML escaping bypasses that widen XSS review scope.

## Reference-Only Guidance

- Keep validation, serialization, and queryset loading ownership obvious across view, serializer, and model boundaries.
