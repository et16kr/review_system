# Rule Self-Test Coverage Baseline - 2026-04-26

- generated_at: `2026-04-26`
- source_of_truth: `review-engine/examples/rule_self_tests/manifest.yaml`
- enabled_rule_entries: 361
- auto_review_rule_entries: 265
- reference_only_rule_entries: 96
- reviewable_direct_detector_backed_auto_rules: 258
- hard_gated_reviewable_direct_detector_backed_auto_rules: 258
- cxx_detector_gap_auto_rules: 0
- shared_auto_rules_pending_host_validation: 7
- reference_only_rules_accounted_by_case_or_waiver: 96

## Scope Notes

This baseline records deterministic self-test coverage for reviewable language rules that have a direct detector hint and an applicability-compatible trigger pattern.

The C++ detector-gap unit is closed. All enabled reviewable C++ `auto_review`
rules now have direct detector-backed accepted self-test coverage.

Shared `SEC.*` auto-review rules remain queued for host-language validation because `language_id=shared` is not a reviewable runtime surface:

- `shared:SEC.1`
- `shared:SEC.2`
- `shared:SEC.3`
- `shared:SEC.4`
- `shared:SEC.5`
- `shared:SEC.6`
- `shared:SEC.7`
