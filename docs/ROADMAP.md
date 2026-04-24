# Roadmap

## Purpose

이 문서는 지금 바로 실행할 수 있는 작업만 관리한다.
이미 끝난 기반 설명은 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
완료된 roadmap 이력은 git history와 [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에 둔다.
외부 계정, live provider quota, 사람 승인, 별도 repository 권한이 필요한 작업은 실행 조건이 준비될 때까지
`docs/deferred/*.md`에 남긴다.

마지막 코드 상태 점검일: `2026-04-25`

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

- 없음. 새 source-backed deterministic slice가 식별되면 `Now`에 올린다.
- CUDA official documentation gap check는 `CUDA.ASYNC.4` pinned-memory async transfer rule로
  닫혔다.
- dbt/CI YAML/OpenAPI schema official source gap check는 `SQL.DBT.3` side-effecting
  `run_query` command-scope rule로 닫혔다. CI YAML과 OpenAPI schema 쪽은 이번 pass에서
  추가 detector-backed direct pattern gap이 없어 `no_yaml_sql_rule_gap_from_official_sources`로
  retained 한다.
- `coverage_matrix.yaml` 기준 pending source atom은 없다.

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

현재 `active` unit은 없다.

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
- Source provenance hardening for additional rule expansion
  - 현재 상태: C POSIX safety, Java runtime baseline, generic SQL/runtime/migration/analytics,
    product config YAML 같은 일부 source가 내부 baseline 또는 `example.invalid` URL을 사용한다.
  - 필요 조건: 해당 언어/영역의 public guideline 또는 organization-approved source를
    `review-engine/rule_sources/manifest.yaml`과 source markdown `source_ref`에 먼저 고정한다.
  - 준비되면 C, Java runtime, generic SQL, migration SQL, analytics SQL, product/Kubernetes/Helm YAML
    rule expansion을 `Now`에 별도 unit으로 올린다.
  - owner: [rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:1)
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
