---
rule_source_id: go.go_runtime_baseline
language_id: go
dialect_id: null
profile_hints: [default]
pack_targets: [project_go]
source_type: public_guideline_summary
source_ref:
  title: Go Runtime Review Baseline
  url: https://go.dev/doc/effective_go
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [go, errors, defer, context, http, validation]
status: drafted
---

# Go Runtime Baseline

## Scope

- This bundle covers Go request-scoped work, cleanup, goroutine ownership, error propagation, and HTTP transport boundaries.
- The review emphasis is on control over lifetime and failure visibility rather than purely stylistic Effective Go advice.

## High-Signal Review Areas

- Check errors directly and consistently.
- Prefer `errors.Is` or `errors.As` when sentinel or typed errors may cross wrapping boundaries.
- Attach cleanup with `defer` as soon as the resource is acquired.
- Propagate `context` through request-scoped work and reason about goroutine ownership.
- Make HTTP request decoding and validation boundaries visible before handler code reaches domain work.
- Treat `context.Background()` or `context.TODO()` in service paths as an explicit ownership decision.
- Review `panic` in request, worker, or library code as a crash-boundary decision that usually deserves typed errors instead.

## Candidate Canonical Rule Groups

- Error handling: ignored errors, wrapped errors, and operation context in returned failures.
- Sentinel error matching: `errors.Is` / `errors.As` for wrapper-aware branches on typed or sentinel failures.
- Cleanup: prompt `defer`, response body closure, and lexical ownership.
- Transaction cleanup: `Begin` / `Commit` paths should keep rollback ownership visible from the start.
- HTTP handler validation boundaries: raw JSON decoding, including retained decoder variables, should be followed by an explicit request contract check before domain use.
- Concurrency: goroutine launch ownership, cancellation, and anonymous goroutine behavior.
- Context propagation: request cancellation, deadline inheritance, and detached work.

## Reference-Only Guidance

- Prefer API shapes that make zero values, ownership, and cancellation behavior obvious to callers.
- Treat concurrency review as "who owns this work and when does it stop?" rather than only "is a goroutine present?"
