# Current State Review

## Purpose

이 문서는 `docs/REVIEW_ROADMAP.md`를 따라 `gpt-5.5`로 새로 수행하는 현재 상태 리뷰 본문이다.
이전 리뷰 라운드 결과는 git history에 남아 있으며, 이번 문서는 새 라운드 기준으로 다시 누적한다.

## Review Round

- model target: `gpt-5.5`
- started: `2026-04-24`
- source roadmap: [docs/REVIEW_ROADMAP.md](/home/et16/work/review_system/docs/REVIEW_ROADMAP.md:1)

## Executive Summary

이번 `gpt-5.5` 리뷰 라운드는 이전 라운드 결과를 이어받아 누적하지 않고,
현재 저장소 상태를 새 기준으로 다시 점검한다.

첫 unit에서는 기술 영역별 판단을 시작하지 않고, 이후 unit이 같은 기준으로
finding과 backlog를 남기도록 scope, evidence level, finding format, validation
rule을 고정했다.

Product direction review 기준으로는 현재 방향이 유지 가능하다. 제품의 중심은
새 리뷰 UI가 아니라 기존 Git review surface 안에서 rule-backed finding, backlog,
feedback loop, lifecycle analytics를 제공하는 것이다. 지금 roadmap의 active 항목은
그 방향에서 벗어나지 않고, 아직 넓거나 외부 신호가 필요한 surface는 contract-first
또는 deferred 상태로 남아 있다.

Architecture review 기준으로는 핵심 `ReviewRequestKey` identity와 runner/adapter/DB
저장 경계가 대체로 일치한다. 다만 local harness의 bot bridge는 이미 제거된 legacy
`pr_id` bot endpoint를 계속 호출하고 있어, `review-platform` UI에서 bot trigger/state
동작이 current `review-bot` API와 어긋난다.

Engine correctness review 기준으로는 canonical YAML rule root, generated dataset,
runtime retrieval selection이 현재 번들 상태에서는 서로 맞는다. 다만 profile/pack
selection 경계에 두 가지 silent drift 위험이 있다. loader가 중복 `pack_id`를
덮어쓰고 누락된 selected pack을 조용히 건너뛰며, `REVIEW_ENGINE_DEFAULT_PROFILE`은
설정으로 존재하지만 실제 review runtime selection에는 반영되지 않는다. Source coverage
matrix도 source atom complete만 검증하고 canonical rule reverse coverage는 검증하지 않아,
출처 atom이 없는 rule이 누적될 수 있다.

Engine authoring UX review 기준으로는 minimal rule lifecycle CLI를 현재처럼 좁게
유지하는 판단이 맞다. CLI는 canonical YAML을 직접 읽고 single pack/profile write
boundary만 수정하며, mutation output에 후속 검증 plan을 함께 낸다. Manual editor도
아직 deferred 상태가 맞다. 다만 canonical YAML authoring model이 알 수 없는 key를
거부하지 않아 `fix_guidence`, `enabled_packz` 같은 typo가 fail-fast 없이 사라지는
검증 공백이 있다.

Review-bot lifecycle review 기준으로는 detect -> publish -> sync responsibility가
runner에 모여 있고 queue handoff, dead-letter, immutable lifecycle event 기록도 현재
방향과 맞는다. 다만 GitLab note-trigger의 expected head가 settle retry 이후에도 맞지
않을 때 stale diff로 계속 진행할 수 있고, adapter thread/feedback reference가 contract
상 request-scoped인지 global인지 명확하지 않은데 DB는 global unique로 저장한다.

Provider/fallback review 기준으로는 lifecycle smoke와 direct provider signal을
분리하는 현재 방향이 맞다. Deterministic `stub` provider quality gate는 통과했고,
OpenAI quality/comparison path는 API key가 없을 때 skipped artifact와 runtime
provenance를 남긴다. 다만 lifecycle run의 `provider_runtime`은 configured/effective
provider와 fallback 여부만 저장하므로, `BOT_OPENAI_BASE_URL`로 OpenAI-compatible local
backend를 붙였을 때 API, log, summary note에서 default OpenAI와 local backend/model을
구분할 수 없다.

## Evidence Inventory

### Evidence Levels

- `static_doc`: repository 문서, roadmap, runbook, deferred 문서를 읽고 확인한 근거
- `static_code`: 코드, 테스트, fixture, migration, script를 읽고 확인한 근거
- `deterministic_validation`: 네트워크와 장기 실행 서비스 없이 반복 가능한 명령 결과
- `runtime_smoke`: local GitLab, compose stack, provider runtime처럼 실행 환경 상태가 필요한 검증
- `direct_provider`: fallback 없는 live provider 호출 또는 provider-direct smoke 결과
- `human_review`: 제품 방향, 운영 정책, 위험 감수 여부처럼 사람의 결정이 필요한 판단

### Validation Policy

- 문서-only review unit은 `git diff --check`를 기본 검증으로 삼는다.
- 코드 경계나 deterministic behavior를 근거로 삼는 unit은 관련 targeted test를 함께 남긴다.
- local GitLab smoke는 lifecycle, webhook, thread sync, stale head, adapter behavior를
  실제 근거로 삼을 때만 실행한다.
- provider-direct smoke와 lifecycle smoke는 서로 다른 신호다. fallback이 켜진 lifecycle
  smoke pass는 live OpenAI 성공의 근거로 쓰지 않는다.
- OpenAI direct path나 quota 상태를 finding 근거로 쓰려면 `direct_provider` evidence를
  별도로 남긴다.

### Unit 1 Evidence

- Roadmap frame: [docs/REVIEW_ROADMAP.md](/home/et16/work/review_system/docs/REVIEW_ROADMAP.md:1)
- Current review artifact: [docs/reviews/CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)
- Backlog artifact: [docs/reviews/REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)
- Validation: `git diff --check`
- Skipped validation: local GitLab smoke and OpenAI direct smoke were not needed for this
  document-only frame reset.

### Unit 2 Evidence

- Product entry point and workspace boundary: [README.md](/home/et16/work/review_system/README.md:3)
- Current system invariants and provider/runtime boundaries:
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:17)
- Adapter/API responsibility split:
  [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:5)
- Implementation roadmap and deferred split:
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:24)
- Deferred provider/model work:
  [docs/deferred/provider_and_model_work.md](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:10)
- Deferred authoring/editor work:
  [docs/deferred/rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:10)
- Deferred platform expansion:
  [docs/deferred/platform_expansion.md](/home/et16/work/review_system/docs/deferred/platform_expansion.md:9)
- Deferred auto-fix automation:
  [docs/deferred/automation_work.md](/home/et16/work/review_system/docs/deferred/automation_work.md:9)
- Static scan: `rg -n "review-platform|ask|review-bot.yaml|GitHub|Gerrit|auto|OpenAI|fallback|stub|local harness|local backend|provider|roadmap|deferred|manual rule editor" README.md docs/CURRENT_SYSTEM.md docs/API_CONTRACTS.md docs/ROADMAP.md docs/deferred`
- Validation: `git diff --check`
- Skipped validation: local GitLab smoke and OpenAI direct smoke were not needed for this
  document-only product direction review.

### Unit 3 Evidence

- Canonical identity contract: [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:820)
- API key construction from GitLab note hooks:
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:262)
- Internal key-based review request endpoints:
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:136)
- DB unique request key and repeated key columns:
  [review-bot/review_bot/db/models.py](/home/et16/work/review_system/review-bot/review_bot/db/models.py:16)
- Adapter V2 boundary:
  [review-bot/review_bot/review_systems/base.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/base.py:24)
- GitLab project path encoding from `project_ref`:
  [review-bot/review_bot/review_systems/gitlab.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/gitlab.py:410)
- Local harness BotClient stale endpoint calls:
  [review-platform/app/clients/bot_client.py](/home/et16/work/review_system/review-platform/app/clients/bot_client.py:12)
- Review-platform bot endpoints call that client:
  [review-platform/app/api/main.py](/home/et16/work/review_system/review-platform/app/api/main.py:307)
- Existing tests mock the stale bridge instead of exercising the real bot API:
  [review-platform/tests/test_pr_flow.py](/home/et16/work/review_system/review-platform/tests/test_pr_flow.py:189)
- Static scans:
  `rg -n "ReviewRequestKey|project_ref|review_system|review_request_id" review-bot/review_bot review-platform/app docs/CURRENT_SYSTEM.md docs/API_CONTRACTS.md docs/OPERATIONS_RUNBOOK.md README.md`
  and
  `rg -n "pr-updated|next-batch|state/\\{pr_id\\}|ReviewUpdated|NextBatch|pr_id" review-bot/review_bot/api review-bot/tests review-platform/tests docs/API_CONTRACTS.md docs/OPERATIONS_RUNBOOK.md`
- Validation: `git diff --check`
- Skipped validation: local GitLab smoke and OpenAI direct smoke were not needed for this
  static architecture review. No provider or lifecycle runtime success claim was made.

### Unit 4 Evidence

- Engine README rule root and ingest contract:
  [review-engine/README.md](/home/et16/work/review_system/review-engine/README.md:5)
- Runtime loader pack/profile/policy selection:
  [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:51)
- Ingest generated dataset write path:
  [review-engine/review_engine/ingest/build_records.py](/home/et16/work/review_system/review-engine/review_engine/ingest/build_records.py:26)
- Review search runtime candidate filtering:
  [review-engine/review_engine/retrieve/search.py](/home/et16/work/review_system/review-engine/review_engine/retrieve/search.py:156)
- Runtime metadata and source-family alias model:
  [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:34)
- Language/profile inference:
  [review-engine/review_engine/languages/registry.py](/home/et16/work/review_system/review-engine/review_engine/languages/registry.py:300)
- Source coverage matrix validation:
  [review-engine/tests/test_source_coverage_matrix.py](/home/et16/work/review_system/review-engine/tests/test_source_coverage_matrix.py:60)
- Expected retrieval and smoke fixture retrieval contracts:
  [review-engine/tests/test_expected_examples.py](/home/et16/work/review_system/review-engine/tests/test_expected_examples.py:13)
  and [review-engine/tests/test_smoke_fixture_contracts.py](/home/et16/work/review_system/review-engine/tests/test_smoke_fixture_contracts.py:95)
- Static scans:
  `rg -n "pack_index\\[|continue$|selected_pack_ids|overridden_by|explicit_override|source_family|pack_id|rule_uid|get_rules\\(|existing_by_rule|where=\\{\\\"rule_no\\\"" review-engine/review_engine/ingest/rule_loader.py review-engine/review_engine/retrieve/search.py review-engine/review_engine/ingest/chroma_store.py review-engine/review_engine/models.py`,
  `rg -n "default_profile_id|REVIEW_ENGINE_DEFAULT_PROFILE|default_profile" review-engine/review_engine review-engine/tests docs review-engine/README.md`,
  and `rg -n "missing pack|missing.*pack|duplicate pack|selected_pack|pack_id.*ambiguous|provide --pack-id|fails_fast|fail-fast" review-engine/tests review-engine/review_engine/ingest review-engine/review_engine/cli/rule_lifecycle.py`
- Structured static checks:
  bundled profile pack references have no missing pack refs; committed generated dataset IDs match
  canonical runtime IDs for all discovered languages; source coverage matrix references 313 unique
  rules while 37 committed canonical rules are not referenced by any source atom.
- Deterministic validation: `git diff --check`
- Skipped validation: local GitLab smoke and OpenAI direct smoke were not needed for this
  static `review-engine` correctness review. No provider or lifecycle runtime success claim was made.

### Unit 5 Evidence

- Rule lifecycle CLI command surface:
  [review-engine/review_engine/cli/rule_lifecycle.py](/home/et16/work/review_system/review-engine/review_engine/cli/rule_lifecycle.py:45)
- Rule lifecycle mutation validation plan:
  [review-engine/review_engine/cli/rule_lifecycle.py](/home/et16/work/review_system/review-engine/review_engine/cli/rule_lifecycle.py:360)
- Rule lifecycle tests for read-only inspection, single rule mutation, pack mutation, ambiguity, and merged-profile fail-fast:
  [review-engine/tests/test_rule_lifecycle_cli.py](/home/et16/work/review_system/review-engine/tests/test_rule_lifecycle_cli.py:32)
- Current system lifecycle CLI boundary:
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:108)
- Operations runbook lifecycle CLI examples and validation guidance:
  [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:261)
- Deferred manual editor rationale:
  [docs/deferred/rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:10)
- Manual editor readiness packet:
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:162)
- Canonical authoring model definitions:
  [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:80)
  and [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:124)
- Runtime YAML validation call sites:
  [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:77)
- Deterministic checks:
  `UV_CACHE_DIR=/tmp/uv-cache uv run --project review-engine python -m review_engine.cli.rule_lifecycle --help`
  confirmed the minimal subcommand surface, and a structured `model_validate` check showed unknown
  `RuleEntry`, `RulePackManifest`, and `ProfileConfig` keys are ignored instead of rejected.
- Validation: `git diff --check` and
  `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`
- Skipped validation: local GitLab smoke and OpenAI direct smoke were not needed for this
  static `review-engine` authoring UX review. No provider or lifecycle runtime success claim was made.

### Unit 6 Evidence

- Keyed review-run creation and detect queue handoff:
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:344)
  and [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:366)
- Worker detect -> publish -> sync chain:
  [review-bot/review_bot/worker.py](/home/et16/work/review_system/review-bot/review_bot/worker.py:23)
- Detect, publish, and sync phases:
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:353),
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:589),
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:926)
- GitLab note-trigger head refresh and detect-time settle retry:
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:393)
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:548)
- Thread reconciliation and immutable lifecycle event recording:
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1902)
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1775)
- Feedback event ingestion and adapter event keys:
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1664),
  [review-bot/review_bot/db/models.py](/home/et16/work/review_system/review-bot/review_bot/db/models.py:199),
  and [review-bot/review_bot/review_systems/gitlab.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/gitlab.py:309)
- Existing deterministic coverage:
  [review-bot/tests/test_api_queue.py](/home/et16/work/review_system/review-bot/tests/test_api_queue.py:444)
  and [review-bot/tests/test_review_runner.py](/home/et16/work/review_system/review-bot/tests/test_review_runner.py:1005)
  cover payload head refresh and eventual detect-time head settle; runner tests at
  [review-bot/tests/test_review_runner.py](/home/et16/work/review_system/review-bot/tests/test_review_runner.py:1088)
  cover fixed/manual resolution classification and lifecycle event recording.
- Static scans:
  `rg -n "def (create_review_run_for_key|execute_detect_phase|execute_publish_phase|execute_sync_phase|_refresh_detect_inputs_for_expected_head|_reconcile_thread_snapshots|_record_finding_lifecycle_event|_ingest_feedback)" review-bot/review_bot/bot/review_runner.py`,
  `rg -n "event_key|adapter_thread_ref|UniqueConstraint|collect_feedback" review-bot/review_bot review-bot/tests`,
  and `rg -n "expected_head|stale-head|fixed_in_followup|remote_resolved_manual_only|reopened|resolve_failed" review-bot/tests`.
- Validation passed: `timeout 180s .venv/bin/pytest tests/test_review_runner.py::test_review_runner_waits_for_expected_head_on_gitlab_note_trigger tests/test_review_runner.py::test_resolution_classifier_marks_fixed_in_followup_commit_and_records_lifecycle tests/test_review_runner.py::test_resolution_classifier_marks_remote_resolved_manual_only_when_diff_does_not_match tests/test_review_runner.py::test_review_runner_recovers_stale_thread_after_resolve_failure_when_remote_thread_is_still_open tests/test_review_runner.py::test_reopen_records_immutable_lifecycle_event_without_erasing_fixed_history -q`
  passed with `5 passed`.
- Blocked validation: `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_review_runner.py tests/test_api_queue.py -q`
  hung after partial progress, and a single API queue test timed out inside
  `starlette.testclient.TestClient.__enter__` before making the webhook request. This is recorded as
  a validation limitation and follow-up test-gate investigation, not as a blocker for continuing the
  review round.
- Skipped validation: local GitLab smoke was not run because this unit did not require runtime
  webhook/thread evidence. OpenAI direct smoke was skipped by configuration and was not relevant to
  lifecycle correctness. Provider validation used deterministic fake/stub provider paths only.

### Unit 7 Evidence

- OpenAI-compatible client wiring:
  [review-bot/review_bot/providers/openai_provider.py](/home/et16/work/review_system/review-bot/review_bot/providers/openai_provider.py:330)
  stores `BOT_OPENAI_MODEL` and `BOT_OPENAI_BASE_URL`, and passes `base_url`, retry, and timeout
  settings to the OpenAI client.
- Lifecycle runtime metadata model and persistence:
  [review-bot/review_bot/providers/base.py](/home/et16/work/review_system/review-bot/review_bot/providers/base.py:29),
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3240),
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3336)
  store only configured/effective provider plus fallback fields on review runs and finding evidence.
- Lifecycle API/log/note surfaces:
  [review-bot/review_bot/schemas.py](/home/et16/work/review_system/review-bot/review_bot/schemas.py:47),
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3296),
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3628),
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3865)
  expose the same narrow lifecycle provenance.
- Provider quality artifact provenance:
  [review-bot/review_bot/cli/evaluate_provider_quality.py](/home/et16/work/review_system/review-bot/review_bot/cli/evaluate_provider_quality.py:20)
  includes configured model, endpoint base URL, and transport class for OpenAI quality artifacts,
  while [docs/baselines/review_bot/provider_quality_openai_2026-04-23.md](/home/et16/work/review_system/docs/baselines/review_bot/provider_quality_openai_2026-04-23.md:1)
  is an older skipped artifact without those runtime fields.
- Direct-provider smoke boundary:
  [ops/scripts/smoke_openai_provider_direct.sh](/home/et16/work/review_system/ops/scripts/smoke_openai_provider_direct.sh:22)
  directly probes the configured OpenAI-compatible endpoint without review-bot fallback, and
  [review-bot/tests/test_openai_provider_direct_smoke.py](/home/et16/work/review_system/review-bot/tests/test_openai_provider_direct_smoke.py:68)
  covers script root/env override behavior with a fake `curl`.
- Documentation boundary:
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:83)
  and [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:89)
  explicitly separate lifecycle fallback success from direct OpenAI or local-backend success.
- Static scans:
  `rg -n "provider_runtime|configured_provider|effective_provider|fallback_used|fallback_reason|build_draft_with_runtime|provider_|fallback" review-bot/review_bot review-bot/tests docs/API_CONTRACTS.md docs/CURRENT_SYSTEM.md docs/OPERATIONS_RUNBOOK.md ops/scripts/smoke_openai_provider_direct.sh ops/scripts/smoke_local_gitlab_lifecycle_review.sh ops/scripts/smoke_local_gitlab_multilang_review.py`.
- Validation passed:
  `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_provider_quality.py tests/test_openai_provider_direct_smoke.py tests/test_prompting.py::test_openai_provider_client_uses_configured_base_url tests/test_review_runner.py::test_review_runner_persists_provider_runtime_metadata_on_run_and_finding tests/test_review_runner.py::test_review_runner_persists_fallback_provider_runtime_metadata tests/test_review_runner.py::test_pr_summary_includes_live_provider_runtime_provenance tests/test_review_runner.py::test_publish_logs_and_summary_include_fallback_provider_runtime_provenance -q`
  passed with `15 passed`.
- Validation passed:
  `UV_CACHE_DIR=/tmp/uv-cache uv run --project review-bot python -m review_bot.cli.evaluate_provider_quality --provider stub --json-output /tmp/provider_quality_stub_review_unit7.json`
  returned `status=passed`, `passed_cases=6`, `failed_cases=0`.
- Validation passed:
  `OPENAI_API_KEY= BOT_OPENAI_MODEL=local-model BOT_OPENAI_BASE_URL=http://127.0.0.1:11434/v1 UV_CACHE_DIR=/tmp/uv-cache uv run --project review-bot python -m review_bot.cli.evaluate_provider_quality --provider openai --json-output /tmp/provider_quality_openai_skipped_review_unit7.json`
  returned `status=skipped` with `provider_runtime` showing
  `transport_class=non_default_openai_compatible_base_url`.
- Validation passed:
  `UV_CACHE_DIR=/tmp/uv-cache uv run --project review-bot python -m review_bot.cli.compare_provider_quality --stub-json /tmp/provider_quality_stub_review_unit7.json --openai-json /tmp/provider_quality_openai_skipped_review_unit7.json --json-output /tmp/provider_comparison_review_unit7.json`
  returned `openai_status=skipped`, `human_review_required=False`, and
  `recommended_next_action=defer_openai_comparison_until_api_key_available`.
- Failed validation attempt:
  `timeout 180s .venv/bin/pytest ... -q` from the repository root failed during collection because
  the root virtualenv lacked `openai` and `sqlalchemy`; the same targeted tests passed through
  `uv run` in `review-bot`.
- Skipped validation: OpenAI direct smoke was skipped by configuration, so this unit made no live
  OpenAI success claim. Local GitLab lifecycle smoke was not run because provider boundary judgment
  did not require runtime GitLab evidence. Provider validation used deterministic `stub` and skipped
  OpenAI artifact paths, not direct OpenAI.

## Findings

### F-product-01 Existing Git review surface remains the right product center

- Severity: `info`
- Area: `cross-cutting`
- Evidence level: `static_doc`
- Evidence: [README.md](/home/et16/work/review_system/README.md:3) defines the goal as adding
  rule-backed review to existing Git PR/MR systems instead of creating a new review UI.
  [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:7) keeps the
  external Git review system as the canonical UI and `review-platform` as harness-only.
- Impact: This keeps user value concentrated on high-signal inline comments, backlog/status notes,
  feedback capture, and analytics where reviewers already work.
- Recommended action: Keep new product work anchored to Git review comments, notes, checks, and
  adapter capabilities. Avoid promoting `review-platform` or separate dashboards into the primary
  user surface without a new product decision.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static document review only. No runtime smoke needed.

### F-product-02 Current roadmap sequencing matches user value and blocker risk

- Severity: `info`
- Area: `docs`
- Evidence level: `static_doc`
- Evidence: [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:34) prioritizes
  fresh evidence for targeted rule expansion, `.review-bot.yaml` and `ask` contract boundaries,
  local backend retained artifact prep, and deferred readiness packets before broader execution.
- Impact: The active work is not feature accumulation for its own sake. It clears ambiguity around
  rule gaps, note-first configuration, provider provenance, and deferred prerequisites before
  implementation expands user-facing behavior.
- Recommended action: Keep the current ordering. Treat `.review-bot.yaml` and `ask` as contract
  definition work until their precedence, session, provider, and "what not to answer" boundaries
  are explicit.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static document review only. No targeted tests needed because no code contract
  changed.

### F-product-03 Broad expansion surfaces are correctly deferred

- Severity: `info`
- Area: `cross-cutting`
- Evidence level: `static_doc`
- Evidence: Provider tuning is blocked on quota, direct provider success, and human review in
  [docs/deferred/provider_and_model_work.md](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:12).
  Manual editor work is deferred behind rule state and validation boundaries in
  [docs/deferred/rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:12).
  Multi-SCM expansion is deferred behind GitLab stability and GitHub test permissions in
  [docs/deferred/platform_expansion.md](/home/et16/work/review_system/docs/deferred/platform_expansion.md:11).
  Auto-fix is deferred behind trust metrics, low-risk class definition, approval, audit, and
  rollback policy in [docs/deferred/automation_work.md](/home/et16/work/review_system/docs/deferred/automation_work.md:11).
- Impact: The roadmap avoids committing to large, trust-sensitive, or externally blocked features
  before the review bot has enough evidence and operational control to support them.
- Recommended action: Keep these surfaces deferred. Reconsider them only through the readiness
  packets already queued in `docs/ROADMAP.md`.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static document review only. Direct OpenAI and local GitLab smoke were not
  required because no provider or lifecycle success claim was made.

### F-architecture-01 Canonical request identity is coherent across API, runner, adapters, and DB

- Severity: `info`
- Area: `review-bot`
- Evidence level: `static_code`
- Evidence: [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:820)
  defines `review_system + project_ref + review_request_id` as the business key.
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:262)
  builds GitLab keys from `project.path_with_namespace` plus MR iid. [review-bot/review_bot/db/models.py](/home/et16/work/review_system/review-bot/review_bot/db/models.py:16)
  enforces the same tuple as `uq_review_request_key`, and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3400)
  looks requests up by all three fields.
- Impact: Same-iid MRs from different GitLab projects remain isolated, and downstream run,
  finding, publication, thread, feedback, lifecycle, and dead-letter rows carry enough key
  context for analytics and recovery.
- Recommended action: Keep this boundary. New internal APIs and harness calls should accept
  `ReviewRequestKey` or enough structured input to construct it explicitly.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static code review only. No targeted test needed because no behavior changed.

### F-architecture-02 Local harness bot bridge still targets removed `pr_id` bot endpoints

- Severity: `medium`
- Area: `review-platform`
- Evidence level: `static_code`
- Evidence: [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:828)
  says legacy `pr_id` endpoints were removed and harness/tests should use runner helpers or
  `ReviewRequestKey` APIs. Current `review-bot` exposes key-based `/internal/review/runs` and
  `/internal/review/requests/{review_system}/{project_ref}/{review_request_id}` endpoints at
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:81)
  and [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:136).
  But [review-platform/app/clients/bot_client.py](/home/et16/work/review_system/review-platform/app/clients/bot_client.py:12)
  still calls `/internal/review/pr-updated`, `/internal/review/next-batch`, and
  `/internal/review/state/{pr_id}`. The harness test at
  [review-platform/tests/test_pr_flow.py](/home/et16/work/review_system/review-platform/tests/test_pr_flow.py:189)
  patches `app.api.main.bot_client`, so it does not catch the real bridge mismatch.
- Impact: The local harness is correctly non-production, but its review/next-batch/state UI can
  404 against the current bot. That weakens the harness as integration evidence and preserves a
  stale product-shaped compatibility path around a removed contract.
- Recommended action: Replace the `review-platform` BotClient bridge with the current
  `ReviewRequestKey` API, or remove/hide harness bot controls that cannot be supported without a
  key-based next-batch contract. Add an unmocked deterministic test for the bridge contract.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Static code review found the mismatch. A follow-up fix should run
  `cd review-platform && uv run pytest tests/test_pr_flow.py -q` and a targeted bot API test; local
  GitLab smoke is not required unless the fix touches GitLab adapter behavior.

### F-architecture-03 Lifecycle analytics boundary is intentionally event-backed

- Severity: `info`
- Area: `review-bot`
- Evidence level: `static_code`
- Evidence: [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:56)
  states that `finding_lifecycle_events` is the analytics source of truth after Phase A.
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1775)
  records immutable lifecycle events when thread sync resolves or reopens findings, while
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:2201)
  reads `FindingLifecycleEvent` rows for finding outcome analytics.
- Impact: Current-state `ThreadSyncState` can remain mutable without becoming the historical
  analytics authority, reducing regression risk when remote threads are reopened or classified.
- Recommended action: Keep lifecycle analytics event-backed. Treat future mutable-state analytics
  shortcuts as architecture risks unless they are explicitly documented as snapshots.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static code review only. Unit 6 should perform the deeper lifecycle correctness
  review and decide whether targeted runner tests are needed.

### F-engine-01 Canonical engine runtime and generated datasets agree in the current bundle

- Severity: `info`
- Area: `review-engine`
- Evidence level: `static_code`
- Evidence: [review-engine/review_engine/ingest/build_records.py](/home/et16/work/review_system/review-engine/review_engine/ingest/build_records.py:26)
  loads every discovered language with `include_all_packs=True` and writes active/reference/excluded
  generated datasets from the same runtime records. [review-engine/review_engine/retrieve/search.py](/home/et16/work/review_system/review-engine/review_engine/retrieve/search.py:156)
  then queries active collections and re-filters candidates against the selected runtime. A structured
  static check found no ID mismatch between committed generated JSON datasets and canonical runtime
  records for discovered languages.
- Impact: Current committed generated artifacts do not appear stale relative to canonical YAML rule
  selection, so retrieval evidence can be interpreted against the checked-in rule bundle.
- Recommended action: Keep generated datasets derived from canonical YAML and continue requiring
  ingest/evaluation after rule changes. Do not treat generated JSON as an independent source of truth.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static code and structured read-only checks only. No runtime smoke needed.

### F-engine-02 Profile pack selection can silently drop or replace packs

- Severity: `medium`
- Area: `review-engine`
- Evidence level: `static_code`
- Evidence: [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:73)
  builds `pack_index` by assigning `pack_index[pack.pack_id] = (pack, path)`, so a later root with
  the same selected-language `pack_id` replaces the earlier pack without an explicit override record.
  [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:113)
  copies profile-selected pack ids, but [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:124)
  silently `continue`s when a selected pack id is absent from `pack_index`. Existing rule lifecycle
  tests cover ambiguous rule numbers inside selected packs, but the static scan found no test for
  duplicate pack identity or missing profile pack refs.
- Impact: A typo in `enabled_packs`/`shared_packs`, or an extension root accidentally reusing a public
  pack id, can shrink or replace the review rule surface without failing ingest, review, or lifecycle
  inspection. That weakens rule expansion safety and makes pack identity drift hard to diagnose.
- Recommended action: Fail fast when a profile-selected pack id cannot be resolved, and fail fast on
  duplicate selected-language pack ids unless there is a documented extension replacement contract.
  Add deterministic loader tests for both cases.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Follow-up fix should run `cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`.
  Local GitLab smoke and provider validation are not required.

### F-engine-03 `REVIEW_ENGINE_DEFAULT_PROFILE` does not select the review runtime profile

- Severity: `medium`
- Area: `review-engine`
- Evidence level: `static_code`
- Evidence: [review-engine/review_engine/config.py](/home/et16/work/review_system/review-engine/review_engine/config.py:43)
  defines `default_profile_id`, and [review-engine/review_engine/config.py](/home/et16/work/review_system/review-engine/review_engine/config.py:113)
  reads `REVIEW_ENGINE_DEFAULT_PROFILE`. But [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:51)
  falls back to `registry.get(selected_language).default_profile`, while
  [review-engine/review_engine/retrieve/search.py](/home/et16/work/review_system/review-engine/review_engine/retrieve/search.py:60)
  resolves language/profile before loading runtime. A read-only check with
  `default_language_id='python'` and `default_profile_id='fastapi_service'` returned
  `python default` for `GuidelineSearchService.review_code(...)`.
- Impact: Operators can set a profile default that does not affect API/CLI review behavior, while
  direct `build_query_analysis` calls still use the setting. That can produce profile/prompt/rule
  selection confusion and missed framework-specific rules when no explicit `profile_id` is supplied.
- Recommended action: Either wire `settings.default_profile_id` into language resolution and runtime
  selection where it is safe, or remove/rename the setting so profile selection remains explicitly
  path/content inferred or request-supplied.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Follow-up fix should add a targeted default-profile selection test and run
  `cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_multilang_regressions.py -q`.
  Local GitLab smoke and provider validation are not required.

### F-engine-04 Source coverage is atom-complete but not reverse-complete for canonical rules

- Severity: `medium`
- Area: `review-engine`
- Evidence level: `static_code`
- Evidence: [review-engine/rule_sources/coverage_matrix.yaml](/home/et16/work/review_system/review-engine/rule_sources/coverage_matrix.yaml:4)
  declares source-atom coverage and [review-engine/rule_sources/coverage_matrix.yaml](/home/et16/work/review_system/review-engine/rule_sources/coverage_matrix.yaml:8)
  says all committed source atoms are classified. [review-engine/tests/test_source_coverage_matrix.py](/home/et16/work/review_system/review-engine/tests/test_source_coverage_matrix.py:60)
  verifies that every manifest source has atom counts and that atom `canonical_rules` exist, but it
  does not assert that every canonical rule is mapped back to at least one source atom. A structured
  static check found 350 committed rule numbers, 313 referenced by coverage atoms, and 37 unreferenced
  rules including `R.1`, `R.13`, `SQL.5`, `TS.2`, and `PY.PROJ.6`.
- Impact: Rule expansion can pass the current coverage test while leaving rules without source
  provenance in the matrix. That makes it harder to audit why a rule exists, whether it was meant to
  be active or reference-only, and whether source/rule/example validation moved together.
- Recommended action: Add reverse coverage validation, or maintain an explicit allow-list of
  intentionally untraced rules with reasons and reviewability expectations.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Follow-up fix should run `cd review-engine && uv run pytest tests/test_source_coverage_matrix.py -q`
  and any affected retrieval example tests. Local GitLab smoke and provider validation are not required.

### F-engine-05 Minimal rule lifecycle CLI is correctly bounded for current operations

- Severity: `info`
- Area: `review-engine`
- Evidence level: `static_code`
- Evidence: [review-engine/review_engine/cli/rule_lifecycle.py](/home/et16/work/review_system/review-engine/review_engine/cli/rule_lifecycle.py:51)
  exposes only `list`, `show`, `disable`, `enable`, `disable-pack`, and `enable-pack`.
  Mutating commands return `write_boundary` and a validation plan at
  [review-engine/review_engine/cli/rule_lifecycle.py](/home/et16/work/review_system/review-engine/review_engine/cli/rule_lifecycle.py:252)
  and [review-engine/review_engine/cli/rule_lifecycle.py](/home/et16/work/review_system/review-engine/review_engine/cli/rule_lifecycle.py:341).
  The runbook documents the same boundary and validation sequence at
  [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:261).
- Impact: Operators can inspect and toggle canonical YAML runtime state without introducing a
  separate rule state store or broad editor surface. This matches the current product direction:
  high-signal rule maintenance through Git-reviewed YAML, not a parallel authoring UI.
- Recommended action: Keep the lifecycle CLI narrow. Treat new authoring features as separate
  readiness or editor work unless they preserve canonical YAML, Git history, and deterministic
  validation as the source of truth.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static code and docs review plus CLI help check. No local GitLab smoke or
  provider validation needed.

### F-engine-06 Canonical YAML authoring models silently ignore unknown keys

- Severity: `medium`
- Area: `review-engine`
- Evidence level: `deterministic_validation`
- Evidence: [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:80)
  defines `RuleEntry`, [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:124)
  defines `RulePackManifest`, and
  [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:141)
  defines `ProfileConfig` as plain Pydantic `BaseModel` subclasses with no strict unknown-field
  policy. [review-engine/review_engine/ingest/rule_loader.py](/home/et16/work/review_system/review-engine/review_engine/ingest/rule_loader.py:77)
  validates YAML with `model_validate(...)`. A deterministic check showed
  `fix_guidence` leaves `RuleEntry.fix_guidance=None`, an unknown pack key is absent from
  `RulePackManifest.model_dump()`, and `enabled_packz` leaves `ProfileConfig.enabled_packs=[]`
  without a validation error.
- Impact: Common authoring typos in rule metadata, pack metadata, profile selection, or future
  editor-generated YAML can silently remove intended guidance or pack selection. The failure mode is
  especially risky because later ingest and lifecycle commands appear successful while the authored
  field was ignored.
- Recommended action: Make canonical authoring models reject unknown keys, or add an explicit YAML
  unknown-key validation layer with clear error messages. Cover `RuleEntry`, `RulePackManifest`,
  `ProfileConfig`, `PriorityPolicy`, and root/source manifests with deterministic tests.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Follow-up fix should run
  `cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`.
  Local GitLab smoke and provider validation are not required.

### F-engine-07 Manual rule editor should remain deferred behind strict schema and readiness work

- Severity: `info`
- Area: `review-engine`
- Evidence level: `static_doc`
- Evidence: [docs/deferred/rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:14)
  says canonical YAML plus Git history is the current base and an editor needs rule state,
  validation, and extension boundaries first. [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:162)
  keeps a queued readiness packet to split existing lifecycle CLI write boundaries from new editor
  surface and collect common metadata/validation failures before implementation.
- Impact: Deferring the editor avoids creating a second authoring path before strict schema
  validation, preview, ingest, regression, extension, and audit boundaries are ready.
- Recommended action: Keep manual editor work deferred. Before promoting it, close the strict YAML
  authoring validation gap and complete the readiness packet so any editor remains a canonical YAML
  helper rather than an alternate state store.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static document review only. No runtime validation needed.

### F-review-bot-01 Runner-owned lifecycle is the right boundary

- Severity: `info`
- Area: `review-bot`
- Evidence level: `static_code`
- Evidence: [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:344)
  creates keyed review runs and enqueues detect jobs. [review-bot/review_bot/worker.py](/home/et16/work/review_system/review-bot/review_bot/worker.py:23)
  chains detect -> publish -> sync jobs, while [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:353),
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:589),
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:926)
  keep detect, publish, and sync state transitions inside `ReviewRunner`. Thread reconciliation
  records immutable lifecycle events at
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1902)
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1775).
- Impact: Adapter code can stay focused on external review-system I/O, while run state,
  publication state, feedback ingestion, and lifecycle analytics keep one canonical owner.
- Recommended action: Keep runner-level lifecycle ownership. Future adapter work should expose
  capabilities and snapshots, not local lifecycle state machines.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static code review plus runner-only lifecycle tests passed. API queue validation
  is blocked by a TestClient startup hang, so API-queue evidence remains a follow-up limitation. No
  runtime smoke was needed for this keep finding.

### F-review-bot-02 GitLab note-trigger can proceed on stale diff after expected head never settles

- Severity: `medium`
- Area: `review-bot`
- Evidence level: `static_code`
- Evidence: [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:393)
  refreshes a note-triggered run's `head_sha` from the source branch when the webhook payload is
  stale. [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:548)
  retries detect inputs when the fetched MR diff head does not match that expected head, but after
  exhausting retries it only logs `detect_head_not_settled` and returns the refreshed diff. Then
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:404)
  overwrites `review_run.head_sha` from the observed diff/meta head. Existing tests cover payload
  head refresh and eventual settle at
  [review-bot/tests/test_api_queue.py](/home/et16/work/review_system/review-bot/tests/test_api_queue.py:444)
  and [review-bot/tests/test_review_runner.py](/home/et16/work/review_system/review-bot/tests/test_review_runner.py:1005),
  but there is no deterministic test for the never-settled path.
- Impact: A force-push followed immediately by `@review-bot review` can still produce a successful
  review on stale MR diff data if GitLab's changes endpoint remains behind for all retries. The run
  then loses the expected head in persisted state, weakening status checks, reports, and smoke
  assertions that rely on the latest head.
- Recommended action: Treat never-settled expected head as a retryable detect failure or explicit
  pending state instead of silently proceeding. Add a deterministic runner test where all retries
  observe the stale head, and keep the local GitLab lifecycle smoke as the runtime regression gate
  when this behavior is changed.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: This review used static evidence and existing deterministic tests only. The
  runner-only lifecycle tests passed, but API queue validation is currently blocked by a TestClient
  startup hang. The follow-up fix should run `cd review-bot && uv run pytest tests/test_review_runner.py tests/test_api_queue.py -q`;
  because it changes GitLab head handling, run `bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh`
  when the local GitLab environment is ready.

### F-review-bot-03 Adapter thread and feedback identities are global in storage but not in contract

- Severity: `medium`
- Area: `review-bot`
- Evidence level: `static_code`
- Evidence: [review-bot/review_bot/contracts.py](/home/et16/work/review_system/review-bot/review_bot/contracts.py:104)
  defines `FeedbackRecord.event_key`, and
  [review-bot/review_bot/contracts.py](/home/et16/work/review_system/review-bot/review_bot/contracts.py:63)
  defines `ThreadSnapshot.thread_ref`, but neither contract states that these adapter refs must be
  globally unique across review systems, projects, and review requests. Storage assumes global
  uniqueness through `ThreadSyncState.adapter_thread_ref` at
  [review-bot/review_bot/db/models.py](/home/et16/work/review_system/review-bot/review_bot/db/models.py:183)
  and `FeedbackEvent.event_key` at
  [review-bot/review_bot/db/models.py](/home/et16/work/review_system/review-bot/review_bot/db/models.py:199).
  GitLab currently emits raw discussion/note-derived keys at
  [review-bot/review_bot/review_systems/gitlab.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/gitlab.py:171)
  and [review-bot/review_bot/review_systems/gitlab.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/gitlab.py:321)
  without a `ReviewRequestKey` prefix.
- Impact: Current GitLab IDs may be unique enough in practice, but the lifecycle storage layer is
  stricter than the adapter contract. Any adapter or fixture that reuses simple thread/comment IDs
  across projects can collide, drop feedback through `_ingest_feedback`, or prevent a separate
  request from creating its own thread sync row.
- Recommended action: Make identity scope explicit. Either require adapters to emit globally unique
  refs and test that contract, or scope DB uniqueness/deduplication by `review_request_pk` plus
  adapter ref while preserving the raw remote ref needed for API calls. Cover two review requests
  with identical adapter refs in deterministic tests.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: This is a static contract/storage finding. Runner-only lifecycle tests passed,
  while API queue validation is blocked by a TestClient startup hang. A follow-up fix likely needs a
  DB migration plus targeted runner tests; local GitLab smoke is only required if GitLab adapter ref
  handling changes.

### F-provider-01 Provider and fallback signals are correctly separated for review judgment

- Severity: `info`
- Area: `review-bot`
- Evidence level: `deterministic_validation`
- Evidence: [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:88)
  states that lifecycle smoke and direct OpenAI smoke are different signals, and
  [ops/scripts/smoke_openai_provider_direct.sh](/home/et16/work/review_system/ops/scripts/smoke_openai_provider_direct.sh:22)
  probes the OpenAI-compatible Responses endpoint without review-bot fallback. The deterministic
  provider quality CLI run for `stub` passed all 6 packaged cases, while the OpenAI quality run with
  `OPENAI_API_KEY` unset produced a skipped artifact instead of pretending live provider success.
- Impact: Review and release work can keep fail-open lifecycle behavior without mistaking it for
  live OpenAI, quota, or local-backend evidence. This is the right trust boundary for current
  provider work.
- Recommended action: Keep lifecycle smoke, direct provider smoke, and provider quality artifacts
  as separate signals. Continue treating skipped OpenAI artifacts as `defer`, not as prompt/ranking
  tuning input.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Targeted provider tests passed with `15 passed`; stub provider quality returned
  `passed`; OpenAI quality/comparison returned `skipped` with runtime provenance. Direct OpenAI
  smoke was skipped by configuration, so no direct provider success claim was made.

### F-provider-02 Lifecycle provider provenance omits model and endpoint transport

- Severity: `medium`
- Area: `review-bot`
- Evidence level: `static_code`
- Evidence: [review-bot/review_bot/providers/openai_provider.py](/home/et16/work/review_system/review-bot/review_bot/providers/openai_provider.py:330)
  reads both `BOT_OPENAI_MODEL` and `BOT_OPENAI_BASE_URL`, and the provider quality CLI records
  configured model, endpoint base URL, and transport class at
  [review-bot/review_bot/cli/evaluate_provider_quality.py](/home/et16/work/review_system/review-bot/review_bot/cli/evaluate_provider_quality.py:20).
  But lifecycle `ProviderRuntimeMetadata` only contains configured/effective provider plus fallback
  fields at [review-bot/review_bot/providers/base.py](/home/et16/work/review_system/review-bot/review_bot/providers/base.py:29),
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3249)
  persists only those fields to `review_runs.provider_runtime`. The API schema exposes the same
  narrow shape at [review-bot/review_bot/schemas.py](/home/et16/work/review_system/review-bot/review_bot/schemas.py:47),
  while summary/log text describes any non-stub effective provider as `(live provider path)` at
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3319).
- Impact: A lifecycle run using `BOT_OPENAI_BASE_URL=http://...` can look identical to a default
  OpenAI run in the current-state API, review summary note, and structured logs. Operators cannot
  tell which model/backend produced comments, and a local-backend success can be mistaken for live
  OpenAI success unless a separate artifact happens to exist.
- Recommended action: Extend lifecycle provider runtime metadata to include sanitized
  `configured_model`, `endpoint_base_url`, and `transport_class` for OpenAI-compatible providers,
  and surface those fields in state API, structured logs, and provider summary text. Add targeted
  tests for default OpenAI, non-default local backend, stub, and fallback cases.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Static code review found the provenance gap. Targeted existing provider runtime
  tests pass, which confirms the current narrow contract but does not cover model/base-url
  provenance. Follow-up validation should run provider runtime tests plus provider quality tests;
  direct OpenAI smoke is only required if claiming live provider success.

이후 finding은 아래 형식을 따른다.

```md
### F-<area>-NN <short title>
- Severity: `critical|high|medium|low|info`
- Area: `review-engine|review-bot|review-platform|ops|docs|cross-cutting`
- Evidence level: `static_doc|static_code|deterministic_validation|runtime_smoke|direct_provider|human_review`
- Evidence: [path](/abs/path:line), command `...`, observed behavior `...`
- Impact: <user, operator, correctness, trust, or maintenance impact>
- Recommended action: <concrete action or explicit keep rationale>
- Follow-up target: `direct fix|docs/ROADMAP.md|deferred|remove|needs decision|none`
- Post-review bucket: `bug_fix|roadmap_update|deferred_update|remove|keep|needs_decision`
- Validation note: <validation already run, needed later, or skipped reason>
```

Finding rules:

- Findings must be evidence-first and include impact plus recommended action.
- `keep` findings are allowed when the current direction is intentionally preserved.
- Only findings with an executable follow-up target enter
  [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1).
- A blocked or skipped runtime signal must be recorded as skipped evidence, not as proof.

## Direction Check

유지한다.

- Core value: 기존 Git review UI 안에서 high-signal inline review, backlog/status note,
  feedback loop, lifecycle analytics를 제공한다.
- Scope boundary: `review-engine`은 rule/retrieval candidate 생성, `review-bot`은
  detect/publish/sync lifecycle, adapter는 외부 review system bridge, `review-platform`은
  local harness 역할로 유지한다.
- Investment direction: 다음 구현 투자는 rule gap evidence, note-first UX contract,
  provider provenance/retained artifact, deferred readiness처럼 현재 product boundary를
  더 실행 가능하게 만드는 준비 작업에 둔다.
- Defer/avoid: Multi-SCM, auto-fix, manual editor, provider tuning처럼 권한, quota,
  trust metric, human review가 필요한 surface는 현재처럼 deferred 또는 readiness packet
  단계에 둔다.

Unit 2에서는 새로운 actionable backlog entry를 만들지 않았다. 확인된 판단은 현재 방향을
유지해야 한다는 `keep` 성격이고, 넓은 surface의 선행 조건은 이미 implementation
roadmap과 deferred 문서에 분리되어 있다.

## Architecture And Boundary Check

Canonical request identity는 문서, API, DB, runner lookup, GitLab adapter path 구성에서
일관된다. `review-platform`은 여전히 local harness로 문서화되어 있고, 운영 필수
구성요소로 승격된 증거는 없다.

주요 정리 후보는 local harness와 `review-bot` 사이의 stale `pr_id` bridge다.
`review-platform` 자체가 product boundary로 승격된 것은 아니지만, 현재 BotClient는
current key-based bot API를 호출하지 않아 harness integration signal을 약하게 만든다.

## Engine Correctness Check

현재 번들 기준으로 canonical YAML, generated dataset, active retrieval path는 서로
맞는다. Rule source coverage matrix도 committed source atom을 빠뜨리지 않고 분류한다.

다만 `review-engine`의 pack/profile 경계에는 silent drift 방지 장치가 더 필요하다.
중복 pack identity와 누락된 profile-selected pack은 loader 단계에서 실패해야 하고,
`REVIEW_ENGINE_DEFAULT_PROFILE`은 실제 runtime selection에 연결하거나 제거해야 한다.
Coverage matrix는 source atom completeness에 더해 canonical rule reverse coverage도
검증해야 한다.

## Engine Authoring And Lifecycle UX Check

Minimal rule lifecycle CLI는 현재 운영자 UX로 충분하다. `list`/`show`는 generated
dataset 없이 canonical YAML runtime을 읽고, mutation command는 single pack entry나
single profile pack list만 바꾸며, output에 write boundary와 validation plan을 남긴다.

Manual editor는 계속 deferred로 두는 편이 맞다. 지금 필요한 것은 UI가 아니라 strict
authoring validation과 readiness packet이다. 특히 canonical YAML model이 unknown key를
거부하지 않는 공백을 먼저 닫아야 editor나 form이 잘못된 metadata를 조용히 쓰는 위험을
막을 수 있다.

## Review-Bot Lifecycle Correctness Check

`review-bot`의 기본 lifecycle boundary는 현재 방향과 맞다. API는 `ReviewRequestKey`로
run을 만들고 detect job만 enqueue하며, worker가 detect -> publish -> sync를 이어서
실행한다. Runner는 remote thread snapshot reconciliation, feedback ingestion,
publication state, lifecycle event 기록을 함께 다루므로 source of truth가 adapter로
새지 않는다.

주요 수정 후보는 두 가지다. GitLab note trigger에서 source branch head를 보정한 뒤에도
MR diff head가 끝까지 settle되지 않으면 stale diff로 성공할 수 있으므로 retryable failure
또는 explicit pending 상태가 필요하다. 또한 adapter thread/comment/feedback identity가
contract에서는 request-scoped일 수 있는데 DB는 global unique로 가정하므로, scope를
명시하거나 composite uniqueness로 바꿔야 한다.

## Provider, Fallback, And Model Backend Review

Provider boundary는 대체로 올바르게 분리되어 있다. Normal lifecycle은 `openai -> stub`
fail-open을 유지할 수 있고, direct provider smoke와 provider quality artifact는 lifecycle
success와 별개 signal로 남는다. 이번 unit에서는 direct OpenAI preflight가 configuration에
의해 skipped였으므로 live OpenAI 성공 판단은 하지 않았다.

Deterministic validation 기준으로는 `stub` provider quality gate가 6개 packaged case를
모두 통과했고, OpenAI quality/comparison path는 `OPENAI_API_KEY`가 없을 때 skipped
artifact와 `provider_runtime`을 남긴다. 이 점은 provider tuning을 자동으로 진행하지 않고
`defer`로 남기는 현재 정책과 맞다.

남은 gap은 lifecycle provenance다. `BOT_OPENAI_BASE_URL`로 local/backend endpoint를 붙일
수 있는데, review run 상태 API와 summary/log는 model, endpoint, transport class를 담지
않는다. Provider quality artifact에는 이미 이 richer provenance가 있으므로 lifecycle
runtime metadata도 같은 수준으로 맞춰야 fallback lifecycle pass, local backend success,
default OpenAI success를 운영자가 혼동하지 않는다.

## Interface And UX Assessment

아직 평가 전. Unit 8에서 user-facing command와 note surface를 점검한다.

## Roadmap / Deferred Assessment

아직 평가 전. Unit 10에서 roadmap과 deferred 문서의 역할 분리를 점검한다.

## Post-Review Handoff

- `bug_fix`: 코드나 테스트를 직접 고쳐야 하는 결함
- `roadmap_update`: 구현 roadmap에 새 작업을 추가하거나 우선순위를 고쳐야 하는 항목
- `deferred_update`: deferred 문서의 조건, 사유, 범위를 보정해야 하는 항목
- `remove`: 더 이상 유지할 이유가 약한 기능, wrapper, 문서, compatibility path
- `keep`: 현재 방향을 유지할 근거가 충분한 항목
- `needs_decision`: 자동화가 판단하면 안 되는 제품 또는 운영 결정

## Recommended Actions

다음 review action은 `8. User Interface And Review UX Review`다. Unit 6의 API queue
validation hang은 follow-up test-gate 조사 대상으로 남기고, Unit 7의 direct OpenAI smoke는
configuration에 의해 skipped된 provider evidence limitation으로 남긴다.
