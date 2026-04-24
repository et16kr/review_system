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

### B-review-bot-01 Fail or defer when GitLab note-trigger expected head never settles

- Finding: `F-review-bot-02 GitLab note-trigger can proceed on stale diff after expected head never settles`
- Severity: `medium`
- Area: `review-bot`
- Evidence: [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:393)
  refreshes note-triggered `head_sha` from the source branch, but
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:548)
  returns the last observed diff after settle retries are exhausted, and
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:404)
  persists the observed stale head.
- Recommended action: Change the never-settled path into a retryable detect failure or explicit
  pending/deferred state, and add a deterministic runner test where all settle retries observe the
  stale MR diff head.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Run `cd review-bot && uv run pytest tests/test_review_runner.py tests/test_api_queue.py -q`.
  Because this changes GitLab head handling, also run
  `bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh` when local GitLab is ready.

### B-review-bot-02 Scope adapter thread and feedback identity explicitly

- Finding: `F-review-bot-03 Adapter thread and feedback identities are global in storage but not in contract`
- Severity: `medium`
- Area: `review-bot`
- Evidence: [review-bot/review_bot/contracts.py](/home/et16/work/review_system/review-bot/review_bot/contracts.py:63)
  and [review-bot/review_bot/contracts.py](/home/et16/work/review_system/review-bot/review_bot/contracts.py:104)
  define adapter thread and feedback keys without a global uniqueness contract, while
  [review-bot/review_bot/db/models.py](/home/et16/work/review_system/review-bot/review_bot/db/models.py:183)
  and [review-bot/review_bot/db/models.py](/home/et16/work/review_system/review-bot/review_bot/db/models.py:199)
  store those values as globally unique.
- Recommended action: Decide and enforce the identity scope: require globally unique adapter refs in
  the adapter contract, or change storage/deduplication to composite uniqueness by
  `review_request_pk` plus raw adapter ref. Add deterministic tests with two review requests that
  reuse the same remote thread/comment/event ids.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: A storage-scope fix likely needs a migration plus targeted runner tests. Local
  GitLab smoke is only required if GitLab adapter ref handling changes.

### B-review-bot-03 Add model and endpoint provenance to lifecycle provider runtime

- Finding: `F-provider-02 Lifecycle provider provenance omits model and endpoint transport`
- Severity: `medium`
- Area: `review-bot`
- Evidence: [review-bot/review_bot/providers/base.py](/home/et16/work/review_system/review-bot/review_bot/providers/base.py:29)
  defines lifecycle `ProviderRuntimeMetadata` without model or endpoint fields, while
  [review-bot/review_bot/providers/openai_provider.py](/home/et16/work/review_system/review-bot/review_bot/providers/openai_provider.py:330)
  reads `BOT_OPENAI_MODEL` and `BOT_OPENAI_BASE_URL`, and
  [review-bot/review_bot/cli/evaluate_provider_quality.py](/home/et16/work/review_system/review-bot/review_bot/cli/evaluate_provider_quality.py:20)
  already records richer artifact provenance.
- Recommended action: Extend lifecycle provider runtime metadata, persistence, state API, summary
  note, and structured logs with sanitized `configured_model`, `endpoint_base_url`, and
  `transport_class` for OpenAI-compatible providers. Cover default OpenAI, non-default local backend,
  stub, and fallback cases with targeted tests.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Run `cd review-bot && uv run pytest tests/test_provider_quality.py tests/test_prompting.py::test_openai_provider_client_uses_configured_base_url tests/test_review_runner.py::test_review_runner_persists_provider_runtime_metadata_on_run_and_finding tests/test_review_runner.py::test_review_runner_persists_fallback_provider_runtime_metadata tests/test_review_runner.py::test_pr_summary_includes_live_provider_runtime_provenance tests/test_review_runner.py::test_publish_logs_and_summary_include_fallback_provider_runtime_provenance -q`.
  Run direct OpenAI smoke only when making a live provider success claim.

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

### B-review-engine-04 Reject unknown canonical YAML authoring keys

- Finding: `F-engine-06 Canonical YAML authoring models silently ignore unknown keys`
- Severity: `medium`
- Area: `review-engine`
- Evidence: [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:80)
  defines canonical authoring models as plain Pydantic `BaseModel` subclasses, while
  [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:77)
  validates YAML through `model_validate(...)`. A deterministic check showed typoed keys such as
  `fix_guidence` and `enabled_packz` are ignored without a validation error.
- Recommended action: Configure canonical rule/profile/policy/source manifest models to reject
  unknown fields, or add an explicit unknown-key validation layer with clear messages. Add tests for
  typoed `RuleEntry`, `RulePackManifest`, `ProfileConfig`, `PriorityPolicy`, root manifest, and source
  manifest keys.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Run `cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`
  after the fix. Local GitLab smoke and provider validation are not required.
