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

다음 review unit은 `5. review-engine Authoring And Lifecycle UX Review`다.
