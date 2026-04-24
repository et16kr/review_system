# Roadmap

## Purpose

이 문서는 지금 바로 실행할 수 있는 작업만 관리한다.
이미 끝난 기반 설명은 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
완료된 roadmap 이력은 git history와 [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에 둔다.
외부 계정, live provider quota, 사람 승인, 별도 repository 권한이 필요한 작업은 실행 조건이 준비될 때까지
`docs/deferred/*.md`에 남긴다.

마지막 코드 상태 점검일: `2026-04-24`

상태 표기:

- `active`: 지금 바로 commit 단위로 진행할 수 있다.
- `queued`: 앞선 `active` 항목이 끝나면 바로 착수할 다음 후보다.
- `watch`: 구현보다 회귀 방지와 운영 관찰이 중심이다.

운영 원칙:

- 한 roadmap unit은 가능하면 한 commit에서 닫는다.
- 아래 `###` 항목 하나가 `advance_roadmap_with_codex.sh`의 한 iteration에서 고를 수 있는 최소 실행 단위다.
- 한 iteration에서 두 개 이상의 `###` 항목을 묶지 않는다.
- `active` 항목을 roadmap order대로 먼저 처리한다.
- `queued` 항목은 앞선 관련 `active` 항목이 완료되거나 blocked로 기록된 뒤 처리한다.
- blocked이면 final output의 `BLOCKED_UNIT`에 아래 heading을 그대로 쓴다.

## Current Snapshot

`2026-04-24` `gpt-5.5` 리뷰 라운드 이후 post-review immediate fixes, cleanup,
contract readiness packet은 닫혔다. OpenAI direct smoke는 live provider로 통과했고,
`reference_only` 규칙도 `provider.verify_draft` 직접 호출에서는 LLM이 적용/비적용 대조
케이스를 구분하는 신호가 확인됐다.

현재 roadmap에는 완료 항목을 반복 노출하지 않고, 외부 조건 없이 시작 가능한 slice가
생길 때만 `Now`에 올린다. 사람의 품질 판단이나 정책 승인이 필요한 작업은 내일
결정 대상으로 미룬다.

완료된 작업은 이 문서에 반복해서 남기지 않는다. 완료 이력은 git history,
[CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1),
[CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1),
그리고 관련 baseline artifact를 기준으로 확인한다.

현재 즉시 실행 가능한 방향:

- 외부 서비스 없이 deterministic 검증으로 닫을 수 있는 rule coverage breadth pass를 진행한다.
- `coverage_matrix.yaml` 기준 pending source atom은 없지만, rule 수가 얇거나 detector-backed
  direct pattern을 더 만들 수 있는 언어를 순차적으로 보강한다.

현재 바로 실행하지 않는 방향:

- `reference_only` LLM applicability smoke packaging: OpenAI direct smoke가
  `api.openai.com` DNS 해석 실패로 막혀 있어 지금 자동 진행할 수 없다.
- provider/ranking/density tuning: OpenAI direct smoke와 comparison artifact는 생겼지만,
  comparison이 `failed` / `human_review_required=true`이고 triage packet도 review input일 뿐이므로
  사람의 품질 판단이 필요하다.
- `reference_only` 자동 게시 또는 자동 승격 정책: LLM 검증 신호는 생겼지만, 어떤 규칙을
  어디까지 자동화할지 product/risk decision이 필요하다.
- GitHub/Multi-SCM adapter: test repository, token/permissions, webhook 또는 replay fixture가 필요하다.
- auto-fix/apply: trust metric, low-risk fix class, reviewer approval, audit, rollback evidence가 필요하다.

## Now

### Expand Go Review Rule Coverage

Status: `active`

목표:

- Go는 현재 단일 pack 중심이고 rule 수가 얇으므로, detector-backed auto-review 규칙을 먼저 보강한다.
- HTTP client timeout, response body handling, strict JSON decoding, goroutine/error ownership처럼
  changed snippet에서 직접 확인 가능한 패턴을 우선한다.

범위:

- `review-engine/rule_sources/go/`에 보강 source를 추가하거나 기존 source를 갱신한다.
- `review-engine/rules/go/packs/project_go.yaml`에 2~3개 narrow auto-review rule을 추가한다.
- `review-engine/review_engine/query/languages/go.py`에 대응 pattern과 hinted rule을 추가한다.
- `review-engine/rule_sources/coverage_matrix.yaml`을 새 source atom 기준으로 갱신한다.
- broad design guidance나 whole-program 판단은 `reference_only`로 두고 auto-review로 올리지 않는다.

검증:

```bash
cd review-engine && uv run pytest tests/test_query_conversion.py tests/test_rule_runtime.py tests/test_source_coverage_matrix.py -q
git diff --check
```

완료 기준:

- 새 Go rule이 source coverage matrix에 mapped 또는 reference_only로 연결된다.
- 새 direct pattern이 최소 하나의 deterministic query/conversion test로 재현된다.

### Expand Bash And Dockerfile Automation Safety Rules

Status: `queued`

목표:

- checked-in automation과 container build surface에서 아직 얇은 안전 규칙을 보강한다.
- Bash는 temporary file/trap/lock cleanup, glob/path validation, command argv shaping을 우선한다.
- Dockerfile은 package pinning, BuildKit secret mount, runtime surface minimization을 우선한다.

범위:

- Bash와 Dockerfile source/rule/query pattern을 각각 작고 직접 검출 가능한 패턴으로 확장한다.
- CI/YAML remote execution 규칙과 중복되는 경우에는 shared source 또는 cross-language rationale만
  맞추고 같은 defect를 중복 게시하지 않게 rule text를 조정한다.

검증:

```bash
cd review-engine && uv run pytest tests/test_query_conversion.py tests/test_rule_runtime.py tests/test_source_coverage_matrix.py -q
git diff --check
```

완료 기준:

- Bash와 Dockerfile에서 각각 최소 하나 이상의 새 detector-backed rule 또는 source-backed
  reference rule이 추가된다.

### Expand Rust Async And Boundary Rules

Status: `queued`

목표:

- Rust/Tokio 규칙을 async cancellation, FFI/unsafe boundary, serialization/trust boundary 중심으로 보강한다.
- panic/unwrap 계열과 중복되지 않는 changed-snippet direct signal만 auto-review로 둔다.

범위:

- `review-engine/rule_sources/rust/`, `review-engine/rules/rust/`,
  `review_engine/query/languages/rust.py`를 함께 갱신한다.
- direct signal이 약한 API design guidance는 `reference_only`로 유지한다.

검증:

```bash
cd review-engine && uv run pytest tests/test_query_conversion.py tests/test_rule_runtime.py tests/test_source_coverage_matrix.py -q
git diff --check
```

완료 기준:

- Rust 또는 Tokio pack에 source-backed rule 보강이 들어가고, query pattern test가 추가된다.

### Expand C, JavaScript, And Java Service Boundary Rules

Status: `queued`

목표:

- C, JavaScript, Java의 service/API boundary 규칙을 얇은 direct-signal 중심으로 보강한다.
- C는 size/null/errno contracts, JavaScript는 Express/Node request boundary, Java는 Spring/Jackson
  request validation과 resource ownership 후보를 우선한다.

범위:

- 한 iteration에서 한 언어만 구현해도 된다. 여러 언어를 동시에 묶지 말고 가장 작은
  detector-backed slice부터 처리한다.
- source coverage, canonical YAML rule, query pattern, deterministic test를 함께 갱신한다.

검증:

```bash
cd review-engine && uv run pytest tests/test_query_conversion.py tests/test_rule_runtime.py tests/test_source_coverage_matrix.py -q
git diff --check
```

완료 기준:

- 선택한 언어에 최소 하나 이상의 새 source-backed rule과 direct pattern regression이 생긴다.
- 남은 언어는 `ROADMAP.md`에 계속 queued 상태로 유지한다.

### Expand Targeted YAML, SQL, And Python Rule Gaps

Status: `queued`

목표:

- provider quality artifact에 등장한 YAML, SQL, Python/FastAPI 영역을 rule gap 관점에서도 점검한다.
- 단, 현재 artifact의 주된 신호는 OpenAI draft length/required term 문제이므로 prompt tuning과
  rule 보강을 섞지 않는다.

범위:

- existing source corpus에서 직접 detector-backed rule로 승격할 수 있는 gap만 추가한다.
- FastAPI, SQL, CI YAML의 existing rule expectation 또는 required-term gate를 바꾸는 작업은
  human provider review decision 없이는 하지 않는다.

검증:

```bash
cd review-engine && uv run pytest tests/test_query_conversion.py tests/test_rule_runtime.py tests/test_source_coverage_matrix.py -q
git diff --check
```

완료 기준:

- 실제 rule gap이 있으면 source-backed rule과 test가 추가된다.
- rule gap이 없으면 retained note나 roadmap update로 `no_rule_gap_without_human_provider_decision`을 남긴다.

## Deferred But Not Yet Executable

아래 항목은 readiness packet은 있지만, 현재 automation이 바로 구현하면 조건을 채울 수 없다.
조건이 준비되면 이 문서의 `Now`에 새 `active` unit으로 올린다.

- Provider / ranking / density tuning
  - 현재 상태: OpenAI direct smoke는 성공했고 provider quality/comparison artifact도 생겼지만,
    comparison이 `failed` / `human_review_required=true`다. 2026-04-24 triage packet은
    review input이며 tuning approval이 아니다.
  - 필요 조건: human comparison decision artifact
  - owner: [provider_and_model_work.md](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)
- Reference-only LLM applicability smoke packaging
  - 현재 상태: `CPP.REF.4` 직접 verifier 대조 테스트에서는 OpenAI가 적용/비적용을 구분했지만,
    재실행 가능한 smoke script 작업은 `api.openai.com` DNS 해석 실패로 blocked 됐다.
  - 필요 조건: `bash ops/scripts/smoke_openai_provider_direct.sh --expect-live-openai` 성공
  - 준비되면 `Now`에 `Package reference-only LLM applicability smoke` unit으로 다시 올린다.
  - owner: [provider_and_model_work.md](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)
- Reference-only auto-review promotion
  - 현재 상태: `CPP.REF.4` 직접 verifier 대조 테스트에서는 OpenAI가 적용/비적용을 구분했다.
  - 필요 조건: 어떤 `reference_only` rule을 backlog/report/publish 중 어디까지 승격할지에 대한
    human product/risk decision
  - owner: [provider_and_model_work.md](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)
- GitHub / Multi-SCM adapter expansion
  - 필요 조건: GitHub test repository, GitHub App 또는 token permissions, webhook/replay fixture,
    live smoke artifact policy
  - owner: [platform_expansion.md](/home/et16/work/review_system/docs/deferred/platform_expansion.md:1)
- Auto-fix / apply automation
  - 필요 조건: trust metric baseline, low-risk fix class evidence, reviewer approval/audit/rollback validation
  - owner: [automation_work.md](/home/et16/work/review_system/docs/deferred/automation_work.md:1)

## Watch

아래 영역은 현재 roadmap의 직접 구현 대상이 아니다.

- Existing Git review surface 중심 제품 방향
- Canonical `ReviewRequestKey` identity
- Runner-owned lifecycle boundary
- Event-backed lifecycle analytics direction
- Current six-command note UX
- Local GitLab smoke와 direct provider smoke를 별도 evidence로 보는 운영 원칙

변경이 생기면 여기서 다시 `active`로 올린다.

## Validation Baseline

문서/계약 작업:

```bash
git diff --check
bash -n ops/scripts/advance_roadmap_with_codex.sh ops/scripts/advance_review_roadmap_with_codex.sh
```

`review-engine` rule / package / lifecycle contract 변경:

```bash
cd review-engine && uv run pytest tests/test_rule_runtime.py tests/test_rule_lifecycle_cli.py -q
cd review-engine && uv run pytest tests/test_rule_runtime_private_extension.py tests/test_source_coverage_matrix.py -q
```

`review-bot` contract 변경:

```bash
cd review-bot && uv run pytest tests/test_review_runner.py -q
cd review-bot && uv run pytest tests/test_api_queue.py -q
```

`review-platform` harness 변경:

```bash
cd review-platform && uv run pytest tests/test_health.py tests/test_pr_flow.py -q
```

local smoke와 direct provider validation은 해당 작업이 실제 runtime/adapter/provider 경로를 건드릴 때만 추가한다.
