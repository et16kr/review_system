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
