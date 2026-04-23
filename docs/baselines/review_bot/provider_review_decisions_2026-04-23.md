# Provider Review Decisions 2026-04-23

- Commit: `b89db55e1eedee625f7f8d20c6939b3cfc80f97e`
- Corpus revision: `b89db55e1eedee625f7f8d20c6939b3cfc80f97e`
- Stub artifact: `docs/baselines/review_bot/provider_quality_stub_2026-04-23.md`
- OpenAI artifact: `docs/baselines/review_bot/provider_quality_openai_2026-04-23.md`
- Comparison artifact: `docs/baselines/review_bot/provider_comparison_2026-04-23.md`
- Reviewer: `codex`

## Summary

`stub` provider quality passed all 6 packaged cases. OpenAI provider quality was
skipped because `OPENAI_API_KEY` is not set in the current environment, so no
prompt, ranking, or rule tuning decision can be made from this artifact set.

| Category | Count |
| --- | ---: |
| accept_baseline | 0 |
| prompt_tune | 0 |
| ranking_tune | 0 |
| rule_gap | 0 |
| defer | 6 |

## Case Decisions

| Case | Decision | Evidence | Follow-up |
| --- | --- | --- | --- |
| `yaml_ci_remote_script_execution` | `defer` | OpenAI artifact skipped due missing API key | Re-run OpenAI artifact capture with `OPENAI_API_KEY` |
| `python_fastapi_untyped_request_body` | `defer` | OpenAI artifact skipped due missing API key | Re-run OpenAI artifact capture with `OPENAI_API_KEY` |
| `python_fastapi_blocking_io` | `defer` | OpenAI artifact skipped due missing API key | Re-run OpenAI artifact capture with `OPENAI_API_KEY` |
| `sql_ordinal_group_by` | `defer` | OpenAI artifact skipped due missing API key | Re-run OpenAI artifact capture with `OPENAI_API_KEY` |
| `cuda_async_default_stream` | `defer` | OpenAI artifact skipped due missing API key | Re-run OpenAI artifact capture with `OPENAI_API_KEY` |
| `cuda_cooperative_groups_grid_sync` | `defer` | OpenAI artifact skipped due missing API key | Re-run OpenAI artifact capture with `OPENAI_API_KEY` |

## Next Action

Do not change prompt templates, ranking weights, source atoms, or rule policy from
this skipped comparison. The next valid step is to run the same provider quality
and comparison workflow in an environment where `OPENAI_API_KEY` is available,
then replace these `defer` decisions with case-specific `accept_baseline`,
`prompt_tune`, `ranking_tune`, or `rule_gap` decisions.
