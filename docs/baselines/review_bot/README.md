# Review Bot Baselines

Phase A instrumentation baseline snapshots are stored here.

Recommended files:

- `baseline_v0_YYYY-MM-DD.md`
- `baseline_v1_YYYY-MM-DD.md`
- `wrong_language_28d_YYYY-MM-DD.md`
- `wrong_language_backlog_28d_YYYY-MM-DD.md`
- `provider_quality_stub_YYYY-MM-DD.md`
- `provider_quality_openai_YYYY-MM-DD.md`
- `provider_ranking_density_YYYY-MM-DD.md`
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
Provider/ranking/density snapshots combine the deterministic provider quality gate with
the smoke fixture density contract so publish volume and file spread changes are visible.

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
  --output ../docs/baselines/review_bot/provider_quality_stub_$(date -u +%F).md
```

Provider/ranking/density helper:

```bash
cd /home/et16/work/review_system/review-bot
uv run pytest tests/test_multilang_smoke_fixture.py tests/test_provider_quality.py -q
cd /home/et16/work/review_system
bash ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture synthetic-mixed-language \
  --json-output /tmp/review-bot-multilang-smoke.json
```
