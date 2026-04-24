# Review Bot Baselines

Phase A instrumentation baseline snapshots are stored here.

Recommended files:

- `baseline_v0_YYYY-MM-DD.md`
- `baseline_v1_YYYY-MM-DD.md`
- `lifecycle_smoke_YYYY-MM-DD.json`
- `multilang_smoke_<fixture_id>_YYYY-MM-DD.json`
- `wrong_language_28d_YYYY-MM-DD.md`
- `wrong_language_backlog_28d_YYYY-MM-DD.md`
- `direct_openai_smoke_YYYY-MM-DD.txt`
- `direct_openai_smoke_openai_compatible_local_YYYY-MM-DD.txt`
- `provider_quality_stub_YYYY-MM-DD.md`
- `provider_quality_openai_YYYY-MM-DD.md`
- `provider_quality_openai_compatible_local_YYYY-MM-DD.md`
- `provider_comparison_YYYY-MM-DD.md`
- `provider_comparison_openai_compatible_local_YYYY-MM-DD.md`
- `provider_review_decisions_YYYY-MM-DD.md`
- `provider_ranking_density_YYYY-MM-DD.md`
- `review_unit_split_audit_YYYY-MM-DD.md`
- `targeted_rule_expansion_evidence_YYYY-MM-DD.md`
- `baseline_v0_TEMPLATE.md`
- `baseline_v1_TEMPLATE.md`

Suggested contents:

- deployment date and branch/commit
- `review-bot` build or image version
- key operational metrics snapshot
- `/internal/analytics/rule-effectiveness` output summary
- `/internal/analytics/finding-outcomes` output summary

`baseline_v0` is intended for pre-Phase-A or instrumentation bootstrap snapshots.
`baseline_v1` should be recorded after the new lifecycle/verify analytics path has been
deployed long enough to accumulate a meaningful 14d/28d window.
Wrong-language snapshots may include synthetic smoke feedback unless captured with a
production project filter or interpreted with smoke project refs excluded.
Provider quality snapshots compare provider draft quality against the packaged corpus.
The `stub` snapshot is deterministic and network-free; `openai` is an opt-in artifact
for human review and should not be required in default CI.
If `BOT_OPENAI_BASE_URL` is non-default, keep a separate local-backend artifact name and
use the embedded `provider_runtime` provenance (`configured_model`, `endpoint_base_url`,
`transport_class`) to distinguish it from the default OpenAI baseline.
Direct smoke stdout captures use separate filenames for default OpenAI and local backend
endpoints. A direct smoke capture is provider-success evidence only when it was run with
`--expect-live-openai`, exited `0`, and includes both `models_probe_status=ok` and a
`live_probe_model=...` line. Otherwise it is a diagnostic artifact.
Provider comparison snapshots summarize stub/OpenAI deltas and include a human-review
checklist. If `OPENAI_API_KEY` is unavailable, the comparison can still be captured as
`openai_status=skipped` without changing prompt or ranking weights.
Provider review decision snapshots record the human decision for each comparison case:
`accept_baseline`, `prompt_tune`, `ranking_tune`, `rule_gap`, or `defer`.
Provider/ranking/density snapshots combine the deterministic provider quality gate with
the smoke fixture density contract so publish volume and file spread changes are visible.
Review-unit split audit snapshots record which languages still need syntax-aware split
after the current fixed-line hunk splitter is applied to the deterministic long-hunk corpus.
Targeted rule expansion evidence snapshots record why the next rule family was selected
before any new canonical rule source, detector, or fixture work begins.
Retained smoke JSON artifacts should live next to these Markdown baselines instead of
only in `/tmp`.

Regular checkpoint bundle:

- keep retained smoke JSON as `lifecycle_smoke_YYYY-MM-DD.json` and
  `multilang_smoke_<fixture_id>_YYYY-MM-DD.json`
- pair wrong-language review work with `wrong_language_28d_YYYY-MM-DD.md` and
  `wrong_language_backlog_28d_YYYY-MM-DD.md` from the same checkpoint date
- use `/tmp` only for ad hoc iteration; if a smoke run is part of the baseline, rerun it
  with the canonical `docs/baselines/review_bot/` output path
- if local GitLab is unavailable and smoke is intentionally skipped, record that skip in
  the roadmap or change note rather than creating an empty placeholder artifact

Capture helper:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_review_bot_baseline.py \
  --baseline-kind v0
```

Provider quality helper:

```bash
cd /home/et16/work/review_system/review-bot
uv run python -m review_bot.cli.evaluate_provider_quality \
  --provider stub \
  --output ../docs/baselines/review_bot/provider_quality_stub_$(date -u +%F).md \
  --json-output /tmp/provider_quality_stub.json
uv run python -m review_bot.cli.evaluate_provider_quality \
  --provider openai \
  --output ../docs/baselines/review_bot/provider_quality_openai_$(date -u +%F).md \
  --json-output /tmp/provider_quality_openai.json
uv run python -m review_bot.cli.compare_provider_quality \
  --stub-json /tmp/provider_quality_stub.json \
  --openai-json /tmp/provider_quality_openai.json \
  --output ../docs/baselines/review_bot/provider_comparison_$(date -u +%F).md \
  --json-output /tmp/provider_comparison.json
```

For a non-default `BOT_OPENAI_BASE_URL`, use separate retained filenames such as
`direct_openai_smoke_openai_compatible_local_YYYY-MM-DD.txt`,
`provider_quality_openai_compatible_local_YYYY-MM-DD.md` and
`provider_comparison_openai_compatible_local_YYYY-MM-DD.md`.

Local backend capture checklist:

- `BOT_OPENAI_BASE_URL` is non-default and points at the intended OpenAI-compatible `/v1`
  endpoint.
- `BOT_OPENAI_MODEL` names the backend model under test.
- `OPENAI_API_KEY` is set to the real key or backend-accepted placeholder used for the run.
- direct smoke, provider quality, and comparison retained filenames use the
  `openai_compatible_local` suffix.
- artifact `provider_runtime.endpoint_base_url`, `configured_model`, and `transport_class`
  match the intended backend.
- `capture_success` means direct smoke provider-success evidence plus provider quality
  `status=passed`; comparison `human_review_required=true` still requires a decision
  artifact before tuning.
- `skipped`, transport failure, provenance mismatch, or missing provider-quality JSON means
  `defer`, not tuning evidence.

Provider/ranking/density helper:

```bash
cd /home/et16/work/review_system/review-bot
uv run pytest tests/test_multilang_smoke_fixture.py tests/test_provider_quality.py -q
cd /home/et16/work/review_system
bash ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture synthetic-mixed-language \
  --json-output docs/baselines/review_bot/multilang_smoke_synthetic-mixed-language_$(date -u +%F).json
python3 ops/scripts/capture_wrong_language_telemetry.py \
  --window 28d \
  --output docs/baselines/review_bot/wrong_language_28d_$(date -u +%F).md
python3 ops/scripts/build_wrong_language_backlog.py \
  --window 28d \
  --output docs/baselines/review_bot/wrong_language_backlog_28d_$(date -u +%F).md
```

Review-unit split audit helper:

```bash
cd /home/et16/work/review_system/review-bot
uv run python -m review_bot.cli.review_unit_split_audit \
  --output ../docs/baselines/review_bot/review_unit_split_audit_$(date -u +%F).md
```

Targeted rule expansion evidence refresh:

Use this path before choosing the next rule family to expand. The decision must be
driven by fresh retained evidence, not by whichever language or rule pack is convenient
to edit.

Evidence order:

1. Reuse the newest repo-local retained artifact named
   `targeted_rule_expansion_evidence_YYYY-MM-DD.md` when it is fresh enough.
2. If no fresh artifact exists, inspect local review-bot analytics:
   `/internal/analytics/finding-outcomes?window=28d`,
   `/internal/analytics/rule-effectiveness`, and
   `/internal/analytics/wrong-language-feedback?window=28d`.
3. If analytics are unavailable or empty, use retained local smoke artifacts only when
   they expose a concrete fixture regression or density/language-tag contract gap.

Freshness rule:

- default automation may use a same-day UTC artifact without further review
- a human-named artifact may be reused for up to 7 UTC days if it still matches the
  current branch and validation baseline
- older artifacts, empty analytics, or unrelated smoke passes are not enough to choose
  a rule family

Recommended artifact fields:

- `generated_at_utc`
- `source_order_used`
- `review_bot_baseline_artifacts`
- `analytics_endpoints`
- `smoke_artifacts`
- `candidate_rule_families`
- `selected_rule_family`
- `freshness_decision`
- `blocked_reason` if no family can be selected

When no fresh evidence exists, stop the rule expansion work and report a blocker using
the roadmap automation blocked-unit format:

```text
BLOCKED_UNIT: Evidence Refresh Path For Targeted Rule Expansion
BLOCKER_TYPE: external_services
BLOCKED_REASON: review-bot analytics were unavailable or empty, and no fresh retained smoke artifact identified a concrete rule gap.
```

If a smoke refresh is required but local GitLab is not ready, use
`BLOCKER_TYPE: local_gitlab_state` and do not create an empty evidence artifact.

Lifecycle smoke helper:

```bash
cd /home/et16/work/review_system
bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh \
  --json-output docs/baselines/review_bot/lifecycle_smoke_$(date -u +%F).json
```
