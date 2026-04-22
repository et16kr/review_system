---
rule_source_id: c.posix_c_safety
language_id: c
dialect_id: null
profile_hints: [default]
pack_targets: [posix_c, project_c, native_memory_shared]
source_type: public_guideline_summary
source_ref:
  title: POSIX C Safety Baseline
  url: https://example.invalid/review-engine/posix-c
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [c, posix, memory, strings]
status: drafted
---

# POSIX C Safety

## Scope

- This bundle covers native C code that relies on explicit allocation, cleanup labels, POSIX I/O, and string-manipulation APIs.
- The primary review focus is on ownership clarity, buffer boundaries, and interfaces that make caller obligations explicit.

## High-Signal Review Areas

- Keep ownership and cleanup paths centralized in code that uses explicit allocation.
- Prefer size-aware string and formatting APIs and make truncation policy visible where data crosses a boundary.
- Make caller ownership, capacity, nullability, and cleanup responsibilities visible in the interface.
- Treat goto-based cleanup as acceptable only when the unwinding order remains single-sourced and mechanically obvious.

## Candidate Canonical Rule Groups

- Manual memory ownership: allocation checks, rollback semantics, and one obvious release path.
- Cleanup flow: `goto cleanup/error/fail`, reverse-order release, and avoidance of partially overlapping release branches.
- String and formatting safety: bounded APIs, destination sizes, and explicit format contracts.
- Project-facing C APIs: buffer size, output ownership, nullability, and errno/error code expectations.

## Reference-Only Guidance

- Prefer interfaces that package pointer-plus-size semantics into one explicit contract where compatibility permits.
- Avoid forcing reviewers to infer capacity or ownership from distant declarations or comments alone.
- Review C changes through the question "who owns this memory, who frees it, and what size contract is actually visible here?"
