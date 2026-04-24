# Provider Comparison Triage Packet 2026-04-24

- Purpose: human review input for default OpenAI provider quality deltas.
- Decision status: `review_input_only`
- Tuning status: `not_approved`
- Stub artifact: `docs/baselines/review_bot/provider_quality_stub_2026-04-24.json`
- OpenAI artifact: `docs/baselines/review_bot/provider_quality_openai_2026-04-24.json`
- Comparison artifact: `docs/baselines/review_bot/provider_comparison_2026-04-24.json`
- Comparison summary: `docs/baselines/review_bot/provider_comparison_2026-04-24.md`
- Stub status: `passed`
- OpenAI status: `failed`
- Compared cases: `6`
- Human review required: `true`
- Recommended next action: `review_provider_deltas_before_tuning`

## Provenance

| Provider | Runtime |
| --- | --- |
| stub | `configured_provider=stub`, `effective_provider=stub`, `fallback_used=false`, `transport_class=deterministic_stub` |
| openai | `configured_provider=openai`, `effective_provider=openai`, `fallback_used=false`, `configured_model=gpt-5.2`, `endpoint_base_url=https://api.openai.com/v1`, `transport_class=default_openai_base_url` |

This packet uses retained artifacts only. It does not prove a fresh live OpenAI run in
the current shell, and it must not be used as a tuning approval by itself.

## Mechanical Bucket Summary

| Bucket | Cases | Triage meaning |
| --- | ---: | --- |
| `suggested_fix_length` | 6 | OpenAI drafts exceeded the deterministic length gate or were much longer than stub output. |
| `missing_required_terms` | 2 | OpenAI drafts missed a required term enforced by the packaged case. |
| `line/evidence` | 0 | No line anchor mismatch was reported; OpenAI drafts included evidence snippets. |
| `should_publish` | 0 | OpenAI and stub both produced `should_publish=true` for every compared case. |

## Case Triage

| Case | OpenAI status | Buckets | Evidence anchor | should_publish | Human question |
| --- | --- | --- | --- | --- | --- |
| `cuda_async_default_stream` | `failed` | `suggested_fix_length` | line `11`; `cudaMemcpyAsync(host_dst, device_src, bytes, cudaMemcpyDeviceToHost, 0);` | stub `true`, OpenAI `true` | Is the longer OpenAI fix acceptable, or should the draft stay within the CUDA review UI length gate? |
| `cuda_cooperative_groups_grid_sync` | `failed` | `suggested_fix_length` | line `14`; `grid.sync();` | stub `true`, OpenAI `true` | Does the extra cooperative-launch detail improve actionability enough to justify a prompt or length-budget change? |
| `python_fastapi_blocking_io` | `failed` | `suggested_fix_length`, `missing_required_terms` | line `21`; `result = requests.get(url, timeout=5)` | stub `true`, OpenAI `true` | Should the required term gate accept the Korean/English mixed phrasing, or should the prompt force the literal `blocking` term? |
| `python_fastapi_untyped_request_body` | `failed` | `suggested_fix_length` | line `18`; `payload = await request.json()` | stub `true`, OpenAI `true` | Is the long Pydantic example useful reviewer guidance, or should examples be compressed for review UI density? |
| `sql_ordinal_group_by` | `failed` | `missing_required_terms` | line `34`; `GROUP BY 1, 2` | stub `true`, OpenAI `true` | Should the required term gate require literal `explicit`, or is `명시적` enough for this localized draft? |
| `yaml_ci_remote_script_execution` | `failed` | `suggested_fix_length` | line `12`; `curl -fsSL https://example.com/install.sh \| bash` | stub `true`, OpenAI `true` | Is the checksum example useful enough to permit a longer suggested fix, or should this be shortened before publishing? |

## Decision Checklist For Human Review

For each case, choose exactly one decision before any follow-up tuning work:

- `accept_baseline`: keep current prompt/ranking/rule gates.
- `prompt_tune`: change the provider prompt and add a deterministic regression.
- `ranking_tune`: change ranking or density selection and add a deterministic regression.
- `rule_gap`: change rule metadata, required terms, or packaged case expectations.
- `defer`: keep the evidence but do not change behavior yet.

Do not change prompt templates, ranking weights, rule source, density thresholds, or
publish policy from this packet alone.
