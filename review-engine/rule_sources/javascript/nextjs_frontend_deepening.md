---
rule_source_id: javascript.nextjs_frontend_deepening
language_id: javascript
dialect_id: null
profile_hints: [nextjs_frontend]
pack_targets: [nextjs_frontend]
source_type: public_guideline_summary
source_ref:
  title: Next.js Frontend Deepening for JavaScript
  url: https://nextjs.org/docs
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [javascript, nextjs, app-router, server-actions]
status: drafted
---

# Next.js Frontend Deepening

## Scope

- This bundle deepens JavaScript review for Next.js route handlers, server actions, and app-router file boundaries.
- It targets framework-specific boundary mistakes that remain visible even without a full type layer.

## Candidate Canonical Rule Groups

- Route and action input boundaries: request JSON, FormData, and explicit validation.
- Server and client file responsibilities: secret/env access, browser APIs, and visible client boundaries.

## Reference-Only Guidance

- Keep cache, revalidation, and server-client ownership obvious from the file boundary so reviewers do not have to infer framework defaults from distant files.
