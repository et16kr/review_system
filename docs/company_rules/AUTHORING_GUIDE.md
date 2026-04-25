# Company Rule Authoring Guide

## Purpose

Use this guide before converting company coding standards into review-engine rule
packs. The intake source is a human-readable Markdown document based on
[COMPANY_RULE_TEMPLATE.md](COMPANY_RULE_TEMPLATE.md). The implementation output,
when a rule is ready, is still a canonical YAML rule pack reviewed through Git.

Private and organization-specific rules follow the same model as public rules:
canonical YAML plus Git review is the source of truth. A web editor, local
harness, or generated vector artifact may assist validation, but it must not
become the authoritative rule state.

## Intake Flow

1. Write the original rule in Markdown with clear ownership and source material.
2. Classify the rule's reviewability as `auto_review`, `reference_only`, or
   `manual_only`.
3. Record the source, provenance, owner, approval path, rollout note, validation
   command, and whether regression coverage is required.
4. Convert only approved and scoped rules into canonical YAML rule entries.
5. Preview and validate the rule pack before it is enabled for review traffic.
6. Review the canonical YAML diff through Git, then roll out by profile or pack.

Do not edit generated datasets, Chroma collections, or runtime artifacts by hand.
Those are derived outputs from canonical rule files and validation commands.

## Reviewability

Use the most conservative classification that matches the available evidence.
If automatic review safety is unclear, start with `reference_only` or
`manual_only`.

`auto_review`

- The rule has a clear, inspectable code signal.
- A review comment can point to an actionable fix or concrete risk.
- Bad and good examples exist for the relevant language or framework.
- Known exceptions are documented.
- False-positive risk is acceptable for the target profile.
- Validation and regression coverage are identified before rollout.

`reference_only`

- The rule is useful context for reviewer judgement, backlog analysis, reports,
  or LLM applicability checks.
- The signal may be context-heavy, style-sensitive, or not yet backed by enough
  examples.
- The rule should not publish automatic inline findings until promotion criteria
  and validation evidence are reviewed.

`manual_only`

- The rule depends on team-specific judgement, architecture intent, product risk,
  legal approval, or information outside the diff.
- The expected action cannot be reliably inferred from changed code alone.
- The rule can be documented for reviewers, but the bot should not auto-detect
  or auto-publish findings for it.

## Required Metadata

Each intake document must include:

- `rule id`: stable ASCII identifier proposed by the owning team.
- `title`: short reviewer-facing name.
- `language`: target language, framework, or file family.
- `scope/profile`: target repository area, rule pack, or review profile.
- `status`: draft, proposed, approved, enabled, disabled, or deprecated.
- `reviewability`: `auto_review`, `reference_only`, or `manual_only`.
- `severity`: reviewer impact level and rationale.
- `intent`: what risk or maintenance cost the rule prevents.
- `bad example` and `good example`: minimal examples when applicable.
- `exceptions`: documented cases where the rule should not fire.
- `detection hints`: concrete signals, AST patterns, filenames, APIs, or
  semantic checks that may help implementation.
- `source/provenance`: source document, section, version, URL or internal path,
  author, review date, and approval record.
- `rollout note`: initial profile, enablement plan, validation command, and
  rollback expectation.
- `regression requirement`: whether runtime, lifecycle CLI, source coverage, or
  fixture coverage is required before enabling the rule.

## Validation Entry Points

For previewing a candidate rule pack from `review-engine`:

```bash
uv run python -m review_engine.cli.rule_lifecycle preview ...
```

For rule runtime and lifecycle CLI regression checks when the canonical YAML or
lifecycle contract changes:

```bash
uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
```

Additional source coverage, private extension, or package validation may be
required when the rule changes public source manifests, private extension roots,
or profile/package boundaries.

## Editor Boundary

A v0 editor may assist with:

- Viewing canonical YAML rule entries.
- Showing preview output and validation results.
- Enabling or disabling existing canonical YAML rules or packs.
- Helping authors fill intake metadata consistently.

The following remain deferred and must not be introduced as part of intake
documentation work:

- Free-form web authoring that bypasses Git review.
- DB-backed rule state as the source of truth.
- Direct edits to generated datasets, vector stores, or runtime artifacts.
- Private rule package install/update automation without a validated package
  manifest, rollback model, and validation gate.

## Ready For Conversion Checklist

- The template is complete and linked to source material.
- The owner and approver are explicit.
- Reviewability is conservative and justified.
- Automatic review candidates include examples, exceptions, detection hints, and
  validation expectations.
- Rollout starts with the narrowest practical profile.
- The canonical YAML diff and validation result can be reviewed together in Git.
