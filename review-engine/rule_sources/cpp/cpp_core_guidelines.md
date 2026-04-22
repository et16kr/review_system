---
rule_source_id: cpp.cpp_core_guidelines
language_id: cpp
dialect_id: null
profile_hints: [default]
pack_targets: [cpp_core, project_cpp, native_memory_shared]
source_type: public_guideline_summary
source_ref:
  title: C++ Core / Native Memory Review Baseline
  url: https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [cpp, memory, raii, portability]
status: drafted
---

# C++ Runtime Baseline

## Scope

- This bundle covers C++ ownership, RAII, portability, low-level API wrapping, formatting, and concurrency boundaries.
- It is derived from the review-relevant subset of public C++ Core Guideline themes rather than full-text reproduction.

## High-Signal Review Areas

- Prefer RAII and explicit ownership instead of raw lifetime management.
- Avoid `malloc/free`, raw `new/delete`, and delayed ownership handoff when dynamic lifetime is required.
- Encapsulate low-level APIs and portability-sensitive details behind narrow wrappers.
- Keep control flow explicit when loops, switches, manual cleanup, and lock scopes interact.
- Treat borrowing vs owning pointer interfaces as an API-contract question, not just a local implementation detail.

## Candidate Canonical Rule Groups

- Ownership and lifetime: raw allocation, explicit owners, pointer contracts, and manager handoff.
- Low-level interop: system headers, standard-library C APIs, portability wrappers, and formatting boundaries.
- Concurrency: manual lock/unlock, lock scope minimization, and callback-under-lock review.
- Control flow: switch defaults, fallthrough clarity, loop-local declarations, and manual cleanup complexity.
- Boundary documentation: when contracts should be explicit but do not justify an inline defect claim.

## Reference-Only Guidance

- Prefer views, spans, and value-returning APIs where they remove pointer-plus-size ambiguity.
- Review code that mixes low-level native APIs with business logic as a design-boundary issue first and a style issue second.
- Use reference-only rules for broad guideline themes that require whole-program context or design knowledge to judge safely.
