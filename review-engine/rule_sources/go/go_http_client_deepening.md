---
rule_source_id: go.go_http_client_deepening
language_id: go
dialect_id: null
profile_hints: [default]
pack_targets: [project_go]
source_type: public_guideline_summary
source_ref:
  title: Go net/http Package Documentation
  url: https://pkg.go.dev/net/http
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [go, http, client, timeout, response-body]
status: drafted
---

# Go HTTP Client Deepening

## Scope

- This bundle deepens Go review for outbound HTTP client calls where timeout and response-body ownership should be clear from the local patch.
- It focuses on call-site review signals rather than broad transport tuning, retry policy, or whole-service latency design.

## Candidate Canonical Rule Groups

- HTTP client timeout ownership: package-level HTTP helpers, default clients, and client literals without an explicit `Timeout` leave outbound deadline ownership invisible unless a caller context or deadline path is obvious.
- Response body ownership: successful outbound HTTP responses should attach `resp.Body.Close()` in the same local scope before reading or otherwise consuming the body.
