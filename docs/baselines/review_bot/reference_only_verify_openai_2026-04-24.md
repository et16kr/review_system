# Reference-Only LLM Applicability Smoke

- created_at: `2026-04-24T13:43:55.347240+00:00`
- rule: `CPP.REF.4` / `reference_only`
- provider_status: `passed`
- stub_status: `failed`
- configured_model: `gpt-5.2`
- endpoint_base_url: `https://api.openai.com/v1`

## What This Tests

The same review comment is checked against two similar C++ diffs. The useful signal is whether the verifier can distinguish work performed while a mutex guard is in scope from work performed after the guard's inner scope ends.

## Results

### cpp_ref4_applies_blocking_callback_under_lock

- expected_applies: `True`
- openai_applies: `True`
- openai_confidence: `0.96`
- openai_passed: `True`
- stub_applies: `True`
- stub_passed: `True`
- openai_reason: 

### cpp_ref4_not_applies_work_after_lock_scope

- expected_applies: `False`
- openai_applies: `False`
- openai_confidence: `0.86`
- openai_passed: `True`
- stub_applies: `True`
- stub_passed: `False`
- openai_reason: pattern_mismatch

## Notes

- This directly exercises `provider.verify_draft`, not the full auto-publish lifecycle.
- Current retrieval/runner policy still suppresses `reference_only` rules before drafting/publishing.
- The stub verifier always accepts here, so it cannot make this applicability distinction.
