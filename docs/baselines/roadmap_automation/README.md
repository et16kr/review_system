# Roadmap Automation Baselines

Retained artifacts for roadmap-advancement automation live here.

Recommended files:

- `blocked_roadmap_units_YYYY-MM-DD.md`

Retention rules:

- keep one Markdown file per UTC date when a run actually encountered blockers
- append one entry per blocked roadmap unit that automation skipped in that day's file
- do not create empty placeholder files when no blocker was observed
- keep transient Codex prompt/output scratch files in `/tmp`; only the normalized blocked
  summary belongs in this directory

Required entry fields:

- `date`
- `attempt`
  - `advance_roadmap_with_codex.sh` 한 번의 실행 안에서의 iteration 번호를 그대로 사용한다
- `blocked_unit`
- `reason`

Optional entry fields:

- `blocker_type`
- `validation_summary`
- `notes`
- `status`

Suggested entry shape:

```md
# Blocked Roadmap Units - 2026-04-24

## Attempt 1
- date: `2026-04-24`
- attempt: `1`
- blocked_unit: `Targeted Rule Expansion / fresh telemetry or smoke checkpoint artifact`
- reason: `Local review-bot API and analytics endpoints were unavailable, so the checkpoint evidence could not be captured.`
- status: `STATUS: BLOCKED`
```

This format keeps the canonical fields stable for future append automation while still
leaving room for extra validation context when a blocker needs more explanation.
