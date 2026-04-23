---
rule_source_id: typescript.react_frontend_deepening
language_id: typescript
dialect_id: null
profile_hints: [frontend_strict]
pack_targets: [project_typescript, ts_api_design]
source_type: public_guideline_summary
source_ref:
  title: React Frontend TypeScript Deepening
  url: https://react.dev/reference/react
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [typescript, react, frontend, effects, rendering]
status: drafted
---

# React Frontend TypeScript Deepening

## Scope

- This bundle deepens TypeScript review for React and TSX code where runtime rendering, effect ownership, and hook dependency contracts matter as much as the type system.
- It focuses on reviewable frontend patterns that frequently lead to stale UI behavior, hidden lifecycle bugs, or widened XSS boundaries.

## High-Signal Review Areas

- Treat `dangerouslySetInnerHTML` as a trust boundary that needs a narrow sanitization story.
- Treat `useEffect(async () => ...)` as a lifecycle smell because cleanup and rejection ownership become unclear.
- Treat suppression of `react-hooks/exhaustive-deps` as a strong hint that effect ownership or state derivation needs restructuring.

## Candidate Canonical Rule Groups

- Rendering trust boundaries: raw HTML sinks, sanitization adjacency, and data-to-markup conversion.
- Effect lifetime ownership: async effect callbacks, rejection visibility, and cleanup expectations.
- Hook dependency suppression: local disable directives, stale captures, and intentionally detached behavior.

## Reference-Only Guidance

- Prefer stable semantic keys over positional indexes when list item identity affects local state or animation continuity.
- Review React/TSX changes through the question "which state, effect, or rendering trust boundary became harder to prove locally in this component?"
