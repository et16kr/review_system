# Roadmap

## Purpose

이 문서는 지금 바로 실행할 수 있는 작업만 관리한다.
이미 끝난 기반 설명은 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
직접 착수할 수 없는 장기 작업은 `docs/deferred/*.md`에 둔다.

마지막 코드 상태 점검일: `2026-04-24`

상태 표기:

- `active`: 지금 바로 commit 단위로 진행할 수 있다.
- `partial`: 일부 기반은 있지만 남은 실행 단위가 있다.
- `queued`: 선행 작업이 끝나면 바로 착수할 다음 후보다.
- `watch`: 구현보다 회귀 방지와 운영 관찰이 중심이다.

운영 원칙:

- external API quota, 사람 승인, 별도 계정 권한이 필요한 작업은 본 문서의 직접 실행 항목으로 두지 않는다.
- 한 roadmap unit은 가능하면 한 commit에서 닫는다.
- 문서만 정리하는 작업도, 다음 구현을 실제로 열어 주는 경우에만 roadmap에 둔다.
- post-review 즉시 수정 항목은 deferred work보다 먼저 닫는다.

## Current Snapshot

`2026-04-24` `gpt-5.5` 리뷰 라운드 기준으로 아래 기반은 유지 판단이 끝났고,
새 구현 대상이 아니다.

- 기존 Git review surface 중심 제품 방향
- canonical `ReviewRequestKey(review_system, project_ref, review_request_id)` identity
- runner-owned `detect -> publish -> sync` lifecycle boundary
- immutable lifecycle event-backed analytics direction
- 현재 번들 기준 `review-engine` canonical YAML, generated dataset, runtime retrieval selection 정합성
- minimal rule lifecycle CLI의 좁은 운영 범위
- `review`, `summarize`, `walkthrough`, `full-report`, `backlog`, `help` note command surface
- deterministic gate, local GitLab runtime smoke, direct provider smoke를 분리하는 운영 원칙
- `review-bot` / `review-platform` TestClient gate와 OpenAI direct smoke preflight의 bounded
  runtime diagnostic guardrail
- lifecycle `provider_runtime` provenance가 configured/effective provider, fallback, configured model,
  sanitized endpoint base URL, transport class를 run state, finding evidence, structured log,
  summary note에 일관되게 남기는 구조

반대로 아래 항목은 닫힌 기반으로 보면 안 된다. 리뷰 결과상 즉시 수정 또는 문서 보정이 남아 있다.

- Organization/private rule packaging
  - filesystem extension support는 있으나 package shape와 validation owner는 deferred readiness로 남아 있다.

## Post-Review Source

현재 `Now`의 실행 순서는 아래 review artifact를 따른다.

- [POST_REVIEW_IMMEDIATE_FIXES.md](/home/et16/work/review_system/docs/reviews/POST_REVIEW_IMMEDIATE_FIXES.md:1)
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)
- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)

이번 post-review handoff의 actionable 분포:

- `bug_fix`: 12 entries
- `roadmap_update`: 2 entries
- `remove`: 3 entries
- `deferred_update`: 0 entries
- `needs_decision`: 0 entries

이번 `ROADMAP.md` 정리에서 반영 완료한 내용:

- 닫힌 기반과 아직 열린 post-review guardrail work를 분리했다.
- post-review immediate fixes 문서를 현재 실행 순서의 source로 연결했다.
- private rule packaging은 deferred readiness owner가 있음을 `Prepare Deferred Work`에 노출했다.
- suggested next step을 evidence refresh에서 gate reliability로 바꿨다.

## Now

자동 실행 기준:

- 아래 `###` 항목 하나가 `advance_roadmap_with_codex.sh`의 한 iteration에서 고를 수 있는 최소 실행 단위다.
- 한 iteration에서 두 개 이상의 `###` 항목을 묶지 않는다.
- `active` 항목을 roadmap order대로 먼저 처리한다.
- `queued` 항목은 앞선 관련 `active` guardrail이 완료되거나 blocked로 기록된 뒤 처리한다.
- blocked이면 final output의 `BLOCKED_UNIT`에 아래 heading을 그대로 쓴다.

### 1. Make Review-Bot API Queue TestClient Gate Bounded And Diagnosable

상태: `watch`

왜 지금 하나:

- 현재 문서화된 deterministic gate 중 `review-bot` API queue TestClient path가
  bounded run에서 output 없이 timeout될 수 있다.
- 이 상태에서는 후속 `review-bot` contract fix가 회귀 신호를 받지 못하고 automation hang으로 끝날 수 있다.

이번 작업의 범위:

1. `review-bot` API queue TestClient-backed suite에 bounded timeout 또는 equivalent guardrail을 추가한다.
2. hang diagnostics를 남겨 startup/lifespan 문제와 실제 assertion failure를 구분한다.
3. parser/business-logic처럼 ASGI startup이 필요 없는 빠른 테스트는 계속 분리해 유지한다.

완료 기준:

- `cd review-bot && uv run pytest tests/test_api_queue.py -q`가 outer timeout 없이 끝난다.
- 실패 시에도 pytest 결과나 hang diagnostic이 남는다.

완료 기록:

- `review-bot` API queue suite는 deterministic ASGI test client와 per-test watchdog으로
  TestClient/threadpool hang diagnostic을 남긴다.
- 검증 통과:
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-api-queue-validation-4 uv run --no-sync pytest tests/test_api_queue.py -q`
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-runner-validation-3 uv run --no-sync pytest tests/test_review_runner.py -q`
  - `git diff --check`
- 기본 `uv run`은 sandbox의 read-only `/home/et16/.cache/uv` 때문에 실행 전 cache 초기화에서 실패해,
  같은 test command를 writable `UV_CACHE_DIR`와 existing environment `--no-sync`로 검증했다.
- local GitLab lifecycle smoke와 direct OpenAI smoke는 이 test guardrail 변경에 필요하지 않아 실행하지 않았다.

관련 backlog: `B-cross-cutting-01`

### 2. Make Review-Platform TestClient Gates Bounded And Diagnosable

상태: `watch`

왜 지금 하나:

- 현재 문서화된 deterministic gate 중 `review-platform` FastAPI/TestClient path가
  bounded run에서 output 없이 timeout될 수 있다.
- 이 상태에서는 harness bridge fix가 회귀 신호를 받지 못하고 automation hang으로 끝날 수 있다.

이번 작업의 범위:

1. `review-platform` FastAPI/TestClient-backed suite에 bounded timeout 또는 equivalent guardrail을 추가한다.
2. hang diagnostics를 남겨 startup/lifespan 문제와 실제 assertion failure를 구분한다.
3. ASGI startup이 필요 없는 harness unit test는 계속 분리해 유지한다.

완료 기준:

- `cd review-platform && uv run pytest tests/test_health.py tests/test_pr_flow.py -q`가 outer timeout 없이 끝난다.
- 실패 시에도 pytest 결과나 hang diagnostic이 남는다.

완료 기록:

- `review-platform` health/PR flow suite는 deterministic ASGI test client와 per-test
  watchdog으로 TestClient/threadpool hang diagnostic을 남긴다.
- 검증 통과:
  - `cd review-platform && UV_CACHE_DIR=/tmp/uv-cache-review-platform-testclient-validation uv run pytest tests/test_health.py tests/test_pr_flow.py -q`
- 첫 검증은 기존 blocking TestClient path에서 output 없이 `124`로 종료되어 hang path를 재현했다.
  이후 deterministic ASGI client로 같은 gate가 `4 passed`로 종료되는 것을 확인했다.
- local GitLab lifecycle smoke와 direct OpenAI smoke는 이 harness test guardrail 변경에 필요하지 않아 실행하지 않았다.

관련 backlog: `B-cross-cutting-01`

### 3. Fail Or Defer GitLab Note-Trigger When Expected Head Never Settles

상태: `watch`

왜 지금 하나:

- GitLab에서 force-push 직후 note trigger가 들어오면 webhook payload head가 stale일 수 있다.
- expected head가 끝까지 settle되지 않았는데 stale diff로 성공 처리하면 review 결과가 잘못된 head에 묶인다.

이번 작업의 범위:

1. GitLab note-trigger expected head가 끝까지 settle되지 않으면 stale diff로 성공 처리하지 않는다.
2. never-settled path를 retryable detect failure 또는 explicit pending/deferred state로 남긴다.
3. 모든 settle retry가 stale MR diff head를 관찰하는 deterministic runner test를 추가한다.

완료 기준:

- never-settled expected head runner test가 추가되고 통과한다.
- stale observed head가 successful detect result로 저장되지 않는다.

검증:

```bash
cd review-bot && uv run pytest tests/test_review_runner.py tests/test_api_queue.py -q
```

GitLab head handling을 바꾸므로 local GitLab 환경이 준비되어 있으면 lifecycle smoke도 실행한다.

완료 기록:

- GitLab note-trigger detect에서 expected head가 settle retry 이후에도 관찰되지 않으면
  stale diff로 detect를 계속하지 않고 retryable `expected_head_not_settled` 실패로 남긴다.
- never-settled runner regression test를 추가해 stale observed head가 successful detect result나
  finding evidence로 저장되지 않는지 검증했다.
- 검증 통과:
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-roadmap-3-validation uv run --no-sync pytest tests/test_review_runner.py tests/test_api_queue.py -q`
  - `git diff --check`
- 기본 `uv run`은 sandbox의 read-only `/home/et16/.cache/uv`를 피하기 위해 writable
  `UV_CACHE_DIR`와 existing environment `--no-sync`로 검증했다.
- local GitLab readiness probe `curl -fsS --max-time 2 http://127.0.0.1:18929/-/readiness`가
  connection refused로 끝나 lifecycle smoke는 실행하지 않았다.
- direct OpenAI smoke는 provider success claim이 아니므로 실행하지 않았다.

관련 backlog: `B-review-bot-01`

### 4. Scope Adapter Thread And Feedback Identity Explicitly

상태: `watch`

왜 지금 하나:

- adapter thread/feedback refs가 contract에서는 global unique인지 request-scoped인지 불명확하다.
- DB는 global unique처럼 저장하므로 서로 다른 review request가 같은 remote id를 재사용할 때 충돌할 수 있다.

이번 작업의 범위:

1. adapter thread/comment/event id의 uniqueness scope를 contract에 명시한다.
2. contract에 맞춰 DB uniqueness 또는 deduplication key를 조정한다.
3. 두 review request가 같은 remote thread/comment/event id를 재사용하는 deterministic test를 추가한다.

완료 기준:

- contract와 storage uniqueness가 같은 scope를 말한다.
- adapter identity reuse test가 통과한다.

검증:

```bash
cd review-bot && uv run pytest tests/test_review_runner.py tests/test_api_queue.py -q
```

완료 기록:

- adapter thread/comment/event refs는 해당 `ReviewRequestKey` 안에서만 unique한 request-scoped
  remote id로 계약화했다.
- `thread_sync_states`는 `(review_request_pk, adapter_thread_ref)`, `feedback_events`는
  `(review_request_pk, event_key)`로 dedupe하도록 storage uniqueness와 runner feedback ingest를
  맞췄다.
- request-scoped ref 재사용 시 analytics가 잘못 join하지 않도록 feedback/outcome metadata lookup도
  `(review_request_pk, adapter_thread_ref)` 기준으로 보정했다.
- Alembic head 추가: `20260424_000006`
- 검증 통과:
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-roadmap-4 uv run --no-sync pytest tests/test_review_runner.py tests/test_api_queue.py -q`
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-roadmap-4 uv run --no-sync alembic heads`
  - `python3 -m py_compile review-bot/alembic/versions/20260424_000006_scope_adapter_remote_refs.py`
  - `git diff --check`
- local GitLab lifecycle smoke는 live adapter runtime 변경 검증이 아니어서 실행하지 않았다.
- direct OpenAI smoke는 provider success claim이 아니고 preflight도 skipped configuration이어서 실행하지 않았다.

관련 backlog: `B-review-bot-02`

### 5. Add Model And Endpoint Provenance To Lifecycle Provider Runtime

상태: `watch`

왜 지금 하나:

- lifecycle run state는 configured/effective provider와 fallback 여부만 드러낸다.
- `BOT_OPENAI_BASE_URL`로 OpenAI-compatible local backend를 붙이면 default OpenAI와 local backend/model을 구분하기 어렵다.

이번 작업의 범위:

1. lifecycle `provider_runtime` metadata에 sanitized model, endpoint base URL, transport class를 추가한다.
2. run state API, finding evidence, structured logs, summary note에 같은 provenance를 반영한다.
3. default OpenAI, non-default local backend, stub, fallback case를 targeted tests로 덮는다.

완료 기준:

- provider runtime metadata가 run state, finding evidence, logs, summary note에 일관되게 보인다.
- OpenAI-compatible local backend와 default OpenAI가 artifact/API/log에서 구분된다.

검증:

```bash
cd review-bot && uv run pytest tests/test_provider_quality.py tests/test_prompting.py -q
cd review-bot && uv run pytest tests/test_review_runner.py -q
```

direct OpenAI smoke는 live provider success claim을 할 때만 실행한다.

완료 기록:

- lifecycle `provider_runtime`에 `configured_model`, sanitized `endpoint_base_url`,
  `transport_class`를 추가해 run state API, finding evidence, structured log, summary note가
  같은 provenance를 보이게 했다.
- default OpenAI, OpenAI-compatible local backend, deterministic stub, fallback case를
  targeted tests로 덮었다.
- 검증 통과:
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-roadmap-5 uv run --no-sync pytest tests/test_provider_quality.py tests/test_prompting.py -q`
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-roadmap-5-runner uv run --no-sync pytest tests/test_review_runner.py -q`
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-roadmap-5-api uv run --no-sync pytest tests/test_api_queue.py -q`
  - `git diff --check`
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh`
- validation은 deterministic fake OpenAI metadata와 stub fallback path를 사용했다.
  direct OpenAI smoke는 live provider success claim이 아니고 preflight도 skipped configuration이라 실행하지 않았다.

관련 backlog: `B-review-bot-03`

### 6. Post Visible Feedback For Directed Unknown Note Commands

상태: `watch`

왜 지금 하나:

- `@review-bot fullreport` 같은 directed unknown command는 detect enqueue 없이 안전하게 무시된다.
- 하지만 GitLab 사용자는 webhook `ignored_reason`을 볼 수 없어 실패 이유를 알 수 없다.

이번 작업의 범위:

1. line-start bot mention의 unknown command token에 대해 concise help/error note를 post/upsert한다.
2. no-enqueue behavior를 유지한다.
3. incidental mention은 계속 silent ignore로 둔다.

완료 기준:

- unknown directed command가 visible feedback과 no-enqueue를 동시에 만족한다.
- incidental mention silence가 유지된다.

검증:

```bash
cd review-bot && uv run pytest tests/test_api_queue.py tests/test_review_runner.py -q
```

완료 기록:

- line-start directed unknown command는 detect run을 만들거나 enqueue하지 않고
  same-purpose `unknown-command` general note로 supported command 안내를 남긴다.
- bot-authored note와 incidental mention은 기존처럼 silent ignore/no-enqueue 경로를 유지한다.
- webhook contract는 `action=unknown_command`, `ignored_reason=unknown_command:...`,
  same-purpose upsert 동작을 명시한다.
- 검증 통과:
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-roadmap-6 uv run --no-sync pytest tests/test_api_queue.py tests/test_review_runner.py -q`
  - `git diff --check`
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh`
- 기본 `uv run`은 sandbox의 read-only `/home/et16/.cache/uv`를 피하기 위해 writable
  `UV_CACHE_DIR`와 existing environment `--no-sync`로 검증했다.
- local GitLab lifecycle smoke와 direct OpenAI smoke는 command dispatch/control path 변경이고
  provider success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-review-bot-04`

### 7. Update Local Harness Bot Bridge To Key-Based Bot API

상태: `watch`

왜 지금 하나:

- `review-platform`은 product UI가 아니라 contract harness다.
- legacy `pr_id` bot endpoint를 계속 호출하면 current `review-bot` API drift를 검증하지 못한다.

이번 작업의 범위:

1. `review-platform` BotClient와 API handlers를 `ReviewRequestKey` 기반 API로 맞춘다.
2. key-based next-batch contract가 아직 없다면 unsupported harness control을 숨기거나 명확히 unsupported 처리한다.
3. drift 방지용 unmocked contract check를 남긴다.

완료 기준:

- local harness bot bridge가 removed `/internal/review/pr-updated`, `/internal/review/next-batch`,
  `/internal/review/state/{pr_id}` endpoint에 의존하지 않는다.
- stale bridge가 mock-only test로 가려지지 않는다.

검증:

```bash
cd review-platform && uv run pytest tests/test_pr_flow.py -q
```

완료 기록:

- `review-platform` BotClient가 removed legacy `pr_id` endpoint 대신
  `POST /internal/review/runs`와
  `GET /internal/review/requests/{review_system}/{project_ref}/{review_request_id}`를 사용한다.
- local harness key는 `review_system=local_platform`, `project_ref=<repository.name>`,
  `review_request_id=<pull_request.id>`로 구성한다.
- key-based next-batch bot API가 아직 없으므로 visible next-batch control은 숨기고,
  API/form route는 `501` unsupported로 명확히 실패하게 했다.
- drift 방지용 BotClient contract test가 실제 HTTP path/payload를 검증한다.
- 검증 통과:
  - `cd review-platform && UV_CACHE_DIR=/tmp/uv-cache-review-platform-roadmap-7 uv run pytest tests/test_health.py tests/test_pr_flow.py -q`
  - `git diff --check`
- local GitLab lifecycle smoke와 direct OpenAI smoke는 harness bridge contract 변경이고
  provider/runtime success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-review-platform-01`

### 8. Retain Blocked Review-Roadmap Unit Artifacts

상태: `watch`

왜 지금 하나:

- implementation roadmap wrapper는 blocked artifact를 retained file로 남긴다.
- review-roadmap wrapper는 blocked summary를 `/tmp` scratch에만 남겨 반복 blocker audit에 약하다.

이번 작업의 범위:

1. `advance_review_roadmap_with_codex.sh`가 blocked unit을 retained artifact로 남기게 한다.
2. blocker type, reason, validation summary, status를 normalize한다.
3. no-block case에서 artifact가 생기지 않는지 테스트한다.

완료 기준:

- review-roadmap blocked unit artifact가 `docs/baselines/roadmap_automation/`에 보존된다.
- repeated blocker audit이 `/tmp` 파일에 의존하지 않는다.

검증:

```bash
bash -n ops/scripts/advance_review_roadmap_with_codex.sh ops/scripts/advance_roadmap_with_codex.sh
```

완료 기록:

- `advance_review_roadmap_with_codex.sh`가 blocked review unit을 normalized pending entry로 만들고,
  exit/cleanup 또는 later completed iteration 전에 `docs/baselines/roadmap_automation/`의
  `blocked_roadmap_units_YYYY-MM-DD.md` retained artifact로 flush한다.
- artifact entry는 `blocked_unit`, `reason`, `blocker_type`, `validation_summary`, `status`를
  가능한 경우 normalized single-line field로 보존한다.
- hidden deterministic self-test가 blocked output normalization과 no-block flush가 artifact를 만들지
  않는 case를 검증한다.
- 검증 통과:
  - `bash -n ops/scripts/advance_review_roadmap_with_codex.sh ops/scripts/advance_roadmap_with_codex.sh`
  - `ops/scripts/advance_review_roadmap_with_codex.sh --self-test-blocked-artifacts`
- local GitLab lifecycle smoke와 direct OpenAI smoke는 roadmap automation wrapper의 retained
  artifact 처리 변경이고 provider/runtime success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-ops-01`

### 9. Bound OpenAI Direct Smoke Preflight Runtime

상태: `watch`

왜 지금 하나:

- roadmap automation can run direct provider smoke before iterations.
- direct smoke script currently has network calls that can stall the automation loop if they are not bounded.

이번 작업의 범위:

1. `smoke_openai_provider_direct.sh`의 `curl` 호출에 connect/overall timeout을 추가한다.
2. 필요하면 preflight 전체를 bounded wrapper로 감싼다.
3. timeout/stall fake-curl cases를 deterministic test에 추가한다.

완료 기준:

- direct smoke preflight가 network stall로 roadmap loop를 무기한 멈추지 않는다.
- timeout exit status가 preflight output에 남는다.

검증:

```bash
bash -n ops/scripts/advance_review_roadmap_with_codex.sh ops/scripts/advance_roadmap_with_codex.sh ops/scripts/smoke_openai_provider_direct.sh
cd review-bot && uv run pytest tests/test_openai_provider_direct_smoke.py -q
```

완료 기록:

- `smoke_openai_provider_direct.sh`가 모든 direct `curl` probe에 configurable
  connect/overall timeout을 적용한다.
- probe transport failure는 `<probe>_curl_exit=<status>`로 출력되어 timeout exit status가
  preflight output에 남는다.
- fake-curl tests가 timeout flag 전달, `/models` timeout, live `/responses` timeout을 검증한다.
- 검증 통과:
  - `bash -n ops/scripts/advance_review_roadmap_with_codex.sh ops/scripts/advance_roadmap_with_codex.sh ops/scripts/smoke_openai_provider_direct.sh`
  - `cd review-bot && UV_CACHE_DIR=/tmp/uv-cache-review-bot-roadmap-9 uv run --no-sync pytest tests/test_openai_provider_direct_smoke.py -q`
- direct OpenAI smoke는 preflight skipped configuration이어서 실행하지 않았고,
  validation은 deterministic fake-curl path만 사용했다. stub fallback은 이 direct-smoke unit에
  관여하지 않는다.

관련 backlog: `B-ops-02`

### 10. Fail Fast On Unresolved Or Duplicate Selected Packs

상태: `watch`

왜 지금 하나:

- profile-selected pack id가 없거나 duplicate `pack_id`가 있으면 runtime rule selection이 조용히 drift할 수 있다.

이번 작업의 범위:

1. missing `enabled_packs`/`shared_packs`와 duplicate selected pack을 fail-fast 처리한다.
2. explicit extension replacement contract가 없다면 silent override를 허용하지 않는다.
3. missing/duplicate pack loader tests를 추가한다.

완료 기준:

- duplicate/missing pack reference test가 추가되고 통과한다.
- loader가 unresolved selected pack을 조용히 건너뛰지 않는다.

검증:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
```

완료 기록:

- `review-engine` rule loader가 duplicate loaded `pack_id`를 발견하면 silent override를 하지 않고
  explicit extension replacement unsupported error로 fail-fast 한다.
- explicit `enabled_packs`/`shared_packs`가 없는 경우의 기존 default-enabled fallback은 유지하되,
  explicit profile selection이 unknown pack id를 가리키면 fail-fast 한다.
- duplicate pack id와 missing explicit profile pack reference regression test를 추가했다.
- 검증 통과:
  - `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache-review-engine-roadmap-10 uv run --no-sync pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`
  - `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache-review-engine-roadmap-10-source uv run --no-sync pytest tests/test_source_coverage_matrix.py -q`
  - `git diff --check`
- local GitLab lifecycle smoke와 direct OpenAI smoke는 rule loader guardrail 변경이고
  provider/runtime success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-review-engine-01`

### 11. Clarify Or Remove Default Profile Configuration

상태: `watch`

왜 지금 하나:

- `REVIEW_ENGINE_DEFAULT_PROFILE`은 config로 존재하지만 current review runtime profile selection에는 반영되지 않는다.
- operator-facing setting이 runtime behavior와 다르면 false confidence를 만든다.

이번 작업의 범위:

1. setting을 safe default profile selection에 연결할지 제거/rename할지 결정한다.
2. 결정에 맞춰 code/docs/tests를 정리한다.
3. targeted default-profile selection test를 추가한다.

완료 기준:

- default profile config의 의미가 runtime behavior나 docs에서 모호하지 않다.

검증:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_multilang_regressions.py -q
```

완료 기록:

- `REVIEW_ENGINE_DEFAULT_PROFILE`은 유지하되, `REVIEW_ENGINE_DEFAULT_LANGUAGE`로 선택된
  language에서만 fallback profile로 쓰이게 했다.
- 명시적 request `profile_id`와 path/content 기반 profile inference가 우선하며,
  runtime loader, language resolution, direct query analysis가 같은 fallback 의미를 사용한다.
- targeted regression은 `default_language_id=python`, `default_profile_id=fastapi_service`에서
  generic Python review가 FastAPI profile을 쓰고 Django inference는 계속 Django profile을 쓰는지 검증한다.
- 검증 통과:
  - `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache-review-engine-roadmap-11 uv run --no-sync pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py tests/test_source_coverage_matrix.py tests/test_multilang_regressions.py -q`
  - `git diff --check`
- 기본 `uv run`은 sandbox의 read-only `/home/et16/.cache/uv`를 피하기 위해 writable
  `UV_CACHE_DIR`와 existing environment `--no-sync`로 검증했다.
- local GitLab lifecycle smoke와 direct OpenAI smoke는 review-engine profile selection 변경이고
  provider/runtime success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-review-engine-02`

### 12. Add Reverse Coverage For Canonical Rules

상태: `watch`

왜 지금 하나:

- source coverage matrix는 source atom completeness를 검증하지만 모든 canonical rule이 source atom을 갖는지는 검증하지 않는다.
- 출처 atom이 없는 canonical rule이 누적될 수 있다.

이번 작업의 범위:

1. canonical rule reverse coverage validation을 추가한다.
2. 의도적으로 source atom이 없는 rule이 있으면 explicit allow-list와 reason을 둔다.
3. affected retrieval example tests를 필요한 만큼 갱신한다.

완료 기준:

- source coverage matrix가 atom completeness뿐 아니라 canonical rule reverse coverage도 검증한다.

검증:

```bash
cd review-engine && uv run pytest tests/test_source_coverage_matrix.py -q
```

완료 기록:

- source coverage matrix가 source atom completeness와 forward canonical rule references뿐 아니라
  모든 canonical pack rule의 reverse source-atom coverage도 검증한다.
- 기존 canonical rule 중 source atom에 연결되지 않았던 C++/Python/TypeScript/Java/Go/Bash/SQL
  detail rules를 기존 source atom에 맞춰 명시적으로 연결했다.
- 현재 committed canonical pack rule `350`개가 모두 coverage matrix의 non-excluded source atom에
  연결된다.
- 검증 통과:
  - `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache-review-engine-roadmap-12 uv run --no-sync pytest tests/test_source_coverage_matrix.py -q`
  - `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache-review-engine-roadmap-12-baseline uv run --no-sync pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`
  - `git diff --check`
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh`
- 기본 `uv run`은 sandbox의 read-only `/home/et16/.cache/uv`를 피하기 위해 writable
  `UV_CACHE_DIR`와 existing environment `--no-sync`로 검증했다.
- local GitLab lifecycle smoke와 direct OpenAI smoke는 source coverage matrix guardrail 변경이고
  provider/runtime success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-review-engine-03`

### 13. Reject Unknown Canonical YAML Authoring Keys

상태: `watch`

왜 지금 하나:

- canonical authoring model이 unknown key를 무시하면 `fix_guidence`, `enabled_packz` 같은 typo가 fail-fast 없이 사라진다.

이번 작업의 범위:

1. canonical rule/profile/policy/source manifest models가 unknown field를 reject하도록 한다.
2. clear validation error를 낸다.
3. typoed `RuleEntry`, `RulePackManifest`, `ProfileConfig`, `PriorityPolicy`, root manifest, source manifest tests를 추가한다.

완료 기준:

- typoed YAML key가 clear validation error를 낸다.

검증:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
```

완료 기록:

- canonical rule/profile/policy/source manifest authoring models가 unknown field를
  Pydantic validation error로 fail-fast 하도록 strict authoring base를 적용했다.
- typoed `RuleEntry`, `RulePackManifest`, `ProfileConfig`, `PriorityPolicy`,
  `RuleRootManifest`, `RuleSourceManifest` regression을 추가했다.
- committed `rule_sources/manifest.yaml`도 strict source manifest model로 검증하며,
  기존 source manifest contract의 `profile_id` field를 명시했다.
- 검증 통과:
  - `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache-review-engine-roadmap-13 uv run --no-sync pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q`
  - `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache-review-engine-roadmap-13-source uv run --no-sync pytest tests/test_source_coverage_matrix.py -q`
  - `git diff --check`
- 기본 `uv run`은 sandbox의 read-only `/home/et16/.cache/uv`를 피하기 위해 writable
  `UV_CACHE_DIR`와 existing environment `--no-sync`로 검증했다.
- local GitLab lifecycle smoke와 direct OpenAI smoke는 canonical YAML authoring validation
  변경이고 provider/runtime success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-review-engine-04`

### 14. Remove Or Relocate Unowned Next.js Scaffold Files

상태: `watch`

왜 지금 하나:

- cleanup은 필요하지만 behavior-changing bug fix와 같은 commit에 섞으면 review가 어려워진다.

이번 작업의 범위:

1. `review-engine/app/`가 accidental scaffold인지 fixture인지 확인한다.
2. accidental scaffold면 제거한다.
3. fixture라면 `examples/` 또는 `tests/fixtures/`로 옮기고 deterministic test에 연결한다.

완료 기준:

- `review-engine/app/`가 runtime/package/docs/test fixture boundary 안에 들어오거나 제거된다.

검증:

```bash
rg -n "review-engine/app|app/api/users/route\\.ts|app/dashboard/page\\.tsx" review-engine review-bot docs
cd review-engine && uv run pytest tests/test_language_registry.py tests/test_multilang_regressions.py tests/test_query_conversion.py -q
```

완료 기록:

- `review-engine/app/`는 packaged runtime, Docker image, docs, deterministic fixture boundary에
  연결되지 않은 accidental Next.js scaffold로 확인해 제거했다.
- existing Next.js profile/language tests와 retrieval examples는 physical scaffold file이 아니라
  logical review path를 사용하므로 그대로 유지했다.
- 검증 통과:
  - `rg -n "review-engine/app|app/api/users/route\\.ts|app/dashboard/page\\.tsx" review-engine review-bot docs`
  - `cd review-engine && UV_CACHE_DIR=/tmp/uv-cache-review-engine-roadmap-14 uv run --no-sync pytest tests/test_language_registry.py tests/test_multilang_regressions.py tests/test_query_conversion.py -q`
- `rg` 결과는 historical review docs와 logical test/example review paths만 남았고,
  physical `review-engine/app/...` files는 final diff의 deletion entry로만 남는다.
- 기본 `uv run`은 sandbox의 read-only `/home/et16/.cache/uv`를 피하기 위해 writable
  `UV_CACHE_DIR`와 existing environment `--no-sync`로 검증했다.
- local GitLab lifecycle smoke와 direct OpenAI smoke는 unowned scaffold cleanup이고
  provider/runtime success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-review-engine-05`

### 15. Remove Or Merge Orphan Root Workspace Note

상태: `watch`

왜 지금 하나:

- root `review_system.md` duplicates canonical workspace/docs notes and has no referenced owner.

이번 작업의 범위:

1. `review_system.md`가 외부 workflow에 쓰이지 않는지 확인한다.
2. 필요한 내용이 있으면 canonical docs로 병합한다.
3. 남은 root orphan doc을 제거한다.

완료 기준:

- `review_system.md`가 canonical docs index 밖에서 중복되지 않는다.

검증:

```bash
rg -n "review_system\\.md" . -g '!ops/gitlab/**'
git diff --check
```

완료 기록:

- root `review_system.md`는 canonical docs/code/ops/agent workflow에서 참조되지 않고,
  durable content가 `README.md`, `docs/README.md`, `docs/CURRENT_SYSTEM.md`,
  `docs/OPERATIONS_RUNBOOK.md`에 이미 소유된 중복 workspace note임을 확인해 제거했다.
- 검증 통과:
  - `rg -n "review_system\\.md" . -g '!ops/gitlab/**'`
  - `git diff --check`
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh`
- `rg` 결과는 roadmap/review history와 이번 완료 기록만 남았고, canonical docs, code,
  ops scripts, AGENTS guidance에는 root note dependency가 없다.
- local GitLab lifecycle smoke와 direct OpenAI smoke는 orphan docs cleanup이고
  provider/runtime success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-docs-03`

### 16. Rename Local GitLab Smoke Internals Away From TDE As Primary Surface

상태: `watch`

왜 지금 하나:

- lifecycle wrapper exists, but docs and lower-level script names still expose `tde` as if it were the primary surface.

이번 작업의 범위:

1. lifecycle-named create/bootstrap/replay entrypoints를 추가한다.
2. docs/runbook/ops README가 lifecycle-named commands를 primary로 보여 주게 한다.
3. `tde` names는 compatibility wrapper 또는 backing fixture name으로만 남긴다.

완료 기준:

- docs/runbook/ops README가 lifecycle-named GitLab smoke entrypoint를 primary로 보여 준다.

검증:

```bash
bash -n ops/scripts/create_gitlab_lifecycle_review.sh ops/scripts/create_gitlab_tde_review.sh ops/scripts/smoke_local_gitlab_lifecycle_review.sh ops/scripts/smoke_local_gitlab_tde_review.sh
python3 -m py_compile ops/scripts/create_gitlab_merge_request.py ops/scripts/bootstrap_local_gitlab_lifecycle_review.py ops/scripts/bootstrap_local_gitlab_tde_review.py ops/scripts/replay_local_gitlab_lifecycle_review.py ops/scripts/replay_local_gitlab_tde_review.py
```

완료 기록:

- lifecycle-named create/bootstrap/replay entrypoints를 추가했다:
  `create_gitlab_lifecycle_review.sh`, `bootstrap_local_gitlab_lifecycle_review.py`,
  `replay_local_gitlab_lifecycle_review.py`.
- `smoke_local_gitlab_lifecycle_review.sh`는 lifecycle replay entrypoint를 직접 호출하고,
  기존 TDE-named scripts는 compatibility 또는 backing fixture 이름으로만 남긴다.
- local GitLab smoke MR title/description과 ops README/runbook/agent 운영 메모의 primary command가
  lifecycle smoke surface를 가리키도록 정리했다. backing fixture branch name
  `tde_first -> tde_base`는 local GitLab state를 넓게 건드리지 않기 위해 유지했다.
- 검증 통과:
  - `bash -n ops/scripts/create_gitlab_lifecycle_review.sh ops/scripts/create_gitlab_tde_review.sh ops/scripts/smoke_local_gitlab_lifecycle_review.sh ops/scripts/smoke_local_gitlab_tde_review.sh`
  - `python3 -m py_compile ops/scripts/create_gitlab_merge_request.py ops/scripts/bootstrap_local_gitlab_lifecycle_review.py ops/scripts/bootstrap_local_gitlab_tde_review.py ops/scripts/replay_local_gitlab_lifecycle_review.py ops/scripts/replay_local_gitlab_tde_review.py`
  - `git diff --check`
- local GitLab lifecycle smoke는 entrypoint/docs cleanup이고 live GitLab state가 필요하지 않아 실행하지 않았다.
- direct OpenAI smoke는 provider success claim이 아니어서 실행하지 않았다.

관련 backlog: `B-ops-03`

## Queued Product Contract Work

아래 항목은 여전히 가치가 있지만 post-review immediate fixes 뒤에 실행한다.

### 17. Evidence Refresh Path For Targeted Rule Expansion

상태: `watch`

이번 작업의 범위:

1. 다음 rule 후보를 고를 때 어떤 근거를 우선하는지 순서를 고정한다.
   - repo-local retained artifact
   - local analytics endpoint
   - local smoke artifact
2. endpoint가 비어 있거나 local GitLab이 꺼져 있어도 blocker가 같은 형식으로 남게 한다.
3. fresh evidence가 없을 때 임의로 다음 rule family를 고르지 않도록 freshness 기준과 artifact 위치를 고정한다.

완료 기록:

- targeted rule expansion 후보를 고르기 전 evidence order를
  repo-local retained artifact -> local analytics endpoint -> retained local smoke artifact로 고정했다.
- retained artifact 위치와 filename은
  `docs/baselines/review_bot/targeted_rule_expansion_evidence_YYYY-MM-DD.md`로 정했다.
- automation 기본 freshness는 같은 UTC 날짜 artifact이고, 사람이 명시한 artifact는 현재 branch와
  validation baseline에 맞을 때 최대 7 UTC일까지 재사용할 수 있게 문서화했다.
- endpoint가 비어 있거나 local GitLab state 때문에 smoke refresh가 불가능하면 임의 rule family를
  고르지 않고 standard blocked output을 남기도록 runbook/baseline contract를 보강했다.
- 검증 통과:
  - `git diff --check`
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh`
- local GitLab lifecycle smoke와 direct OpenAI smoke는 문서/계약 변경이고 provider/runtime success
  claim이 아니어서 실행하지 않았다.

### 18. `.review-bot.yaml` Contract Definition

상태: `watch`

이번 작업의 범위:

1. `.review-bot.yaml`이 다루는 최소 surface를 정의한다.
2. env, repo config, note command precedence 표를 고정한다.
3. 허용하지 않을 값과 fail-fast / ignore / warn 경계를 정한다.
4. `summarize`, `walkthrough`, `backlog`, `full-report`와의 관계를 note-first UX 기준으로 적는다.

완료 기록:

- `.review-bot.yaml` v1 repository config contract를
  [API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:718)에 정의했다.
- v1 최소 surface는 `version`, `review.enabled`, `review.paths.include/exclude`,
  `publish.batch_size`, `publish.rule_family_cap`, `publish.file_comment_cap`,
  `publish.minimum_publish_score`로 제한했다.
- config는 MR source head가 아니라 target/base revision에서 읽는 계약으로 고정했고,
  env/orchestrator setting은 security/identity/provider/adapter source of truth와 publish hard cap으로
  유지했다.
- note command가 per-invocation action selector이며 `review`만 detect/publish lifecycle을 만들고,
  `summarize`, `walkthrough`, `backlog`, `full-report`는 note-first read path,
  `help`는 supported command 안내 note로 남는다고 명시했다.
- malformed YAML, unknown key, unsupported version, forbidden secret/provider/identity key,
  env hard cap보다 완화적인 repo value는 fail-fast config error로 정했다. 파일 없음은 ignore,
  target/base file fetch 미지원은 warn/default, reviewable file 없음은 no-op success로 정했다.
- [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:181)는 contract definition과
  아직 없는 runtime loader를 분리해 설명한다.
- 검증 통과:
  - `git diff --check`
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh`
- local GitLab lifecycle smoke와 direct OpenAI smoke는 문서/계약 변경이고 provider/runtime success
  claim이 아니어서 실행하지 않았다. OpenAI direct smoke preflight는 configuration에 의해 skipped였다.

### 19. `ask` Command Boundary Definition

상태: `watch`

이번 작업의 범위:

1. `ask`가 참조할 수 있는 context source 범위를 정한다.
2. session 저장 여부와 최소 저장 경계를 정한다.
3. provider unavailable / timeout / empty evidence 응답 정책을 정한다.
4. `summarize` / `walkthrough` 이후 note-family command로서의 UX 목적을 정리한다.

완료 기록:

- future `ask` note command boundary를
  [API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:669)에 정의했다.
- 현재 live `review-bot`은 아직 `ask`를 지원 명령으로 파싱하지 않고 directed unknown command로
  처리한다는 점을 유지했다.
- v1 `ask`는 `ReviewRequestKey` 안의 최신 run/full-report/backlog/finding/thread/feedback state와
  adapter-supported file snippets, same-project review-engine similar-code evidence만 참조하는
  note-family read path로 제한했다.
- provider chat session은 저장하지 않고, durable record는 existing webhook/general-note/log/provenance
  diagnostic으로 제한했다.
- provider unavailable, timeout, empty evidence는 detect/publish enqueue 없이 same-purpose visible note
  reason으로 응답하는 정책으로 고정했다.
- `summarize`/`walkthrough` 이후 좁은 Q&A 목적이며 inline finding 생성이나 backlog disposition 변경은
  기존 feedback command와 분리된다고 명시했다.
- [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:185)는 future boundary와
  아직 없는 runtime command를 분리해 설명한다.
- 검증 통과:
  - `git diff --check`
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh`
- local GitLab lifecycle smoke와 direct OpenAI smoke는 문서/계약 변경이고 provider/runtime success
  claim이 아니어서 실행하지 않았다. OpenAI direct smoke preflight는 configuration에 의해 skipped였다.

### 20. Local Backend Retained Artifact Capture Prep

상태: `watch`

이번 작업의 범위:

1. local backend 실험에 필요한 env contract를 정리한다.
2. direct smoke, provider-quality, comparison artifact의 retained filename 규칙을 고정한다.
3. “capture 성공”과 “human review required”를 구분하는 기준을 적는다.
4. local backend artifact가 direct OpenAI artifact와 섞이지 않도록 provenance 표현을 고정한다.

완료 기록:

- OpenAI-compatible local backend capture env contract를
  [OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:93)에
  고정했다.
- direct smoke, provider-quality, comparison retained filename은 default OpenAI와
  `openai_compatible_local` suffix를 쓰는 local backend artifact로 분리했다.
- direct provider success artifact 기준은 `--expect-live-openai`, exit `0`,
  `models_probe_status=ok`, `live_probe_model=...`으로 고정했고,
  provider quality `status=passed`와 provenance match를 capture success 기준으로 적었다.
- comparison `human_review_required=true`, skipped/failure/provenance mismatch/missing JSON은
  tuning evidence가 아니라 decision artifact 또는 `defer`로 처리한다고 문서화했다.
- [docs/baselines/review_bot/README.md](/home/et16/work/review_system/docs/baselines/review_bot/README.md:1)는
  retained filename 목록과 local backend capture checklist를 포함한다.
- 검증 통과:
  - `git diff --check`
  - `bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh`
- local GitLab lifecycle smoke와 direct OpenAI smoke는 문서/계약 prep이고 live provider success
  claim이 아니어서 실행하지 않았다. OpenAI direct smoke preflight는 configuration에 의해 skipped였다.

## Prepare Deferred Work

아래 항목은 아직 deferred 자체를 시작하지 않고,
나중에 바로 착수할 수 있게 선행 조건만 먼저 닫는 작업이다.

### 21. Provider / Ranking / Density Tuning Readiness Packet

상태: `queued`

연결 문서:

- [Deferred Provider And Model Work](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)

지금 할 사전 작업:

1. direct OpenAI smoke 성공 판정 조건을 다시 한 줄로 고정한다.
2. comparison artifact human review 체크리스트를 준비한다.
3. quota/billing 정상 환경이 준비되면 어떤 순서로 재수집할지 실행 절차를 짧게 만든다.

이 사전 작업이 끝나면:

- OpenAI direct artifact 재수집과 ranking/density tuning을 바로 시작할 수 있다.

### 22. Manual Rule Editor Readiness Packet

상태: `queued`

연결 문서:

- [Deferred Rule Authoring And Editor Work](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:1)

지금 할 사전 작업:

1. lifecycle CLI가 이미 다루는 write boundary와 editor가 다뤄야 할 새 surface를 분리한다.
2. authoring에서 자주 틀리는 metadata/validation failure를 수집해 editor scope 후보를 정리한다.
3. editor가 canonical YAML과 Git history를 절대 우회하지 않는 운영 원칙을 한 번 더 고정한다.

이 사전 작업이 끝나면:

- manual rule editor를 UI/preview/validate 단위로 잘라 시작할 수 있다.

### 23. Private Rule Packaging Readiness Packet

상태: `queued`

연결 문서:

- [Deferred Rule Authoring And Editor Work](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:33)

지금 할 사전 작업:

1. private package manifest가 포함해야 할 id/version/compatibility metadata를 정한다.
2. private generated artifact와 repo canonical artifact의 분리 위치와 naming rule을 정한다.
3. install/update/rollback 절차와 validation gate를 정한다.

이 사전 작업이 끝나면:

- private/organization rule packaging을 implementation-ready slice로 나눌 수 있다.

### 24. Multi-SCM Expansion Readiness Packet

상태: `queued`

연결 문서:

- [Deferred Platform Expansion](/home/et16/work/review_system/docs/deferred/platform_expansion.md:1)

지금 할 사전 작업:

1. GitHub adapter가 GitLab adapter와 달라지는 schema / note / thread / status 차이를 표로 정리한다.
2. smoke 또는 replay fixture에 필요한 repository / token / permission 요구사항을 적는다.
3. `ReviewSystemAdapterV2`에서 adapter별 extension point를 어디까지 허용할지 먼저 정한다.

이 사전 작업이 끝나면:

- GitHub PR adapter 설계를 큰 재조사 없이 시작할 수 있다.

### 25. Auto-Fix Safety Packet

상태: `queued`

연결 문서:

- [Deferred Automation Work](/home/et16/work/review_system/docs/deferred/automation_work.md:1)

지금 할 사전 작업:

1. low-risk fix class 후보를 좁히는 기준을 적는다.
2. reviewer approval, audit log, rollback 경계를 한 문서에서 정리한다.
3. `auto_fix_lines`를 실제 patch application flow와 연결할지 판단 기준을 만든다.

이 사전 작업이 끝나면:

- `@review-bot apply`를 설계만 길게 하지 않고 safety-first slice로 시작할 수 있다.

## Watch

아래 영역은 현재 roadmap의 직접 구현 대상이 아니다.

- Existing Git review surface 중심 제품 방향
- Canonical `ReviewRequestKey` identity
- Runner-owned lifecycle boundary
- Event-backed lifecycle analytics direction
- Minimal rule lifecycle CLI surface
- Current six-command note UX
- Local GitLab smoke와 direct provider smoke를 별도 evidence로 보는 운영 원칙

변경이 생기면 여기서 다시 `active`로 올린다.

## Suggested Next Step

현재 가장 자연스러운 다음 작업은 `21. Provider / Ranking / Density Tuning Readiness Packet`이다.

이유:

- review-bot API queue gate reliability는 닫혔다.
- review-platform API client gate reliability도 닫혔다.
- GitLab note-trigger stale head handling의 correctness guardrail은 닫혔다.
- adapter thread/feedback identity scope는 contract와 storage에서 맞춰졌다.
- provider runtime provenance는 lifecycle API/log/summary note에서 model/endpoint/transport까지 드러낸다.
- directed unknown note command는 visible feedback을 남기고 no-enqueue 경로를 유지한다.
- local harness bot bridge는 key-based bot API를 사용하고 legacy `pr_id` endpoint에 의존하지 않는다.
- review-roadmap blocked unit artifact는 retained baseline으로 남는다.
- OpenAI direct smoke preflight는 bounded curl timeout과 timeout exit diagnostic을 남긴다.
- review-engine selected pack resolution은 duplicate loaded pack id와 unknown explicit
  `enabled_packs`/`shared_packs` reference를 fail-fast로 처리한다.
- review-engine default profile configuration은 default language fallback으로 runtime selection에 반영되고,
  explicit profile과 path/content inference가 우선한다.
- canonical rule reverse coverage는 source coverage matrix에서 모든 canonical pack rule이
  source atom에 연결되는지 검증한다.
- canonical YAML authoring typo는 Pydantic validation error로 fail-fast 한다.
- unowned `review-engine/app/` scaffold 파일은 제거되어 engine runtime/package/fixture boundary
  밖의 tracked Next.js app-looking 파일이 남지 않는다.
- root `review_system.md` orphan workspace note는 canonical docs/code/ops dependency 없이
  중복된 내용만 담고 있어 제거됐다.
- local GitLab smoke internals는 lifecycle-named entrypoint를 primary로 노출하고,
  `tde` 이름은 compatibility/backing fixture surface로 낮췄다.
- targeted rule expansion evidence refresh path는 retained artifact, local analytics endpoint,
  local smoke artifact 순서와 freshness/blocker 기준을 고정했다.
- `.review-bot.yaml` v1 contract는 최소 repo config surface, env/repo/note command precedence,
  fail-fast/ignore/warn 경계, note-first report command 관계를 고정했다.
- future `ask` note command boundary는 context source, session/retention, unavailable/timeout/empty
  evidence response, summarize/walkthrough 이후 UX 목적을 고정했다.
- local backend capture prep은 default OpenAI와 OpenAI-compatible local backend artifact가 섞이지
  않도록 env/provenance/retained filename 기준과 capture success/human-review/defer 판정을 고정했다.
- 다음 queued readiness work는 provider/ranking/density tuning을 시작하기 전 direct smoke 성공 조건과
  human comparison checklist, quota 정상 환경에서의 재수집 순서를 정리하는 작업이다.

## Validation Baseline

문서/계약 작업:

```bash
git diff --check
bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh
```

`review-bot` contract 변경:

```bash
cd review-bot && uv run pytest tests/test_review_runner.py -q
cd review-bot && uv run pytest tests/test_api_queue.py -q
```

`review-engine` rule / lifecycle contract 변경:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
cd review-engine && uv run pytest tests/test_source_coverage_matrix.py -q
```

`review-platform` harness 변경:

```bash
cd review-platform && uv run pytest tests/test_health.py tests/test_pr_flow.py -q
```

local smoke와 direct provider validation은 해당 작업이 실제 runtime/adapter/provider 경로를 건드릴 때만 추가한다.
