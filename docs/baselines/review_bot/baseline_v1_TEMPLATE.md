# Review Bot V1 Baseline Template

- generated_at_utc: `YYYY-MM-DDTHH:MM:SSZ`
- environment: `local | staging | prod`
- branch_or_image: `...`
- project_ref: `group/project` or `all`
- source_family: `altibase | cpp_core | all`
- observation_window_ready: `true | false`

## Health

```json
{}
```

## Canonical Quality KPIs

- `fix_confirmation_rate_14d`: `...`
- `human_resolve_rate_14d`: `...`
- `false_positive_feedback_rate_14d`: `...`
- `fix_conversion_rate_28d`: `...`

## Finding Outcomes 14d

```json
{}
```

## Finding Outcomes 28d

```json
{}
```

## Rule Effectiveness

```json
{}
```

## Selected Metrics Snapshot

```text
findings_published_total{...} 0
findings_suppressed_total{...} 0
findings_resolved_total{...} 0
feedback_commands_total{...} 0
verify_attempts_total{...} 0
verify_dropped_total{...} 0
finding_resolution_events_total{...} 0
```

## Notes

- `baseline_v1`는 새 lifecycle/verify path가 실제로 배포된 뒤 기록한다.
- 14d/28d window가 충분하지 않다면 해당 KPI를 provisional로 표시한다.
