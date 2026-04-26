# Rule Self-Test Coverage Baseline - 2026-04-26

- generated_at: `2026-04-27`
- source_of_truth: `review-engine/examples/rule_self_tests/manifest.yaml`
- enabled_rule_entries: 361
- auto_review_rule_entries: 265
- reference_only_rule_entries: 96
- reviewable_direct_detector_backed_auto_rules: 258
- hard_gated_reviewable_direct_detector_backed_auto_rules: 258
- cxx_detector_gap_auto_rules: 0
- shared_auto_rules_pending_host_validation: 0
- shared_auto_rules_explicit_shared_cases: 7
- shared_auto_rules_host_language_validated: 7
- reference_only_rules_accounted_by_case_or_waiver: 96

## Scope Notes

This baseline records deterministic self-test coverage for reviewable language rules that have a direct detector hint and an applicability-compatible trigger pattern.

The C++ detector-gap unit is closed. All enabled reviewable C++ `auto_review`
rules now have direct detector-backed accepted self-test coverage.

Shared `SEC.*` auto-review rules are covered twice:

- explicit `language_id=shared` self-test cases validate direct shared rule behavior
- host-language cases validate that Python, JavaScript, TypeScript, Java, and Go reviews run shared security detector signals and return `shared` rule results
