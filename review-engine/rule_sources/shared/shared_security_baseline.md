---
rule_source_id: shared.shared_security_baseline
language_id: shared
dialect_id: null
profile_hints: [default]
pack_targets: [shared_security, review_process]
source_type: public_guideline_summary
source_ref:
  title: Shared Secure Review Baseline
  url: https://example.invalid/review-engine/shared-security
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [security, secrets, shell, sql]
status: drafted
---

# Shared Security Baseline

## Scope

- This bundle captures cross-language security review themes that recur in code, config, build artifacts, and automation.
- It is intentionally small but reusable across all language profiles.

## High-Signal Review Areas

- Secrets belong in runtime configuration or secret stores, not source.
- Command execution should use structured arguments instead of interpolated shell strings.
- SQL values should be parameterized rather than concatenated into query text.
- Treat fallback credentials, demo secrets, and test-only tokens in committed code as real operational risk, not harmless convenience.

## Candidate Canonical Rule Groups

- Secret handling: committed tokens, fallback passwords, long-lived credentials, and runtime injection.
- Command construction: shell interpolation, executable/argument separation, and trusted primitive construction.
- Query safety: bound values, structural allow-lists, and the line between dynamic structure and injection.
- Review process overlays: trust-boundary naming, safer reconstruction guidance, and when to downgrade to reference-only guidance.

## Reference-Only Guidance

- Not every security concern should become an inline defect claim; use reference-only rules when whole-program trust context is missing.
- Review cross-language security with the question "what untrusted value crosses into executable behavior, privileged operation, or persistent query structure here?"
