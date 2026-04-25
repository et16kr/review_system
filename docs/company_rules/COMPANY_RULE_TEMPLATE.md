# Company Rule Template

Use this Markdown template with the
[Company Rule Authoring Guide](AUTHORING_GUIDE.md). Authors do not need to know
the internal YAML schema while drafting a rule. After review, an implementer can
translate approved content into a canonical YAML rule pack.

If automatic review safety is uncertain, choose `reference_only` or
`manual_only` first.

## Rule Identity

- Rule id:
- Title:
- Language or file family:
- Scope/profile:
- Status: draft
- Reviewability: reference_only
- Severity:
- Owner:
- Approver:

## Intent

Describe the risk, reliability issue, security concern, maintainability cost, or
style rule this is meant to address.

## Rule Statement

State the rule in reviewer-facing language. Prefer one concrete requirement over
several loosely related requirements.

## Bad Example

```text
Replace this block with a minimal example that should be flagged.
```

Why this is bad:

-

## Good Example

```text
Replace this block with a minimal example that should be accepted.
```

Why this is good:

-

## Exceptions

List cases where the rule should not apply, including legacy compatibility,
generated code, tests, framework constraints, or approved migration windows.

-

## Detection Hints

List concrete implementation signals. Examples include API names, AST patterns,
config keys, file paths, dependency names, import patterns, query shapes, or
runtime lifecycle conditions.

-

## Source And Provenance

- Source document:
- Source section:
- Source version or revision:
- Source URL or internal path:
- Original author/team:
- Approval record:
- Last reviewed date:
- Public, private, or organization-only:

## Rollout Note

- Initial pack/profile:
- Enablement plan:
- Validation command:
- Regression required: yes/no
- Rollback or disable expectation:

## Reviewability Notes

Choose one:

- `auto_review`: detection is clear, action is concrete, examples and exceptions
  are available, and validation coverage is planned.
- `reference_only`: useful context, but automatic inline findings need more
  evidence or a product/risk decision.
- `manual_only`: requires human judgement or context outside the diff.

Reason for chosen reviewability:

-
