---
rule_source_id: rust.rust_runtime_baseline
language_id: rust
dialect_id: null
profile_hints: [default]
pack_targets: [project_rust]
source_type: public_guideline_summary
source_ref:
  title: Rust Runtime Review Baseline
  url: https://doc.rust-lang.org/book/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [rust, unsafe, panic, ownership]
status: drafted
---

# Rust Runtime Baseline

## Scope

- This bundle covers Rust panic boundaries, unsafe containment, and API contracts around caller invariants.
- The goal is to capture reviewable operational risks, not to restate the entire language ownership model.

## High-Signal Review Areas

- Keep `unsafe` narrow and document the invariant it relies on.
- Treat `extern "C"` functions as FFI boundaries where ownership, nullability, lifetime, and panic behavior need an explicit contract.
- Treat `unwrap`, `expect`, `panic!`, `dbg!`, and `todo!` as explicit crash or debug boundaries.
- Prefer error propagation over hidden panic behavior in normal operation.
- Review `unsafe fn` signatures as caller-contract boundaries that must explain what remains the caller's responsibility.

## Candidate Canonical Rule Groups

- Panic behavior: unwrap/expect, panic macros, placeholder macros, and crash contracts.
- Unsafe containment: tiny unsafe blocks, safe wrappers, caller invariants, FFI boundaries, and `unsafe fn`.
- Debug residue: `dbg!` and temporary instrumentation leaking into runtime paths.
- Boundary clarity: when a panic is intentional, what invariant makes it acceptable?

## Reference-Only Guidance

- Use reference-only rules for broader API design topics such as clone minimization, iterator style, or trait ergonomics unless the patch exposes a concrete failure mode.
- Review Rust with the question "where does this code leave the safe subset, and who is now responsible for the invariant?"
