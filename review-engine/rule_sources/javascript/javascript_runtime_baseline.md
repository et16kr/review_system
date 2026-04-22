---
rule_source_id: javascript.javascript_runtime_baseline
language_id: javascript
dialect_id: null
profile_hints: [default]
pack_targets: [project_javascript, node_javascript]
source_type: public_guideline_summary
source_ref:
  title: JavaScript Runtime Review Baseline
  url: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [javascript, dom, async, security]
status: drafted
---

# JavaScript Runtime Baseline

## Scope

- This bundle covers JavaScript DOM safety, async error propagation, runtime type assumptions, and dynamic execution boundaries.
- The emphasis is on code-review signals that can be inferred from changed code without deep framework-specific analysis.

## High-Signal Review Areas

- Avoid eval, string-based timers, `document.write`, and raw `innerHTML` writes in normal application paths.
- Keep async error propagation explicit.
- Prefer strict equality unless coercion is intentionally part of the behavior.
- Treat detached promise chains as ownership decisions about where failures and retries actually go.

## Candidate Canonical Rule Groups

- Dynamic execution: eval-like APIs, string callbacks, and runtime code loading.
- DOM injection boundaries: `innerHTML`, `document.write`, and raw HTML rendering.
- Async ownership: promise chaining, returned vs detached work, and error visibility.
- Runtime coercion: loose equality, normalization before comparison, and boundary clarity.

## Reference-Only Guidance

- Use reference-only rules for broader design topics such as event-listener cleanup, module side effects, and state ownership when the diff alone is not conclusive.
- Review JavaScript with the question "where does untrusted text become executable behavior or DOM structure?"
