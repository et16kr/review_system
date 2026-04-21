# Review Bot Baselines

Phase A instrumentation baseline snapshots are stored here.

Recommended files:

- `baseline_v0_YYYY-MM-DD.md`
- `baseline_v1_YYYY-MM-DD.md`
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

Capture helper:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_review_bot_baseline.py \
  --baseline-kind v0
```
