# Review Findings Backlog

## Purpose

이 문서는 `docs/reviews/CURRENT_STATE_REVIEW.md`에서 나온 `gpt-5.5` 리뷰 후속 작업 후보를 모은다.
이전 리뷰 라운드의 backlog는 git history에 남아 있으며, 현재 문서는 새 라운드 기준으로 다시 채운다.

## Intake Rule

- backlog entry는 반드시 `CURRENT_STATE_REVIEW.md`의 finding 하나를 참조한다.
- finding의 `Follow-up target`이 `direct fix`, `docs/ROADMAP.md`, `deferred`, `remove`,
  `needs decision` 중 하나일 때만 backlog에 올린다.
- `Follow-up target`이 `none`이거나 `Post-review bucket`이 `keep`인 finding은 backlog에 올리지 않는다.
- backlog는 리뷰 서술이 아니라 후속 실행 단위 정리 문서다.
- blocked 또는 skipped validation은 후속 작업 판단에 필요하면 `Validation note`에 남긴다.
- runtime smoke, direct provider smoke, human decision이 필요한 항목은 deterministic validation과
  섞어 쓰지 않고 필요한 신호를 명시한다.

## Field Contract

- `Finding`: 원문 finding id와 제목
- `Severity`: review 본문과 동일한 severity
- `Area`: `review-engine`, `review-bot`, `review-platform`, `ops`, `docs`, `cross-cutting` 중 하나
- `Evidence`: backlog를 만든 직접 근거
- `Recommended action`: 다음에 실제로 해야 할 일
- `Follow-up target`: `direct fix`, `docs/ROADMAP.md`, `deferred`, `remove`, `needs decision`
- `Post-review bucket`: `bug_fix`, `roadmap_update`, `deferred_update`, `remove`, `keep`, `needs_decision` 중 하나
- `Validation note`: 후속 작업이 필요로 할 검증 또는 현재 생략 사유

## Backlog Entry Template

```md
### B-<area>-NN <short action title>
- Finding: `F-<area>-NN <short title>`
- Severity: `medium`
- Area: `review-bot`
- Evidence: [path/to/file](/abs/path:1), command `...`, observed mismatch `...`
- Recommended action: <concrete next step>
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: <test or smoke to run later, or why none is needed>
```

## Backlog

### B-review-platform-01 Update local harness bot bridge to key-based bot API

- Finding: `F-architecture-02 Local harness bot bridge still targets removed pr_id bot endpoints`
- Severity: `medium`
- Area: `review-platform`
- Evidence: [review-platform/app/clients/bot_client.py](/home/et16/work/review_system/review-platform/app/clients/bot_client.py:12)
  calls removed `/internal/review/pr-updated`, `/internal/review/next-batch`, and
  `/internal/review/state/{pr_id}` endpoints, while [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:81)
  exposes the current key-based review run API.
- Recommended action: Change `review-platform`'s bot client and UI handlers to use
  `ReviewRequestKey`-based bot APIs, or remove/hide unsupported harness bot controls until a
  key-based next-batch contract exists. Add an unmocked contract test so this bridge cannot drift
  again.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Run `cd review-platform && uv run pytest tests/test_pr_flow.py -q` plus a
  targeted review-bot API test after the fix. Local GitLab smoke is not required unless GitLab
  adapter behavior changes.

### B-review-engine-01 Fail fast on unresolved or duplicate selected packs

- Finding: `F-engine-02 Profile pack selection can silently drop or replace packs`
- Severity: `medium`
- Area: `review-engine`
- Evidence: [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:73)
  overwrites duplicate `pack_id` entries in `pack_index`, and
  [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:124)
  skips profile-selected pack ids that are absent from the loaded pack index.
- Recommended action: Fail fast on missing `enabled_packs`/`shared_packs` references and duplicate
  selected-language pack ids unless an explicit extension replacement contract is added. Cover both
  cases with deterministic loader tests.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Run `cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`.
  Local GitLab smoke and provider validation are not required.

### B-review-engine-02 Clarify or remove default profile configuration

- Finding: `F-engine-03 REVIEW_ENGINE_DEFAULT_PROFILE does not select the review runtime profile`
- Severity: `medium`
- Area: `review-engine`
- Evidence: [review-engine/review_engine/config.py](/home/et16/work/review_system/review-engine/review_engine/config.py:113)
  reads `REVIEW_ENGINE_DEFAULT_PROFILE`, but
  [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:51)
  and [review-engine/review_engine/retrieve/search.py](/home/et16/work/review_system/review-engine/review_engine/retrieve/search.py:60)
  select profiles through the language registry or explicit request input before runtime loading.
- Recommended action: Either wire the setting into safe default profile selection for API/CLI review
  requests, or remove/rename it so operators cannot mistake it for runtime profile selection.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Add a targeted default-profile selection test and run
  `cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_multilang_regressions.py -q`.
  Local GitLab smoke and provider validation are not required.

### B-review-engine-03 Add reverse coverage for canonical rules

- Finding: `F-engine-04 Source coverage is atom-complete but not reverse-complete for canonical rules`
- Severity: `medium`
- Area: `review-engine`
- Evidence: [review-engine/tests/test_source_coverage_matrix.py](/home/et16/work/review_system/review-engine/tests/test_source_coverage_matrix.py:60)
  validates source atom completeness and canonical rule existence, but not that every canonical rule
  has a source atom or an explicit exception. A structured static check found 37 committed canonical
  rule numbers not referenced by any coverage atom.
- Recommended action: Add reverse coverage validation, or maintain an explicit allow-list of
  intentionally untraced rules with reasons and reviewability expectations.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Run `cd review-engine && uv run pytest tests/test_source_coverage_matrix.py -q`
  and any affected retrieval example tests. Local GitLab smoke and provider validation are not required.
