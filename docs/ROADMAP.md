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

`2026-04-25` 기준으로 post-review immediate fixes, cleanup, contract readiness,
source gap closure처럼 이미 닫힌 항목은 이 roadmap에서 제거한다.

현재 roadmap에는 완료 항목을 반복 노출하지 않고, 외부 조건 없이 시작 가능한 slice만
`Now`에 올린다. live provider, 외부 권한, 사람의 품질 판단, product/risk decision이
필요한 작업은 `Deferred But Not Yet Executable` 또는 `docs/deferred/*.md`에 둔다.

완료된 작업은 이 문서에 반복해서 남기지 않는다. 완료 이력은 git history,
[CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1),
[CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1),
그리고 관련 baseline artifact를 기준으로 확인한다.

현재 즉시 실행 가능한 항목은 없다.

- 회사별 코딩 규칙 intake guide와 template는
  [docs/company_rules/AUTHORING_GUIDE.md](/home/et16/work/review_system/docs/company_rules/AUTHORING_GUIDE.md:1)와
  [docs/company_rules/COMPANY_RULE_TEMPLATE.md](/home/et16/work/review_system/docs/company_rules/COMPANY_RULE_TEMPLATE.md:1)에 둔다.
- manual rule editor, private rule package install/update automation, provider tuning,
  reference-only promotion, multi-SCM, auto-fix는 deferred readiness 조건이 충족될 때까지
  구현하지 않는다.

## Now

현재 `active` 항목은 없다. 아래 deferred readiness 조건이 충족되면 새 `active` unit을
roadmap order에 맞춰 추가한다.

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
- Manual rule editor / broad authoring UI
  - 현재 상태: canonical YAML, lifecycle CLI, strict authoring validation은 존재하지만,
    별도 editor/UI는 아직 product boundary와 write boundary가 넓다.
  - 필요 조건: company rule intake guide/template, canonical YAML authoring model, profile/policy
    merge boundary, source coverage validation, approval/audit 경로를 먼저 고정한다.
  - 준비되면 rule 보기, preview, validation result, enable/disable 중심의 좁은 editor v0를
    `Now`에 별도 unit으로 올린다.
  - owner: [rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:1)
- Private rule package install/update automation
  - 현재 상태: filesystem extension root와 package validation readiness는 있으나, 회사별 rule
    package 배포/업데이트/롤백 workflow는 아직 구현 대상이 아니다.
  - 필요 조건: package metadata, private generated artifact 분리, install/update/rollback 절차,
    validation gate를 먼저 확정한다.
  - owner: [rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:61)
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
