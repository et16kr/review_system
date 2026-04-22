---
rule_source_id: python.python_runtime_baseline
language_id: python
dialect_id: null
profile_hints: [default, typed_python]
pack_targets: [pep8_python, pep257_docstrings, project_python]
source_type: public_guideline_summary
source_ref:
  title: Python Runtime Review Baseline
  url: https://peps.python.org/pep-0008/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [python, typing, context-manager, exceptions]
status: drafted
---

# Python Runtime Baseline

## Scope

- This bundle covers Python exception handling, context managers, dynamic execution, serialization trust boundaries, and public API contracts.
- The review focus is on runtime behavior that can be inferred from patch-local evidence rather than framework-specific style nits.

## High-Signal Review Areas

- Avoid mutable default arguments and bare or overly broad exception handling.
- Prefer context managers for resources with close semantics.
- Keep shell execution and eval-like behavior behind explicit trust boundaries.
- Review `assert` as a debug aid, not a dependable runtime validation mechanism for external input or application invariants.
- Treat unsafe deserialization helpers such as `yaml.load` as strong trust-boundary decisions.

## Candidate Canonical Rule Groups

- Function defaults and contracts: mutable defaults, public docstrings, mutation visibility, and exception promises.
- Exception boundaries: bare except, `except Exception`, re-raise behavior, and traceback preservation.
- Resource ownership: `with`, file/socket/process lifetime, and cleanup adjacency.
- Dynamic execution and parsing: `shell=True`, `eval/exec`, unsafe YAML loading, and parser alternatives.

## Reference-Only Guidance

- Prefer concise docstrings for public APIs whose mutation, return shape, or exception behavior is not obvious from the signature alone.
- Review Python changes through the question "is this boundary depending on convention, or is the contract explicit in code and cleanup structure?"
