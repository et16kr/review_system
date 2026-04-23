# Sample Private Extension Root

This example shows the minimum filesystem shape for an opt-in private
organization extension root.

Use it by pointing `REVIEW_ENGINE_EXTENSION_RULE_ROOTS` at this directory when
running `review-engine` commands or tests.

Example from the repository root:

```bash
REVIEW_ENGINE_EXTENSION_RULE_ROOTS=review-engine/examples/extensions/private_org_cpp \
uv run --project review-engine python -m review_engine.cli.ingest_guidelines
```
