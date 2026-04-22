---
rule_source_id: bash.shell_safety
language_id: bash
dialect_id: bash
profile_hints: [default]
pack_targets: [project_bash, shell_safety]
source_type: public_guideline_summary
source_ref:
  title: Shell Safety Baseline
  url: https://mywiki.wooledge.org/BashGuide
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [bash, quoting, strict-mode, safety]
status: drafted
---

# Shell Safety Baseline

## Scope

- This bundle covers checked-in automation scripts, deployment helpers, CI shell steps, and operational glue code.
- The main review lens is trust boundaries around quoting, privilege changes, network bootstrap, and destructive filesystem mutations.

## High-Signal Review Areas

- Quote expansions unless intentional word splitting is required and clearly documented.
- Prefer strict shell options for automation that changes state, especially when pipelines or unset variables would otherwise fail silently.
- Treat remote-download-to-shell pipelines, TLS verification bypasses, and destructive deletes as high-risk patterns.
- Keep privilege escalation boundaries explicit so normal control flow is not silently coupled to `sudo` or interactive environment assumptions.

## Candidate Canonical Rule Groups

- Expansion and argv safety: quoting, arrays, command construction, and empty-path guardrails.
- Failure semantics: `set -euo pipefail`, pipeline visibility, and cleanup behavior around traps.
- Privileged automation: `sudo`, root-only operations, and separation of low-trust input from high-trust actions.
- Artifact bootstrap: `curl | bash`, `--insecure`, downloaded script verification, and explicit provenance checks.

## Reference-Only Guidance

- Prefer small shell wrappers around stable system tools instead of large application logic embedded in shell.
- Keep temporary-file cleanup, trap ownership, and environment assumptions visible at the top of the script.
- Review shell changes through the question "what expands here, with whose privileges, and against which filesystem path?"
