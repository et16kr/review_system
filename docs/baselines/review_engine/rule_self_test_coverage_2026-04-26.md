# Rule Self-Test Coverage Baseline - 2026-04-26

- generated_at: `2026-04-26`
- source_of_truth: `review-engine/examples/rule_self_tests/manifest.yaml`
- enabled_rule_entries: 361
- auto_review_rule_entries: 265
- reference_only_rule_entries: 96
- reviewable_direct_detector_backed_auto_rules: 243
- hard_gated_reviewable_direct_detector_backed_auto_rules: 243
- cxx_detector_gap_auto_rules: 15
- shared_auto_rules_pending_host_validation: 7
- reference_only_rules_accounted_by_case_or_waiver: 96

## Scope Notes

This baseline records deterministic self-test coverage for reviewable language rules that have a direct detector hint and an applicability-compatible trigger pattern.

The remaining C++ rules are the queued detector-gap unit:

- `cpp:CPP.PROJ.1`
- `cpp:CPP.PROJ.2`
- `cpp:CPP.PROJ.3`
- `cpp:CPP.PROJ.4`
- `cpp:CPP.PROJ.5`
- `cpp:CPP.PROJ.6`
- `cpp:F.7`
- `cpp:I.12`
- `cpp:NM.1`
- `cpp:NM.2`
- `cpp:NM.3`
- `cpp:NM.4`
- `cpp:R.13`
- `cpp:R.33`
- `cpp:R.37`

Shared `SEC.*` auto-review rules remain queued for host-language validation because `language_id=shared` is not a reviewable runtime surface:

- `shared:SEC.1`
- `shared:SEC.2`
- `shared:SEC.3`
- `shared:SEC.4`
- `shared:SEC.5`
- `shared:SEC.6`
- `shared:SEC.7`
