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

User-facing review UX 기준으로는 현재 6개 note command surface가 적절하다. `review`는
명시적 trigger, `summarize`/`walkthrough`/`full-report`/`backlog`/`help`는 GitLab
general note에서 상태를 읽는 보조 surface로 분리되어 있고, `.review-bot.yaml`과 `ask`는
아직 contract-first roadmap 항목으로 남아 있어 구현하지 않는 판단이 맞다. 다만
`@review-bot fullreport` 같은 directed unknown command는 webhook response에서만
ignored_reason을 반환하므로 GitLab 사용자가 실패 이유를 보지 못한다.

Ops/smoke automation review 기준으로는 release gate, pre-release GitLab smoke, direct
provider smoke를 분리하는 현재 운영 경계가 맞다. Lifecycle smoke와 mixed-language smoke는
runtime GitLab evidence로 유지하고, fixture contract와 direct-smoke script behavior는
deterministic tests로 일부 보호된다. 다만 review-roadmap automation은 blocked unit skip을
`/tmp` 안에서만 보존해 반복 blocker audit에 남기지 않고, OpenAI direct smoke preflight는
enabled 상태에서 network call timeout이 없어 automation loop를 멈출 수 있다.

Docs/roadmap/deferred review 기준으로는 구현 roadmap과 deferred 문서의 큰 역할 분리는
맞다. Active work는 evidence refresh, note-first UX contract, local backend artifact
prep, deferred readiness packet으로 제한되어 있고, 바로 구현하면 큰 surface는 deferred에
남아 있다. 다만 `ROADMAP.md`의 watch/current snapshot label이 너무 넓어 이번 리뷰에서
확인한 provider lifecycle provenance, review-roadmap blocked artifact retention, direct
smoke timeout gap을 닫힌 기반처럼 보이게 한다. 또한 `CURRENT_SYSTEM.md`가 private rule
packaging을 roadmap 대상으로 명시하지만 `ROADMAP.md`와 deferred 문서에는 해당 owner가 없다.

Dead code/docs cleanup review 기준으로는 삭제하거나 이름을 정리해야 할 작은 표면이 남아
있다. `review-engine/app/`에는 패키징, Docker image, 문서, 테스트 fixture 경계에 속하지
않는 tracked Next.js 예제 파일이 있고, 루트 `review_system.md`는 canonical docs index 밖에서
README/docs와 중복된다. Local GitLab smoke도 lifecycle wrapper가 생겼지만 bootstrap/replay
및 README/runbook의 기본 명령은 여전히 `tde` 이름을 canonical처럼 노출한다.

Test coverage/gate review 기준으로는 deterministic gate와 runtime smoke를 분리하는 큰 방향은
맞다. Engine source coverage, smoke fixture, direct-smoke fake-curl, parser-only command tests는
빠르게 신호를 냈고 local GitLab/runtime provider smoke를 남용할 필요는 없다. 다만 표준 검증
목록에 포함된 `review-bot` API queue TestClient path와 `review-platform` TestClient path가
bounded run에서 output 없이 timeout되어, 현재 상태로는 documented gate가 회귀 신호가 아니라
automation hang으로 변할 수 있다.

Consolidated review outcome 기준으로는 이번 `gpt-5.5` 리뷰 라운드에서 critical/high finding은
없었다. 후속 실행은 medium severity bug-fix와 gate reliability를 먼저 닫고, `ROADMAP.md`
보정, low severity cleanup 순서로 나누는 것이 맞다. 새 구현이나 deferred 문서 수정은 이 리뷰
unit의 산출물이 아니며, backlog entry를 post-review handoff source로 사용한다.

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

### Unit 8 Evidence

- Current command contract:
  [README.md](/home/et16/work/review_system/README.md:7),
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:24),
  and [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:559)
  define explicit MR note commands as the user-facing review UX.
- Live command parser and webhook dispatch:
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:383)
  limits recognized note commands to `review`, `full-report`, `summarize`, `walkthrough`, `backlog`,
  and `help`, while
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:287)
  dispatches report-style commands without enqueueing detect jobs.
- General note rendering and upsert boundary:
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1359)
  posts same-purpose `full-report`, `summarize`, `walkthrough`, `backlog`, and `help` notes, and
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3567)
  prefers adapter `upsert_general_note` before falling back to append.
- Note content surfaces:
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3667),
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3765),
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3831),
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3915),
  and [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:4001)
  render full report, backlog, summarize, walkthrough, and help notes.
- Deferred UX surfaces:
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:179)
  states `.review-bot.yaml` and `ask` do not exist yet, while
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:70)
  and [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:93)
  keep them as contract-definition work before implementation.
- Unknown command behavior:
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:244)
  returns `ignored_reason=unknown_command:...` without posting a visible note, and
  [review-bot/tests/test_api_queue.py](/home/et16/work/review_system/review-bot/tests/test_api_queue.py:713)
  verifies no detect job is enqueued for `@review-bot fullreport`.
- Static scans:
  `rg -n 'review-bot\\.yaml|ask command|@review-bot ask|/review-bot ask|ask' README.md docs review-bot/review_bot review-bot/tests ops -g '!**/.venv/**'`
  and
  `rg -n 'full report|full-report|summarize|walkthrough|backlog|help|unknown_command|multiple|unsupported' review-bot/tests/test_api_queue.py review-bot/tests/test_review_runner.py docs/API_CONTRACTS.md docs/CURRENT_SYSTEM.md`.
- Validation passed:
  `UV_CACHE_DIR=/tmp/uv-cache uv run --project review-bot pytest review-bot/tests/test_api_queue.py::test_extract_gitlab_note_command_recognizes_supported_commands review-bot/tests/test_api_queue.py::test_extract_gitlab_note_command_flags_unknown_and_incidental review-bot/tests/test_review_runner.py::test_post_full_report_note_posts_backlog_overview review-bot/tests/test_review_runner.py::test_render_full_report_note_includes_surfacing_reason_detail_for_suppressed_items review-bot/tests/test_review_runner.py::test_post_full_report_note_upserts_same_purpose_general_note review-bot/tests/test_review_runner.py::test_post_backlog_note_posts_backlog_only_view review-bot/tests/test_review_runner.py::test_render_summarize_note_includes_aggregate_status_and_followup_commands review-bot/tests/test_review_runner.py::test_post_summarize_note_upserts_same_purpose_general_note review-bot/tests/test_review_runner.py::test_render_walkthrough_note_guides_note_order_and_backlog_reasons review-bot/tests/test_review_runner.py::test_post_walkthrough_note_upserts_same_purpose_general_note review-bot/tests/test_review_runner.py::test_render_help_note_lists_walkthrough_command -q`
  passed with `11 passed`.
- Skipped validation: local GitLab smoke was not run because this UX review did not need runtime
  webhook/thread evidence. OpenAI direct smoke was skipped by configuration and was not relevant.
  Provider validation was not used.

### Unit 9 Evidence

- Release gate and smoke tier documentation:
  [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:300)
  separates deterministic release gates from local GitLab pre-release smoke, and
  [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:310)
  keeps direct OpenAI provider smoke as a separate provider signal.
- Lifecycle smoke wrapper and assertion boundary:
  [ops/scripts/smoke_local_gitlab_lifecycle_review.sh](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_lifecycle_review.sh:4)
  delegates to the compatibility wrapper, and
  [ops/scripts/smoke_local_gitlab_tde_review.sh](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh:7)
  runs replay with default updates, reply, resolve, sync, and default smoke assertions. The assertion
  function at [ops/scripts/replay_local_gitlab_tde_review.py](/home/et16/work/review_system/ops/scripts/replay_local_gitlab_tde_review.py:421)
  checks baseline success, failed publications, open threads, incremental replay heads, feedback
  increase, and open-thread decrease after resolve/sync.
- Mixed-language smoke contract:
  [ops/scripts/smoke_local_gitlab_multilang_review.py](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.py:511)
  validates expected/forbidden language tags and comment volume, while
  [ops/scripts/smoke_local_gitlab_multilang_review.py](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.py:546)
  enforces density across paths. Wrong-language telemetry generated by smoke is checked as
  `provenance=smoke`, `triage_cause=synthetic_smoke`, and
  `actionability=ignore_for_detector_backlog` at
  [ops/scripts/smoke_local_gitlab_multilang_review.py](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.py:731).
- Review roadmap automation wrapper:
  [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:215)
  appends blocked unit details only to a temp file, and
  [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:370)
  skips blocked review units in the same run without writing a retained artifact.
- Implementation roadmap automation contrast:
  [ops/scripts/advance_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_roadmap_with_codex.sh:263)
  records blocked artifact entries and
  [ops/scripts/advance_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_roadmap_with_codex.sh:308)
  flushes them into `docs/baselines/roadmap_automation`.
- Roadmap automation artifact contract:
  [docs/baselines/roadmap_automation/README.md](/home/et16/work/review_system/docs/baselines/roadmap_automation/README.md:11)
  requires appending one retained entry per blocked roadmap unit, and
  [docs/baselines/roadmap_automation/README.md](/home/et16/work/review_system/docs/baselines/roadmap_automation/README.md:50)
  says repeated blocker review should use retained `blocked_roadmap_units_*.md` artifacts, not
  `/tmp` scratch files.
- OpenAI direct smoke preflight path:
  [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:225)
  invokes the direct smoke script when enabled, and
  [ops/scripts/smoke_openai_provider_direct.sh](/home/et16/work/review_system/ops/scripts/smoke_openai_provider_direct.sh:95)
  uses `curl` for `/models`, invalid-key, and live `/responses` probes without `--max-time` or an
  outer `timeout`.
- Deterministic validation passed:
  `bash -n ops/scripts/advance_review_roadmap_with_codex.sh ops/scripts/advance_roadmap_with_codex.sh ops/scripts/smoke_openai_provider_direct.sh ops/scripts/smoke_local_gitlab_lifecycle_review.sh ops/scripts/smoke_local_gitlab_tde_review.sh ops/scripts/smoke_local_gitlab_multilang_review.sh`
  passed.
- Deterministic validation passed:
  `python3 -m py_compile ops/scripts/replay_local_gitlab_tde_review.py ops/scripts/smoke_local_gitlab_multilang_review.py ops/scripts/capture_review_bot_baseline.py ops/scripts/capture_wrong_language_telemetry.py ops/scripts/build_wrong_language_backlog.py ops/scripts/attach_local_gitlab_bot.py ops/scripts/bootstrap_local_gitlab_tde_review.py`
  passed.
- Deterministic validation passed:
  `UV_CACHE_DIR=/tmp/uv-cache uv run --project review-bot pytest review-bot/tests/test_openai_provider_direct_smoke.py review-bot/tests/test_multilang_smoke_fixture.py review-bot/tests/test_wrong_language_baseline_scripts.py -q`
  passed with `16 passed`.
- Deterministic option-surface checks passed:
  `bash ops/scripts/advance_review_roadmap_with_codex.sh --help` and
  `bash ops/scripts/advance_roadmap_with_codex.sh --help` returned expected help text.
- Skipped validation: local GitLab lifecycle and mixed-language smoke were not run because this unit
  judged the ops/smoke contract boundary from static scripts, docs, and deterministic tests.
  OpenAI direct smoke was skipped by configuration, so no live OpenAI success claim was made.

### Unit 10 Evidence

- Implementation roadmap role and current active items:
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:6),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:43),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:70),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:93), and
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:116).
- Deferred readiness packets and deferred document links:
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:144),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:162),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:180), and
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:198).
- Deferred scope documents:
  [docs/deferred/provider_and_model_work.md](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:10),
  [docs/deferred/rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:10),
  [docs/deferred/platform_expansion.md](/home/et16/work/review_system/docs/deferred/platform_expansion.md:10), and
  [docs/deferred/automation_work.md](/home/et16/work/review_system/docs/deferred/automation_work.md:9).
- Roadmap watch/current snapshot labels:
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:28),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:31),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:220), and
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:223).
- Provider lifecycle provenance gap:
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:103)
  says lifecycle run state exposes configured/effective provider and fallback provenance, while
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:111)
  still says summary/log provenance work remains roadmap-bound and
  [review-bot/review_bot/schemas.py](/home/et16/work/review_system/review-bot/review_bot/schemas.py:46)
  exposes only configured/effective/fallback fields.
- Review-roadmap blocked artifact gap:
  [docs/baselines/roadmap_automation/README.md](/home/et16/work/review_system/docs/baselines/roadmap_automation/README.md:11)
  requires retained blocked-unit artifacts, while
  [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:250)
  stores blocked review units only in a temp file and
  [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:371)
  appends only to that temp summary. The implementation wrapper has retained artifact helpers at
  [ops/scripts/advance_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_roadmap_with_codex.sh:263).
- Private rule packaging ownership gap:
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:127)
  says private/organization extension roots, prompt roots, and detector plugin paths exist, and
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:153)
  says private rule packaging is still a roadmap target. The sample extension root and tests show
  filesystem extension support at
  [review-engine/examples/extensions/private_org_cpp/README.md](/home/et16/work/review_system/review-engine/examples/extensions/private_org_cpp/README.md:1)
  and [review-engine/tests/test_rule_runtime_private_extension.py](/home/et16/work/review_system/review-engine/tests/test_rule_runtime_private_extension.py:16),
  but `docs/ROADMAP.md` only lists provider, editor, multi-SCM, and auto-fix deferred readiness
  packets.
- Static scans:
  `rg -n "review-bot\\.yaml|@review-bot ask|/review-bot ask|\\bask\\b|BOT_OPENAI_BASE_URL|configured_model|endpoint_base_url|transport_class|blocked_unit|blocked_roadmap_units|ROADMAP_AUTOMATION_DESIGN" review-bot review-engine review-platform ops/scripts docs README.md -g '!**/.venv/**'`,
  `rg -n "ProviderRuntimeResponse|provider_runtime|configured_model|endpoint_base_url|transport_class|fallback_reason" review-bot/review_bot review-bot/tests -g '!**/.venv/**'`,
  and
  `rg -n "private rule packaging|private/organization|private rule|organization rule|extension.*pack|packaging|extension root|prompt overlay|entry point|detector plugin|strict loading" docs/ROADMAP.md docs/deferred docs/CURRENT_SYSTEM.md docs/OPERATIONS_RUNBOOK.md docs/API_CONTRACTS.md review-engine -g '!**/.venv/**'`.
- Skipped validation: local GitLab smoke and OpenAI direct smoke were not needed for this
  static docs/roadmap/deferred review. No provider or lifecycle runtime success claim was made.

### Unit 11 Evidence

- Tracked cleanup candidates:
  command `git ls-files | rg '(^app/|^tests/|^data/|^review-engine/app/|review_system\\.md|ROADMAP_AUTOMATION_DESIGN|\\.pytest_cache)'`
  returned only `review-engine/app/api/users/route.ts`, `review-engine/app/dashboard/page.tsx`,
  and `review_system.md` among tracked root/legacy-looking files.
- Orphaned Next.js-looking engine files:
  [review-engine/app/api/users/route.ts](/home/et16/work/review_system/review-engine/app/api/users/route.ts:1)
  and [review-engine/app/dashboard/page.tsx](/home/et16/work/review_system/review-engine/app/dashboard/page.tsx:1)
  are tracked, while [review-engine/pyproject.toml](/home/et16/work/review_system/review-engine/pyproject.toml:28)
  packages only `review_engine*` and
  [review-engine/Dockerfile](/home/et16/work/review_system/review-engine/Dockerfile:7)
  copies `review_engine`, `data`, `examples`, `prompts`, `rules`, `rule_sources`, and `tests`, not
  `app`.
- Static scan:
  `rg -n "review-engine/app|app/api/users/route\\.ts|app/dashboard/page\\.tsx|DB_PASSWORD|export async function POST\\(request: Request\\)" README.md docs ops review-engine review-bot review-platform -g '!**/.venv/**' -g '!review-engine/data/cpp_core_guidelines.html' -g '!ops/gitlab/**'`
  found tests and `examples/expected_retrieval_examples.json` referencing synthetic `app/...` review
  paths, but no reference to `review-engine/app/...` as a fixture or runtime input.
- Root orphan doc:
  [review_system.md](/home/et16/work/review_system/review_system.md:1) duplicates current workspace
  notes and canonical doc priority, while [docs/README.md](/home/et16/work/review_system/docs/README.md:21)
  says current structure should be merged into `CURRENT_SYSTEM.md` and executable procedure into
  `OPERATIONS_RUNBOOK.md`. Static scan
  `rg -n "review_system\\.md" README.md docs AGENTS.md ops review-engine review-bot review-platform -g '!**/.venv/**' -g '!ops/gitlab/**'`
  returned no references.
- TDE-named smoke surface:
  [ops/scripts/smoke_local_gitlab_lifecycle_review.sh](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_lifecycle_review.sh:5)
  delegates to `smoke_local_gitlab_tde_review.sh`, which delegates to
  [ops/scripts/replay_local_gitlab_tde_review.py](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh:5).
  [ops/README.md](/home/et16/work/review_system/ops/README.md:10) and
  [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:425)
  still present `create/bootstrap/replay_local_gitlab_tde_review` names in primary setup and replay
  commands, even though the standard smoke wrapper is lifecycle-named and the old smoke wrapper is
  documented as compatibility-only.
- Deterministic validation passed:
  `bash -n ops/scripts/create_gitlab_tde_review.sh ops/scripts/smoke_local_gitlab_lifecycle_review.sh ops/scripts/smoke_local_gitlab_tde_review.sh`.
- Deterministic validation passed:
  `python3 -m py_compile ops/scripts/create_gitlab_merge_request.py ops/scripts/bootstrap_local_gitlab_tde_review.py ops/scripts/replay_local_gitlab_tde_review.py ops/scripts/smoke_local_gitlab_multilang_review.py`.
- Failed broad scan attempt:
  the first broad `rg` over `ops` hit permission-denied paths under local GitLab runtime data
  (`ops/gitlab/**`). The same scan passed after excluding `ops/gitlab/**`, so this is a validation
  limitation of local runtime artifacts, not a blocker.
- Skipped validation: local GitLab smoke was not run because cleanup judgment did not require
  runtime GitLab evidence. OpenAI direct smoke was skipped by configuration and was not relevant.
  No provider success claim was made.

### Unit 12 Evidence

- Standard validation guidance:
  [docs/REVIEW_ROADMAP.md](/home/et16/work/review_system/docs/REVIEW_ROADMAP.md:533)
  lists `review-bot` API queue and `review-platform` PR flow tests as targeted tests, and
  [AGENTS.md](/home/et16/work/review_system/AGENTS.md:1) also recommends those suites for bot and
  harness changes.
- Existing gate timeout configuration:
  [review-bot/pyproject.toml](/home/et16/work/review_system/review-bot/pyproject.toml:49),
  [review-platform/pyproject.toml](/home/et16/work/review_system/review-platform/pyproject.toml:47),
  and [review-engine/pyproject.toml](/home/et16/work/review_system/review-engine/pyproject.toml:42)
  configure only `testpaths`; static scan
  `rg -n "pytest-timeout|timeout|addopts|faulthandler|durations|testpaths" review-bot/pyproject.toml review-platform/pyproject.toml review-engine/pyproject.toml`
  found no pytest-level timeout or hang diagnostic setting.
- Review-bot API queue TestClient path:
  [review-bot/tests/test_api_queue.py](/home/et16/work/review_system/review-bot/tests/test_api_queue.py:444)
  covers stale GitLab note payload head refresh through `TestClient`, but
  `timeout 20s .venv/bin/pytest tests/test_api_queue.py::test_gitlab_note_webhook_prefers_source_branch_head_when_payload_commit_is_stale -q`
  timed out with exit `124` and no pytest result. Parser-only tests from the same file passed with
  `2 passed`, showing the hang is tied to the TestClient/API path, not collection or command parser
  logic.
- Review-platform TestClient path:
  [review-platform/tests/test_health.py](/home/et16/work/review_system/review-platform/tests/test_health.py:7)
  and [review-platform/tests/test_pr_flow.py](/home/et16/work/review_system/review-platform/tests/test_pr_flow.py:189)
  exercise the FastAPI harness through `TestClient`, but
  `timeout 20s .venv/bin/pytest tests/test_health.py -q` and
  `timeout 45s env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_pr_flow.py::test_bot_facade_routes_forward_requests -q`
  timed out with exit `124` and no pytest result.
- Mock-only bridge coverage:
  [review-platform/tests/test_pr_flow.py](/home/et16/work/review_system/review-platform/tests/test_pr_flow.py:189)
  patches `app.api.main.bot_client`, while
  [review-platform/app/clients/bot_client.py](/home/et16/work/review_system/review-platform/app/clients/bot_client.py:14)
  still calls removed legacy bot endpoints. This confirms the stale bridge remains ungated by an
  unmocked contract test and stays owned by existing backlog `B-review-platform-01`.
- Deterministic validation passed:
  `UV_CACHE_DIR=/tmp/uv-cache uv run --project review-engine pytest review-engine/tests/test_source_coverage_matrix.py -q`
  passed with `1 passed`.
- Deterministic validation passed:
  `UV_CACHE_DIR=/tmp/uv-cache uv run --project review-bot pytest review-bot/tests/test_openai_provider_direct_smoke.py review-bot/tests/test_multilang_smoke_fixture.py -q`
  passed with `14 passed`.
- Skipped validation: local GitLab smoke was not run because this unit judged gate structure from
  static tests and bounded deterministic validation. OpenAI direct smoke was skipped by
  configuration, and this unit made no live provider success claim.

### Unit 13 Evidence

- Consolidation source: all findings in this document from `F-product-01` through `F-tests-02`.
- Backlog source:
  [docs/reviews/REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:46)
  contains 17 actionable entries produced by the review round: 12 `bug_fix`, 2 `roadmap_update`,
  and 3 `remove` entries.
- Severity distribution from the review artifacts: 15 informational keep findings, 13 medium
  actionable findings, 4 low actionable findings, and no critical or high findings.
- Execution grouping: medium `bug_fix` entries that unblock reliable validation and contract safety
  should precede roadmap updates and low-severity cleanup; cleanup remains separate from bug fixes
  so removal work does not hide behavior changes.
- Validation: `git diff --check`.
- Skipped validation: local GitLab smoke and OpenAI direct smoke were not needed for this
  consolidation-only unit. OpenAI direct smoke preflight remained skipped by configuration, so this
  unit makes no live OpenAI success claim.

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

### F-ux-01 Current note command set is narrow enough for the active product boundary

- Severity: `info`
- Area: `review-bot`
- Evidence level: `static_code`
- Evidence: [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:561)
  defines the supported command set as `review`, `summarize`, `walkthrough`, `full-report`,
  `backlog`, and `help`. The live parser at
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:383)
  recognizes the same set, including the safety behavior that a bare mention maps to `review` and
  unknown directed commands do not enqueue review work. [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:179)
  explicitly says `.review-bot.yaml` and `ask` do not exist yet.
- Impact: The user surface stays centered on explicit GitLab MR note triggers and status/report
  notes. This avoids adding configuration precedence, retrieval/session, cost, latency, and answer
  safety questions to the live command path before their contracts are ready.
- Recommended action: Keep the current command set. Continue treating `.review-bot.yaml` and `ask`
  as contract-definition work in the implementation roadmap before adding live behavior.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static code/doc review plus targeted command parser tests passed. No local
  GitLab smoke or provider validation was needed.

### F-ux-02 Report-style notes give users the right reading path without new UI

- Severity: `info`
- Area: `review-bot`
- Evidence level: `deterministic_validation`
- Evidence: [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1359)
  exposes `post_full_report_note`, `post_summarize_note`, `post_walkthrough_note`,
  `post_backlog_note`, and `post_help_note` as Git review-system general notes. The renderers at
  [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:3667)
  through [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:4001)
  separate latest run, in-flight run, current backlog, suppress counts, and backlog reason text.
  Existing targeted tests passed for full-report/backlog rendering, summarize/walkthrough reading
  order, help content, and same-purpose upsert behavior.
- Impact: Users can stay inside GitLab MR notes and still answer the common questions: what was
  just posted, what remains in backlog, why a backlog item appears, what is suppressed, and which
  note to read next. Same-purpose upsert prevents report-style commands from creating unbounded note
  clutter, while run-level summaries remain append-only as documented.
- Recommended action: Keep the summarize -> backlog -> full-report reading path and same-purpose
  upsert behavior. Revisit only after `.review-bot.yaml` or `ask` contract work changes the note
  command model.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Targeted deterministic validation passed with `11 passed`. Local GitLab smoke
  was not required because no adapter/runtime success claim was made.

### F-ux-03 Directed unknown commands are safe but invisible to GitLab users

- Severity: `low`
- Area: `review-bot`
- Evidence level: `static_code`
- Evidence: [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:244)
  returns `accepted=False`, `status=ignored`, and `ignored_reason=unknown_command:...` when a
  line-start bot mention has an unknown token. That is safe because
  [review-bot/tests/test_api_queue.py](/home/et16/work/review_system/review-bot/tests/test_api_queue.py:713)
  verifies `@review-bot fullreport` does not enqueue detect work. But the response is only a
  webhook response; unlike `@review-bot help` at
  [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:327),
  the unknown-command path does not post a visible MR note.
- Impact: A user who mistypes `full-report`, tries deferred `ask`, or copies an unsupported command
  sees no GitLab-visible explanation. The failure mode is safe but looks like the bot ignored the
  user or failed silently, which increases retries and support/debugging time.
- Recommended action: When a directed unknown command has enough GitLab project/MR context and the
  adapter supports general notes, post or upsert a concise same-purpose help/error note that echoes
  the unknown token and lists supported commands. Preserve the current no-enqueue behavior and keep
  incidental mentions silent.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Follow-up should add deterministic tests for visible unknown-command feedback,
  no detect enqueue, and incidental mention silence. Run targeted parser/webhook tests plus the note
  renderer tests. Local GitLab smoke is only needed if GitLab adapter note posting changes.

### F-ops-01 Smoke tiers are correctly separated by evidence type

- Severity: `info`
- Area: `ops`
- Evidence level: `deterministic_validation`
- Evidence: [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:300)
  separates network-free release gates from local GitLab pre-release smoke, and
  [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:310)
  states that direct OpenAI provider smoke is a separate signal. The lifecycle wrapper at
  [ops/scripts/smoke_local_gitlab_tde_review.sh](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh:7)
  runs replay with default updates, reply, resolve, sync, and smoke assertions, while
  [ops/scripts/replay_local_gitlab_tde_review.py](/home/et16/work/review_system/ops/scripts/replay_local_gitlab_tde_review.py:421)
  validates baseline success, incremental heads, feedback increase, and open-thread decrease.
  Mixed-language smoke validates language tags, density, and synthetic smoke telemetry separation
  at [ops/scripts/smoke_local_gitlab_multilang_review.py](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.py:511)
  and [ops/scripts/smoke_local_gitlab_multilang_review.py](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.py:731).
- Impact: Operators can interpret deterministic CI, local GitLab lifecycle evidence, mixed-language
  routing evidence, and direct provider evidence without treating one passing signal as proof of
  another. This is especially important because fallback-enabled lifecycle smoke can pass without
  proving live OpenAI.
- Recommended action: Keep this signal separation. Continue using targeted deterministic tests as
  release gates and local GitLab smoke only for adapter/lifecycle/runtime evidence or pre-release
  checkpoints.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Shell syntax, Python compile, direct-smoke fixture tests, multilang fixture
  tests, and wrong-language baseline rendering tests passed. Local GitLab smoke and OpenAI direct
  smoke were intentionally skipped for this static/deterministic ops review.

### F-ops-02 Review-roadmap blocked units are skipped but not retained for blocker audit

- Severity: `medium`
- Area: `ops`
- Evidence level: `static_code`
- Evidence: [docs/baselines/roadmap_automation/README.md](/home/et16/work/review_system/docs/baselines/roadmap_automation/README.md:11)
  requires retained `blocked_roadmap_units_YYYY-MM-DD.md` entries for skipped blockers, and
  [docs/baselines/roadmap_automation/README.md](/home/et16/work/review_system/docs/baselines/roadmap_automation/README.md:50)
  says repeated blocker review must use retained artifacts instead of `/tmp` scratch files. The
  implementation wrapper records and flushes blocked artifacts at
  [ops/scripts/advance_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_roadmap_with_codex.sh:263)
  and [ops/scripts/advance_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_roadmap_with_codex.sh:467).
  The review wrapper only appends blocked summaries to `$tmpdir/blocked-review-units.txt` at
  [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:215)
  and skips them in-process at
  [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:370);
  cleanup then removes the temp directory.
- Impact: `--until-done` review automation can correctly avoid a blocked unit within one process,
  but the blocked-unit history disappears when the run exits. Repeated local GitLab state,
  credential, or human-review blockers cannot be audited through the documented retained artifact
  procedure, so prioritization may miss recurring review blockers.
- Recommended action: Port the blocked artifact retention path from
  `advance_roadmap_with_codex.sh` into `advance_review_roadmap_with_codex.sh`, including
  `BLOCKER_TYPE`, `BLOCKED_REASON`, validation summary, status, and flush-on-exit behavior. Add a
  deterministic wrapper test or shell harness that simulates `STATUS: BLOCKED` and verifies retained
  artifact content without invoking real Codex.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Static review plus `bash -n` passed. Follow-up should add deterministic wrapper
  tests for blocked-unit retention and ensure no artifact is created when no blocker occurs.

### F-ops-03 OpenAI direct smoke preflight can hang the roadmap loop

- Severity: `medium`
- Area: `ops`
- Evidence level: `static_code`
- Evidence: [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:225)
  runs `smoke_openai_provider_direct.sh` before each review-roadmap iteration when
  `OPENAI_DIRECT_SMOKE=1`, and [ops/scripts/advance_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_roadmap_with_codex.sh:342)
  does the same for implementation roadmap automation. The direct smoke script's `/models`,
  invalid-key, and live `/responses` probes at
  [ops/scripts/smoke_openai_provider_direct.sh](/home/et16/work/review_system/ops/scripts/smoke_openai_provider_direct.sh:95),
  [ops/scripts/smoke_openai_provider_direct.sh](/home/et16/work/review_system/ops/scripts/smoke_openai_provider_direct.sh:115),
  and [ops/scripts/smoke_openai_provider_direct.sh](/home/et16/work/review_system/ops/scripts/smoke_openai_provider_direct.sh:139)
  call `curl` without `--connect-timeout`, `--max-time`, or an outer `timeout`.
- Impact: When direct smoke preflight is enabled and the configured OpenAI-compatible endpoint stalls
  instead of failing quickly, the roadmap automation can hang before the review/implementation unit
  even starts. That leaves no `STATUS` line, no retained blocker artifact, and no clear distinction
  between an unavailable provider and a wedged automation run.
- Recommended action: Bound direct smoke runtime with explicit curl connect/overall timeouts and/or
  an outer wrapper `timeout`, then record timeout exit status in the preflight output. Cover default
  OpenAI, non-default local backend, missing key, and timeout cases with deterministic fake-curl
  tests.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Existing fake-curl direct smoke tests passed, but they cover successful and
  skipped probes only. OpenAI direct smoke was skipped by configuration in this unit; no live
  provider success claim was made.

### F-docs-01 Roadmap and deferred documents mostly preserve the right execution boundary

- Severity: `info`
- Area: `docs`
- Evidence level: `static_doc`
- Evidence: [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:6)
  keeps directly executable work in the implementation roadmap and sends non-executable long-term
  work to `docs/deferred/*.md`. The current active items at
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:43),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:70),
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:93), and
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:116)
  are contract/evidence/artifact prep rather than broad feature implementation. Deferred docs keep
  provider tuning, manual editor, multi-SCM, and auto-fix behind quota, human review, permission,
  validation, trust metric, or safety prerequisites.
- Impact: The roadmap mostly avoids pulling high-risk or externally blocked surfaces into active
  implementation before their evidence and contract boundaries are clear.
- Recommended action: Keep this split. Continue using active roadmap items for narrow readiness or
  contract work, and leave provider tuning, editor, multi-SCM, and auto-fix in deferred/readiness
  form until their listed prerequisites are satisfied.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Static document review only. Runtime smoke and direct provider validation were
  not needed.

### F-docs-02 Roadmap watch labels hide still-open provider and automation follow-up work

- Severity: `medium`
- Area: `docs`
- Evidence level: `static_doc`
- Evidence: [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:28)
  and [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:220)
  mark broad provider runtime guardrails as closed/watch, while
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:111)
  still says summary/log provider provenance work remains on the roadmap and
  [review-bot/review_bot/schemas.py](/home/et16/work/review_system/review-bot/review_bot/schemas.py:46)
  exposes lifecycle provider runtime without model, endpoint, or transport fields. Similarly,
  [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:31)
  and [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:223)
  mark roadmap automation blocked artifact retention as closed/watch, but
  [docs/baselines/roadmap_automation/README.md](/home/et16/work/review_system/docs/baselines/roadmap_automation/README.md:11)
  requires retained blocked artifacts and
  [ops/scripts/advance_review_roadmap_with_codex.sh](/home/et16/work/review_system/ops/scripts/advance_review_roadmap_with_codex.sh:250)
  keeps review-roadmap blocked summaries only in `/tmp`.
- Impact: Post-review handoff can under-prioritize already-confirmed follow-up work because the
  implementation roadmap reads as though whole guardrail categories are closed. That is especially
  risky before local backend capture prep, where lifecycle provenance and direct smoke boundedness
  determine whether provider evidence is interpretable.
- Recommended action: In the post-review `ROADMAP.md` update, split broad closed/watch labels into
  completed sub-scope and remaining work. At minimum, add or promote entries for lifecycle provider
  model/endpoint/transport provenance, retained review-roadmap blocked artifacts, and direct-smoke
  preflight timeout; or narrow the watch labels so they do not imply those gaps are complete.
- Follow-up target: `docs/ROADMAP.md`
- Post-review bucket: `roadmap_update`
- Validation note: Static docs/code review only. Local GitLab smoke and OpenAI direct smoke were
  not needed because this finding concerns roadmap classification, not runtime success.

### F-docs-03 Private rule packaging has no roadmap or deferred owner

- Severity: `medium`
- Area: `docs`
- Evidence level: `static_doc`
- Evidence: [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:127)
  says private/organization extension roots, prompt roots, and detector plugin paths exist, and
  [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:153)
  explicitly says private rule packaging is still a roadmap target. The repo includes a sample
  private extension root at
  [review-engine/examples/extensions/private_org_cpp/README.md](/home/et16/work/review_system/review-engine/examples/extensions/private_org_cpp/README.md:1)
  and deterministic extension-root coverage at
  [review-engine/tests/test_rule_runtime_private_extension.py](/home/et16/work/review_system/review-engine/tests/test_rule_runtime_private_extension.py:16).
  But [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:144)
  through [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:198)
  only queue provider, manual editor, multi-SCM, and auto-fix readiness packets, with no private rule
  packaging or deferred packaging owner.
- Impact: Organization extension support can remain half-finished from an operator perspective:
  filesystem roots and release-gate tests exist, but there is no tracked work for packaging format,
  versioning, distribution, generated artifact policy, or safe installation/update workflow.
- Recommended action: Add a roadmap or deferred readiness owner for private rule packaging, or
  remove the `CURRENT_SYSTEM.md` claim if packaging is intentionally out of scope. The readiness
  packet should define package shape, version/compatibility metadata, validation gate, installation
  path, and how private generated artifacts are kept separate from public core artifacts.
- Follow-up target: `docs/ROADMAP.md`
- Post-review bucket: `roadmap_update`
- Validation note: Static docs/code review only. No runtime smoke or provider validation is needed
  until packaging behavior is implemented.

### F-engine-08 Tracked Next.js scaffold files sit outside the engine fixture and runtime boundaries

- Severity: `low`
- Area: `review-engine`
- Evidence level: `static_code`
- Evidence: [review-engine/app/api/users/route.ts](/home/et16/work/review_system/review-engine/app/api/users/route.ts:1)
  and [review-engine/app/dashboard/page.tsx](/home/et16/work/review_system/review-engine/app/dashboard/page.tsx:1)
  are tracked under `review-engine/app/`, but [review-engine/pyproject.toml](/home/et16/work/review_system/review-engine/pyproject.toml:28)
  packages only `review_engine*`, and [review-engine/Dockerfile](/home/et16/work/review_system/review-engine/Dockerfile:7)
  does not copy `app`. Static scan found synthetic `app/...` paths used in tests and
  `examples/expected_retrieval_examples.json`, but no reference that consumes `review-engine/app`
  itself as a documented fixture.
- Impact: These files look like a real Next.js application inside the engine project even though the
  engine is a Python service. Because the same snippets also exist under `examples/` and tests, the
  tracked `app/` copy can mislead maintainers, confuse scans for active product surface, and drift
  without affecting validation.
- Recommended action: Remove `review-engine/app/` if it is accidental dead scaffold. If the files
  are intended fixtures, relocate them under an explicit `examples/` or `tests/fixtures/` path and
  wire them into deterministic tests so their purpose is clear.
- Follow-up target: `remove`
- Post-review bucket: `remove`
- Validation note: Static ownership review only. A follow-up removal should run
  `rg -n "review-engine/app|app/api/users/route\\.ts|app/dashboard/page\\.tsx" review-engine review-bot docs`
  and the relevant Next.js profile tests, for example
  `cd review-engine && uv run pytest tests/test_language_registry.py tests/test_multilang_regressions.py tests/test_query_conversion.py -q`.

### F-docs-04 Root `review_system.md` duplicates canonical docs without an owner

- Severity: `low`
- Area: `docs`
- Evidence level: `static_doc`
- Evidence: [review_system.md](/home/et16/work/review_system/review_system.md:1) describes current
  workspace structure, official entrypoints, doc priority, and retired root legacy paths. The same
  durable information is already owned by [README.md](/home/et16/work/review_system/README.md:38)
  and the canonical docs index at [docs/README.md](/home/et16/work/review_system/docs/README.md:6).
  Static scan `rg -n "review_system\\.md" README.md docs AGENTS.md ops review-engine review-bot review-platform -g '!**/.venv/**' -g '!ops/gitlab/**'`
  returned no references outside the file itself.
- Impact: The file creates a second, unlinked current-state document outside the docs index. Future
  changes to service boundaries, ports, compose usage, or retired legacy paths can update canonical
  docs while leaving this root note stale.
- Recommended action: Remove `review_system.md` after confirming no external workflow depends on
  the filename, or fold any still-useful wording into `README.md`, `docs/CURRENT_SYSTEM.md`, or
  `docs/OPERATIONS_RUNBOOK.md` before deleting it.
- Follow-up target: `remove`
- Post-review bucket: `remove`
- Validation note: Static docs review is sufficient. Follow-up should run
  `rg -n "review_system\\.md" . -g '!ops/gitlab/**'` before removal and `git diff --check` after
  docs edits.

### F-ops-04 Local GitLab smoke internals still expose `tde` as the primary name

- Severity: `low`
- Area: `ops`
- Evidence level: `static_code`
- Evidence: [ops/scripts/smoke_local_gitlab_lifecycle_review.sh](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_lifecycle_review.sh:5)
  delegates to `smoke_local_gitlab_tde_review.sh`, which then calls
  [ops/scripts/replay_local_gitlab_tde_review.py](/home/et16/work/review_system/ops/scripts/smoke_local_gitlab_tde_review.sh:5).
  [ops/README.md](/home/et16/work/review_system/ops/README.md:10) lists TDE-named create,
  bootstrap, replay, and smoke scripts as current included assets, and
  [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:425)
  uses `bootstrap_local_gitlab_tde_review.py` and `replay_local_gitlab_tde_review.py` as the primary
  local GitLab setup/replay commands while saying only the smoke wrapper is compatibility-only.
- Impact: `tde` now reads as an old fixture name rather than the current lifecycle invariant under
  review. Keeping TDE names as primary entrypoints makes the smoke suite look domain-specific and
  obscures that the standard validation is baseline review, incremental replay, reply, resolve,
  sync, and analytics behavior.
- Recommended action: Introduce lifecycle-named bootstrap/replay/create entrypoints and update docs
  to present those as canonical. Keep the existing TDE-named scripts as compatibility wrappers for a
  deprecation window, or document `tde` explicitly as only the backing fixture name.
- Follow-up target: `remove`
- Post-review bucket: `remove`
- Validation note: Shell syntax and Python compile checks passed for the current scripts. A
  follow-up rename should run `bash -n` for all wrappers, `python3 -m py_compile` for renamed Python
  scripts, targeted script tests if added, and the local GitLab lifecycle smoke when the environment
  is ready.

### F-tests-01 Documented TestClient gates can hang without producing a regression signal

- Severity: `medium`
- Area: `cross-cutting`
- Evidence level: `deterministic_validation`
- Evidence: [docs/REVIEW_ROADMAP.md](/home/et16/work/review_system/docs/REVIEW_ROADMAP.md:533)
  lists `review-bot` API queue and `review-platform` PR-flow tests as targeted validation, but
  `timeout 20s .venv/bin/pytest tests/test_api_queue.py::test_gitlab_note_webhook_prefers_source_branch_head_when_payload_commit_is_stale -q`
  in `review-bot` exited `124` with no pytest result. `timeout 20s .venv/bin/pytest tests/test_health.py -q`
  in `review-platform` and
  `timeout 45s env UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_pr_flow.py::test_bot_facade_routes_forward_requests -q`
  also exited `124` with no pytest result. Static scan of
  [review-bot/pyproject.toml](/home/et16/work/review_system/review-bot/pyproject.toml:49) and
  [review-platform/pyproject.toml](/home/et16/work/review_system/review-platform/pyproject.toml:47)
  found no pytest timeout or hang diagnostic configuration.
- Impact: The repository's recommended deterministic gates can become automation stalls instead of
  pass/fail evidence. That weakens future review units and implementation fixes that rely on API
  queue or harness validation, especially because local GitLab smoke should not be used as a
  substitute for basic API/harness unit coverage.
- Recommended action: Make TestClient-backed gates bounded and diagnosable: add pytest timeout or
  equivalent per-suite guardrails, enable useful hang diagnostics, and isolate the `review-bot`
  API queue and `review-platform` FastAPI startup/lifespan hang so the documented standard commands
  terminate with clear pass/fail output. Keep parser/business-logic tests runnable without ASGI
  startup where possible.
- Follow-up target: `direct fix`
- Post-review bucket: `bug_fix`
- Validation note: Follow-up should first reproduce with the same bounded commands, then make
  `cd review-bot && uv run pytest tests/test_api_queue.py -q` and
  `cd review-platform && uv run pytest tests/test_health.py tests/test_pr_flow.py -q` complete
  without an outer timeout. Local GitLab smoke is not required unless the fix changes GitLab
  adapter/runtime behavior. Direct OpenAI smoke is not relevant.

### F-tests-02 Deterministic and runtime gate separation is directionally right

- Severity: `info`
- Area: `cross-cutting`
- Evidence level: `static_doc`
- Evidence: [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:300)
  separates deterministic release gates from local GitLab pre-release smoke, and
  [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:310)
  keeps direct OpenAI smoke as a separate provider signal. Existing backlog validation notes also
  distinguish deterministic fixes from local GitLab or direct-provider checks, for example
  [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:81)
  and [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:122).
- Impact: Most follow-up work can be validated with focused, network-free tests first, while local
  GitLab smoke remains reserved for adapter/lifecycle/runtime behavior and direct OpenAI smoke
  remains reserved for live provider claims.
- Recommended action: Keep this split. For each post-review fix, add the smallest deterministic
  regression test first, then run local GitLab or direct provider smoke only when the changed
  behavior actually depends on that runtime signal.
- Follow-up target: `none`
- Post-review bucket: `keep`
- Validation note: Deterministic smoke-contract tests passed in this unit. Local GitLab smoke and
  OpenAI direct smoke were skipped because this review did not need runtime GitLab or live provider
  evidence.

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

현재 command UX는 note-first product boundary에 맞다. `review`만 detect job을 만들고,
`summarize`, `walkthrough`, `full-report`, `backlog`, `help`는 current state와 backlog를
MR general note로 읽게 한다. Report-style notes는 same-purpose upsert를 우선하므로 사용자가
상태를 반복 조회해도 note surface가 과하게 늘어나지 않는다.

`.review-bot.yaml`과 `ask`는 지금 구현하지 않는 판단이 맞다. 둘 다 precedence,
retrieval/session, provider availability, answer safety를 먼저 정해야 하므로, 현재처럼
implementation roadmap의 contract-definition 항목으로 남겨야 한다.

수정 후보는 unknown command feedback이다. Directed unknown command는 review를 실행하지 않는
점에서는 안전하지만, webhook response의 `ignored_reason`은 GitLab 사용자에게 보이지 않는다.
따라서 `@review-bot fullreport` 같은 실수에는 visible help/error note를 남기는 편이
사용자 경험과 운영 디버깅에 더 낫다.

## Ops, Smoke, And Automation Assessment

Ops validation boundary는 현재 방향이 맞다. `release gate`는 deterministic pytest와
stub/provider-quality 같은 network-free 신호로 두고, local GitLab lifecycle 및
mixed-language smoke는 pre-release runtime evidence로 유지해야 한다. Direct OpenAI smoke도
fallback lifecycle pass와 분리된 provider signal로 남겨야 하며, 이번 unit에서는 configuration
때문에 실행하지 않았다.

수정 후보는 automation reliability 쪽이다. Review roadmap wrapper는 같은 실행 안에서 blocked
unit을 건너뛰지만, retained blocker artifact를 남기지 않아 반복 blocker review 절차와 맞지
않는다. 또한 OpenAI direct smoke preflight는 enabled 상태에서 외부 endpoint가 멈추면 timeout
없이 roadmap loop를 멈출 수 있으므로, preflight 자체도 bounded validation으로 만들어야 한다.

## Roadmap / Deferred Assessment

구현 roadmap과 deferred 문서의 큰 역할 분리는 맞다. `ROADMAP.md`는 바로 실행 가능한
evidence refresh, `.review-bot.yaml` contract, `ask` boundary, local backend artifact prep을
active로 두고, provider tuning, manual editor, multi-SCM, auto-fix는 readiness packet 또는
deferred 문서에 남긴다. 이 상태는 현재 제품 방향과 맞는다.

다만 post-review handoff 때 `ROADMAP.md`를 보정해야 한다. Broad watch label인
`Provider runtime guardrails`와 `Roadmap automation blocked artifact retention`은 이미 닫힌
부분과 이번 리뷰에서 확인한 남은 gap을 분리해 표현해야 한다. 또한 `CURRENT_SYSTEM.md`가
private rule packaging을 roadmap 대상으로 부르지만, 실제 roadmap/deferred owner가 없으므로
패키징 readiness 또는 deferred 항목을 추가해야 한다.

## Dead Code, Dead Docs, And Cleanup Assessment

이번 unit은 코드 삭제를 수행하지 않고 cleanup 후보만 분류했다. Tracked generated/cache
artifact는 발견되지 않았고, root `ROADMAP_AUTOMATION_DESIGN.md`도 남아 있지 않았다.

삭제 또는 이름 정리 후보는 세 가지다. `review-engine/app/`는 runtime/package/fixture
경계 밖의 Next.js scaffold처럼 보이므로 제거하거나 명시적 fixture 경로로 옮겨야 한다.
루트 `review_system.md`는 canonical docs index 밖에서 현재 상태를 중복하므로 제거하거나
canonical docs로 흡수해야 한다. Local GitLab smoke는 lifecycle wrapper를 표준으로 유지하되,
bootstrap/replay/create 기본 명령의 `tde` 이름은 compatibility layer로 낮추는 것이 맞다.

## Test Coverage And Missing Gate Assessment

누적 findings에 대한 gate 방향은 대체로 맞다. 대부분의 bug-fix 후보는 먼저 deterministic
test로 막고, GitLab adapter/head/thread behavior를 바꿀 때만 local GitLab lifecycle smoke를
실행하면 된다. Provider 쪽도 lifecycle smoke와 direct OpenAI smoke를 계속 분리해야 한다.

새 수정 후보는 test gate reliability다. `review-bot` API queue와 `review-platform` FastAPI
TestClient 기반 테스트는 표준 검증 목록에 있지만 bounded run에서 output 없이 timeout되었다.
이 상태에서는 테스트가 실패 신호를 주기보다 roadmap automation을 멈출 수 있으므로, per-suite
timeout/hang diagnostics와 TestClient startup hang 조사 자체를 post-review bug-fix backlog로
올린다. Local harness bot bridge의 mock-only drift는 이미 `B-review-platform-01`이 owning한다.

## Consolidated Review Outcome

이번 review round는 implementation backlog를 만들기에 충분한 evidence를 확보했다. Critical/high
severity finding은 없고, medium finding은 대부분 silent drift, stale contract, provenance,
automation reliability처럼 실제 회귀를 만들 수 있는 guardrail gap이다. Low severity finding은
사용자 feedback과 cleanup 성격이므로 bug-fix stabilization 뒤에 처리해도 된다.

Post-review 실행 순서는 아래가 가장 안전하다.

1. Gate reliability를 먼저 닫는다: `B-cross-cutting-01`로 TestClient-backed suite가 hang 대신
   bounded failure signal을 내게 만든다.
2. Review-bot contract safety를 닫는다: `B-review-bot-01`, `B-review-bot-02`,
   `B-review-bot-03`, `B-review-bot-04`를 순서대로 처리한다.
3. Harness/ops automation drift를 닫는다: `B-review-platform-01`, `B-ops-01`, `B-ops-02`를
   처리해 local harness bridge와 roadmap/provider preflight automation을 다시 신뢰 가능한
   signal로 만든다.
4. Engine authoring/runtime guardrail을 닫는다: `B-review-engine-01`부터
   `B-review-engine-04`까지 deterministic loader and authoring tests로 막는다.
5. `ROADMAP.md`를 보정한다: `B-docs-01`, `B-docs-02`를 implementation roadmap update로
   반영한다.
6. Cleanup은 별도 batch로 처리한다: `B-review-engine-05`, `B-docs-03`, `B-ops-03`은 behavior
   change와 섞지 않고 removal/rename PR로 분리한다.

이번 round에서 `deferred_update`와 `needs_decision` backlog는 새로 만들지 않았다. Provider
tuning, manual editor, multi-SCM, auto-fix, `ask`, `.review-bot.yaml`은 현재 deferred 또는
contract-first 상태 유지가 맞다는 keep judgment만 남겼다.

## Post-Review Handoff

- `bug_fix`: 코드나 테스트를 직접 고쳐야 하는 결함
- `roadmap_update`: 구현 roadmap에 새 작업을 추가하거나 우선순위를 고쳐야 하는 항목
- `deferred_update`: deferred 문서의 조건, 사유, 범위를 보정해야 하는 항목
- `remove`: 더 이상 유지할 이유가 약한 기능, wrapper, 문서, compatibility path
- `keep`: 현재 방향을 유지할 근거가 충분한 항목
- `needs_decision`: 자동화가 판단하면 안 되는 제품 또는 운영 결정

## Recommended Actions

리뷰 라운드는 완료되었다. 다음 작업은 이 문서가 아니라 post-review handoff다. 먼저
[REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:46)의
`bug_fix` entry 중 gate reliability와 review-bot contract safety를 처리하고, 그 뒤
`roadmap_update`와 cleanup batch를 별도로 진행한다. Unit 7, Unit 9, Unit 13의 direct OpenAI
smoke는 configuration에 의해 skipped된 provider evidence limitation으로 남아 있으며, live
OpenAI success claim은 없다.
