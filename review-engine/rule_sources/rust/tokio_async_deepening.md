---
rule_source_id: rust.tokio_async_deepening
language_id: rust
dialect_id: null
profile_hints: [tokio_async]
pack_targets: [tokio_async]
source_type: public_guideline_summary
source_ref:
  title: Tokio Async Deepening
  url: https://tokio.rs/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [rust, tokio, async, backpressure]
status: drafted
---

# Tokio Async Deepening

## Scope

- This bundle deepens Rust review for Tokio-based services and worker code.
- It focuses on scheduler starvation, spawned-task ownership, and backpressure assumptions that are usually visible from local async code.

## Candidate Canonical Rule Groups

- Async runtime hygiene: blocking work in async functions and executor starvation.
- Task and queue ownership: detached spawn semantics, unbounded channels, and explicit backpressure stories.

## Reference-Only Guidance

- Keep cancellation, shutdown, and async test determinism obvious at the task boundary even when the exact lifecycle contract spans several modules.
