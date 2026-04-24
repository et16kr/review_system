# Current Review System

## Purpose

이 문서는 현재 구현 기준의 구조와 운영 전제를 한 곳에 고정한다.
과거 설계 문서의 결론 중 아직 유효한 내용만 남기고, 완료된 구현 지시나 토론 이력은 포함하지 않는다.

## Workspace

- `review-engine/`: 다언어 rule ingestion, retrieval, diff/code review candidate 생성
- `review-bot/`: webhook/API, `detect -> publish -> sync` lifecycle, thread/feedback 상태 관리
- `review-platform/`: 로컬 데모와 통합 테스트용 harness
- `ops/`: compose, local GitLab, smoke/replay/baseline/telemetry 스크립트

루트 `docker-compose.yml`은 engine 단독 실행용이고, 통합 스택은 `ops/docker-compose.yml` 기준이다.

## Canonical Invariants

- Business identity는 `ReviewRequestKey(review_system, project_ref, review_request_id)`다.
- GitLab `project_ref`는 webhook payload의 `project.path_with_namespace`를 canonical source로 쓴다.
- `review-bot`은 `detect -> publish -> sync` lifecycle을 책임진다.
- `review-platform`은 운영 표준이 아니라 local harness다.
- GitLab MR open/update만으로 자동 inline review를 게시하지 않는다.
- GitLab 리뷰 트리거는 MR note의 `@review-bot ...` 또는 `/review-bot ...` 명령이다.
- 지원 명령은 `review`, `summarize`, `walkthrough`, `full-report`, `backlog`, `help`다.
- Provider는 1차 탐지기가 아니라 finding 설명과 수정 가이드 생성기에 가깝다.
- 품질 KPI는 Prometheus counter가 아니라 distinct fingerprint 기반 analytics에서 계산한다.

## Review-Bot Lifecycle

1. `detect`
   - adapter에서 MR metadata와 diff를 가져온다.
   - file별 language/profile/context/dialect를 판별한다.
   - `review-engine`에서 rule 후보와 evidence를 받아 `FindingDecision`을 만든다.
   - 현재 thread snapshot과 human feedback을 먼저 반영해 suppress/rerank를 수행한다.
2. `publish`
   - batch cap, file round-robin, rule family cap, same-line/category duplicate suppression을 적용한다.
   - 기존 open/reopened thread update를 새 finding보다 우선한다.
   - inline anchor가 불가능한 finding은 실패/억제 상태로 남긴다.
3. `sync`
   - remote discussion 상태, human reply, resolved/reopened transition을 수집한다.
   - feedback command와 lifecycle event를 immutable history로 남긴다.
   - 수동 resolve와 follow-up commit 기반 fix는 `remote_resolved_manual_only`와 `fixed_in_followup_commit`로 구분한다.

## Data Model

핵심 테이블:

- `review_requests`
- `review_runs`
- `finding_evidences`
- `finding_decisions`
- `publication_states`
- `thread_sync_states`
- `feedback_events`
- `finding_lifecycle_events`
- `dead_letter_records`

`ThreadSyncState`는 current-state snapshot이고, Phase A 이후 lifecycle analytics의 source of truth는 `finding_lifecycle_events`다.

## Metrics And Analytics

- Prometheus는 운영 이벤트 볼륨을 본다.
- Quality analytics는 distinct fingerprint를 기준으로 계산한다.
- Canonical quality endpoint는 `GET /internal/analytics/finding-outcomes`다.
- Rule learning / effectiveness는 rerun row 수가 아니라 distinct fingerprint latest meaningful state를 기준으로 본다.
- Wrong-language 분석은 `FeedbackEvent.payload`의 immutable event와 `GET /internal/analytics/wrong-language-feedback`를 기준으로 한다.
- 현재 wrong-language analytics는 parsed human reply event를 집계한다. repeated reply는 event count에 들어갈 수 있고, smoke fixture가 만든 synthetic feedback도 project filter 없이 보면 같이 보인다.
- Wrong-language response는 `provenance`, `triage_cause`, `actionability`를 포함한다. 운영 detector backlog는 기본적으로 `actionability=fix_detector` 후보만 사용하고, smoke/synthetic event는 telemetry loop 검증으로 분리한다.

## Review-Engine Current State

현재 멀티 랭귀지 core canonicalization은 current seed source bundle 기준으로 완료된 상태다.

- `rules/**/*.yaml`에 language별 canonical pack/profile/policy가 있다.
- `rule_sources/coverage_matrix.yaml`은 source atom 단위 coverage를 관리한다.
- current seed source bundle 기준 `pending` atom은 없다.
- `auto_review`와 `reference_only`는 의도적으로 분리한다.
- language/profile/context/dialect routing은 registry와 query detector가 담당한다.
- provider prompt는 C++ 고정 가정 없이 language/profile/context hint를 사용한다.
- Provider quality gate는 packaged corpus와 `python -m review_bot.cli.evaluate_provider_quality --provider stub` 기준으로 network 없이 실행할 수 있다.
- Provider quality corpus는 YAML CI, FastAPI, SQL, CUDA async stream, CUDA cooperative groups regression case를 포함한다.
- Provider comparison artifact는 `python -m review_bot.cli.compare_provider_quality`로 생성한다.
  OpenAI API key가 없으면 `openai_status=skipped` baseline으로 남길 수 있다.
- lifecycle smoke와 direct OpenAI smoke는 다른 신호로 취급한다.
  fallback이 켜져 있으면 lifecycle smoke만으로 live OpenAI 성공을 증명하지 않는다.
- `BOT_OPENAI_BASE_URL`를 지정하면 기존 `openai` provider/client를 그대로 사용해
  OpenAI-compatible endpoint로 라우팅할 수 있다.
- direct provider smoke의 invalid API key probe는 기본 OpenAI base URL에서만 canonical signal로 본다.
- `review_runs.provider_runtime`에 configured/effective provider와 fallback provenance를 저장하고,
  current-state API는 최신 run의 provenance를 바로 노출한다.
- Markdown 문서는 명시적 unreviewable `markdown`으로 분류한다.
- 마지막 점검 기준 rule count는 public/shared seed 기준 `344`개다.
- extension rule root, prompt overlay, entry point, detector plugin hook, strict loading 골격은 구현되어 있다.
- `python -m review_engine.cli.rule_lifecycle`는 canonical YAML runtime을 직접 읽는
  `list`/`show`와 canonical source mutation `disable`/`enable`/`disable-pack`/`enable-pack`
  범위를 제공한다.
- 다만 summary/log surface에서 같은 provenance를 더 직접 읽게 하는 작업은 아직 roadmap에 남아 있다.

현재 주요 지원 축:

- `cpp`, `c`, `cuda`
- `python`, `typescript`, `javascript`, `java`, `go`, `rust`, `bash`
- `sql`, `yaml`, `dockerfile`
- YAML contexts: GitLab CI, GitHub Actions, Kubernetes, Helm, product/schema config
- SQL profiles/dialects: warehouse, dbt, migration, PostgreSQL 등
- CUDA profiles: default, async runtime, multigpu, tensor core, cooperative groups, pipeline async, thread block cluster, TMA, WGMMA

## Rule And Extension Model

- 사람이 수정하는 기준은 canonical YAML rule source다.
- Generated dataset/vector collection은 ingest 산출물로 본다.
- Public core는 public rule pack만으로 동작해야 한다.
- Private/organization rule을 붙일 수 있는 extension root, prompt root, detector plugin 경로는 코드에 있다.
- extension loading failure policy는 다음처럼 고정한다.
- prod/release gate는 기본값인 `REVIEW_ENGINE_STRICT_EXTENSION_LOADING=1`을 유지하고,
  invalid extension spec나 잘못된 extension rule root를 runtime load/ingest에서 fail-fast 한다.
- local dev는 optional entry-point payload를 실험할 때만
  `REVIEW_ENGINE_STRICT_EXTENSION_LOADING=0`으로 낮출 수 있고,
  이 경우 malformed entry-point spec은 warning 후 public core fallback으로 계속 진행한다.
- 명시적으로 지정한 `REVIEW_ENGINE_EXTENSION_RULE_ROOTS` filesystem root의 manifest/YAML 오류는
  운영자가 직접 선택한 입력이므로 dev/prod 모두 fail-fast 한다.
- broken import/init entry point는 detector/prompt plugin이 optional surface인 현재 구조상
  dev/prod 모두 warning-only로 남기고 public core를 계속 로드한다.
- private/public release gate는 `ops/scripts/run_review_engine_extension_ci.sh`로 분리됐다.
- `pack_id`가 canonical pack identity이고, `source_family`는 API/analytics/chroma compatibility를 위한
  legacy read-only alias로만 유지한다.
- runtime input에 `pack_id`와 `source_family`가 함께 오면 같은 값이어야 하며,
  다르면 ambiguous extension identity로 보고 fail-fast 한다.
- extension authoring에서 `pack_weight`는 policy YAML `pack_weights`에만 둔다.
- `reference_only`는 rule entry `reviewability`로만 표현하고,
  `conflict_action`은 policy override/exclusion이 해석된 runtime state로만 본다.
- lifecycle CLI의 `disable`/`enable`은 single canonical pack YAML entry의 `enabled` field만 바꾸고,
  mutation output에서 `write_boundary=canonical_pack_yaml`를 반환한다.
- lifecycle CLI의 `disable-pack`/`enable-pack`은 single canonical profile YAML의
  `enabled_packs` 또는 `shared_packs`만 바꾸고, pack entry YAML 자체는 수정하지 않는다.
- profile YAML이 explicit `enabled_packs`/`shared_packs` 없이 `default_enabled` fallback에 의존하면,
  pack mutation은 현재 runtime selection을 explicit profile pack list로 materialize한 뒤 적용한다.
- selected runtime이 여러 profile YAML merge 결과면 pack mutation은 single write boundary를 잃으므로 fail-fast 한다.
- private rule packaging은 아직 roadmap 대상이다.
- 우선순위는 특정 조직명 하드코딩이 아니라 pack/profile policy로 표현한다.

## Adapter State

현재 구현:

- `local_platform`: local harness adapter
- `gitlab`: GitLab MR discussion/status/general note adapter

Adapter V2 capability는 [API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)에 고정한다.
다음 SCM 확장 후보는 GitHub, 그 다음 Gerrit이다.

## User-Facing Review UX

- Inline comment는 high-signal finding만 제한적으로 게시한다.
- run-level summary note는 게시 수, backlog, feedback suppress 상태를 구분한다.
- `summarize`는 최신 run/head, provider provenance, aggregate backlog/suppress count만 빠르게 보여 준다.
- `walkthrough`는 summarize/backlog/full-report를 어떤 순서로 읽어야 하는지와 backlog reason 해석을 안내한다.
- `full-report`는 최신 완료 run과 현재 MR backlog를 함께 보여 준다.
- `backlog`는 현재 MR에 실제로 남아 있는 backlog 중심으로 보여 준다.
- `ignore`, `false-positive`, `later`, `allow`, `wrong-language <lang>` feedback을 지원한다.
- 반복 검출은 허용하지만 반복 게시는 줄인다.
- review unit은 현재 hunk 기반이며, 큰 add-only hunk는 작은 unit으로 나눈다.
- adapter가 지원하면 head 파일 내용을 일부 가져와 same-file `file_context`로 쓴다.
- `review-engine` codebase index/search가 있으면 project-scoped similar code를 evidence/provider input에 넣을 수 있다.
- AST 기반 syntax-aware split, broader project-scoped memory, `.review-bot.yaml`, `ask` command는 아직 없다.
- provider 설정값은 문자열 환경 변수 기반이며,
  `BOT_PROVIDER`, `BOT_FALLBACK_PROVIDER`는 `openai`/`stub` allowlist로 startup fail-fast 검증한다.

## Security And Retention

- GitLab token은 MR metadata/diff/discussion/status에 필요한 최소 권한만 사용한다.
- `GITLAB_TOKEN`, `GITLAB_WEBHOOK_SECRET`, `OPENAI_API_KEY`는 secret manager 또는 orchestrator secret으로 주입한다.
- Local `.env`는 dev 전용이다.
- 권장 retention:
  - `review_runs`, `finding_evidences`, `finding_decisions`, `publication_states`: 90일
  - `thread_sync_states`: open thread 유지, resolved/stale 180일
  - `feedback_events`: 180일
  - `dead_letter_records`: 30일

## Validation Assets

- Engine examples:
  - `review-engine/examples/expected_retrieval_examples.json`
  - `review-engine/examples/cpp_diff_contracts.json`
  - `review-engine/examples/*_diffs/*.diff`
- Smoke fixtures:
  - `ops/fixtures/review_smoke/synthetic-mixed-language`
  - `ops/fixtures/review_smoke/curated-polyglot`
  - `ops/fixtures/review_smoke/cuda-targeted`
- `expected_smoke.json`은 language/rule/routing contract와 함께 density contract를 가진다.
  현재 density contract는 기본 local GitLab smoke batch cap `5`와 fixture별 comment path
  분산을 검증한다. `synthetic-mixed-language`와 `curated-polyglot`은 최소 distinct path
  `3`, `cuda-targeted`는 `2`, path별 최대 comment 수는 공통으로 `2`다.
- 일부 smoke fixture는 telemetry flow 검증을 위해 intentional `wrong_language_feedback` reply를 만든다. 이 이벤트는 `provenance=smoke`, `triage_cause=synthetic_smoke`로 분리되며 detector blind spot으로 바로 해석하지 않는다.
- Standard local GitLab smoke:
  - `ops/scripts/smoke_local_gitlab_lifecycle_review.sh`
  - `ops/scripts/smoke_local_gitlab_multilang_review.sh`

검증 명령과 운영 절차는 [OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)를 따른다.
