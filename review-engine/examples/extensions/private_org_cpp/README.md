# Sample Private Extension Root

This example shows the minimum filesystem shape for an opt-in private
organization extension root.

Use it by pointing `REVIEW_ENGINE_EXTENSION_RULE_ROOTS` at this directory when
running `review-engine` commands or tests.

Prod or release-gate example from the repository root:

```bash
REVIEW_ENGINE_EXTENSION_RULE_ROOTS=review-engine/examples/extensions/private_org_cpp \
REVIEW_ENGINE_STRICT_EXTENSION_LOADING=1 \
uv run --project review-engine python -m review_engine.cli.ingest_guidelines
```

Local dev example when iterating on optional extension entry-point packaging:

```bash
REVIEW_ENGINE_EXTENSION_RULE_ROOTS=review-engine/examples/extensions/private_org_cpp \
REVIEW_ENGINE_STRICT_EXTENSION_LOADING=0 \
uv run --project review-engine pytest review-engine/tests/test_rule_runtime.py -q
```

Notes:

- `REVIEW_ENGINE_STRICT_EXTENSION_LOADING=0` only relaxes invalid extension
  entry-point payloads into warning-plus-fallback behavior.
- If this filesystem root contains a broken `manifest.yaml` or invalid pack/profile/policy
  YAML, `review-engine` still fails fast because the operator explicitly selected
  the root via `REVIEW_ENGINE_EXTENSION_RULE_ROOTS`.

Canonical authoring surface:

- `pack_weight` lives in `policies/*.yaml` `pack_weights`; this sample keeps
  `cpp_core=0.72` and `org_cpp=0.97` in
  [policies/org_default.yaml](/home/et16/work/review_system/review-engine/examples/extensions/private_org_cpp/policies/org_default.yaml:1).
- `reference_only` is authored with `reviewability: reference_only` on the rule
  entry itself. The sample
  [packs/org_cpp.yaml](/home/et16/work/review_system/review-engine/examples/extensions/private_org_cpp/packs/org_cpp.yaml:1)
  uses `ORG.REF.1` as the canonical reference-only example.
- conflict actions are runtime resolution state, not a separate rule-entry toggle.
  Keep rule entry `default_action` and policy `defaults.conflict_action` at
  `compatible`; use policy `overrides`/`exclusions` when a rule must become
  `overridden` or `excluded`.
