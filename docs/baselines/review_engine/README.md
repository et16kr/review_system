# Review-Engine Baselines

이 디렉터리는 `review-engine` deterministic validation artifact를 보존한다.

현재 예정된 artifact:

- `rule_self_test_coverage_YYYY-MM-DD.md`
  - rule self-test manifest coverage snapshot
  - `auto_review` hard-gated rule 수, waiver 수, reference-only guard 수를 기록한다.
  - coverage 감소를 판단할 때 기준 artifact로 쓴다.

Provider 품질, review-bot lifecycle, wrong-language telemetry artifact는
[../review_bot/README.md](/home/et16/work/review_system/docs/baselines/review_bot/README.md:1)에 둔다.
