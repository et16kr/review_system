# Roadmap

## Purpose

이 문서는 지금 바로 실행할 수 있는 작업만 관리한다.
이미 끝난 기반 설명은 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
완료된 roadmap 이력은 git history와 [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)에 둔다.
외부 계정, live provider quota, 사람 승인, 별도 repository 권한이 필요한 작업은 실행 조건이 준비될 때까지
`docs/deferred/*.md`에 남긴다.

마지막 코드 상태 점검일: `2026-04-26`

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

`2026-04-26` 기준으로 post-review immediate fixes, cleanup, contract readiness,
source gap closure처럼 이미 닫힌 항목은 이 roadmap에서 제거한다.

현재 roadmap에는 완료 항목을 반복 노출하지 않고, 외부 조건 없이 시작 가능한 slice만
`Now`에 올린다. live provider, 외부 권한, 사람의 품질 판단, product/risk decision이
필요한 작업은 `Deferred But Not Yet Executable` 또는 `docs/deferred/*.md`에 둔다.

완료된 작업은 이 문서에 반복해서 남기지 않는다. 완료 이력은 git history,
[CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1),
[CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1),
그리고 관련 baseline artifact를 기준으로 확인한다.

현재 즉시 실행 가능한 항목은 rule self-test foundation이다.

- 회사별 코딩 규칙 intake guide와 template는
  [docs/company_rules/AUTHORING_GUIDE.md](/home/et16/work/review_system/docs/company_rules/AUTHORING_GUIDE.md:1)와
  [docs/company_rules/COMPANY_RULE_TEMPLATE.md](/home/et16/work/review_system/docs/company_rules/COMPANY_RULE_TEMPLATE.md:1)에 둔다.
- manual rule editor, private rule package install/update automation, provider tuning,
  reference-only promotion, multi-SCM, auto-fix는 deferred readiness 조건이 충족될 때까지
  구현하지 않는다.

## Now

### Build rule self-test manifest runner

- status: `active`
- 설계 기준: [RULE_SELF_TEST_DESIGN.md](/home/et16/work/review_system/docs/RULE_SELF_TEST_DESIGN.md:1)
- 목적: GitLab smoke, provider, DB 없이 `review-engine` rule별 적합/위배 specimen을
  deterministic pytest로 검증할 수 있는 기반을 만든다.
- scope:
  - `review-engine/examples/rule_self_tests/manifest.yaml` schema와 repo-local path validation
  - `review-engine/tests/test_rule_self_tests.py` pytest runner
  - enabled rule entry가 self-test case 또는 waiver를 갖는지 확인하는 accountability test
  - violating specimen은 expected rule/pattern을 검출하고, compliant specimen은 target rule을
    검출하지 않는지 확인하는 판정 flow
  - `reference_only` rule은 auto finding으로 나오지 않아야 한다는 별도 판정 flow
  - 초기 seed는 기존 `examples/expected_retrieval_examples.json`와 smoke fixture contract를
    직접 복사하지 말고 cross-reference 또는 소수 대표 case로 시작한다.
- out of scope:
  - 250개 direct-hinted rule 전체 specimen backfill
  - C++ semantic detector 보강
  - shared `SEC.*` rule을 모든 host language detector에 적용하는 runtime 변경
- done when:
  - 새 runner가 최소 대표 case와 waiver를 읽고 통과한다.
  - rule 추가 시 self-test case 또는 waiver 누락을 CI에서 알 수 있다.
  - `reference_only` rule을 "검출 성공"으로 오해하지 않는 테스트가 있다.
- validation:
  - `git diff --check`
  - `cd review-engine && uv run pytest tests/test_rule_self_tests.py -q`
  - `cd review-engine && uv run pytest tests/test_query_conversion.py tests/test_expected_examples.py -q`

### Backfill direct detector-backed rule self-test corpus

- status: `queued`
- prerequisite: `Build rule self-test manifest runner`
- 목적: direct-hinted `auto_review` rule 250개에 대해 가능한 한 rule별 violating/compliant
  specimen을 채워 hard gate coverage를 올린다.
- scope:
  - bash, c, cuda, dockerfile, go, java, javascript, python, rust, sql, typescript, yaml의
    direct-hinted `auto_review` rule 우선 backfill
  - 각 case에 `judgment: accepted`와 짧은 판단 note를 남긴다.
  - 기존 `examples/multilang`와 `examples/multilang_safe` fixture를 재사용할 수 있으면
    새 파일을 늘리기보다 manifest에서 공유한다.
  - coverage baseline artifact를 `docs/baselines/review_engine/` 아래에 남긴다.
- out of scope:
  - C++ direct hint가 없는 15개 rule hard-gate 전환
  - provider quality나 GitLab smoke
- done when:
  - direct-hinted `auto_review` rule coverage가 baseline으로 기록된다.
  - compliant specimen에서 target rule이 나오는 false-positive regression을 잡을 수 있다.
- validation:
  - `cd review-engine && uv run pytest tests/test_rule_self_tests.py tests/test_multilang_regressions.py -q`

### Close C++ self-test detector gap

- status: `queued`
- prerequisite: `Backfill direct detector-backed rule self-test corpus`
- 목적: direct hint가 없는 C++ `auto_review` rule 15개를 stable hard gate 대상으로 올린다.
- affected rules:
  - `R.13`, `R.33`, `R.37`, `I.12`, `F.7`
  - `NM.1`, `NM.2`, `NM.3`, `NM.4`
  - `CPP.PROJ.1`, `CPP.PROJ.2`, `CPP.PROJ.3`, `CPP.PROJ.4`, `CPP.PROJ.5`, `CPP.PROJ.6`
- scope:
  - `review_engine/query/languages/cpp.py`의 `PatternSpec`, `hinted_rules`,
    `direct_hint_patterns` 보강
  - 필요한 경우 `review_engine/retrieve/applicability.py` pattern alias/category signal 보강
  - 각 rule의 violating/compliant C++ specimen 추가
  - retrieval similarity만으로 통과시키지 않고 detector pattern과 expected rule을 같이 검증
- out of scope:
  - 대규모 C++ parser 도입. regex로 안정화가 안 되는 case만 별도 AST/structured detector 후보로 남긴다.
- done when:
  - C++ gap 15개가 `needs_detector` waiver 없이 accepted self-test case를 갖는다.
  - 기존 C++ retrieval/diff contract가 회귀하지 않는다.
- validation:
  - `cd review-engine && uv run pytest tests/test_rule_self_tests.py tests/test_query_conversion.py tests/test_cpp_diff_contracts.py -q`

### Verify shared security rules in host languages

- status: `queued`
- prerequisite: `Build rule self-test manifest runner`
- 목적: `SEC.*` shared auto rule이 explicit `language_id=shared`뿐 아니라 주요 host language
  review에서도 기대대로 작동하는지 확인한다.
- scope:
  - Python, JavaScript/TypeScript, Java, Go에서 hardcoded secret, shell execution, dynamic SQL
    specimen을 추가한다.
  - 현재 runtime이 shared detector를 host language review에 적용하지 않으면, 먼저 failing/waiver
    contract로 기록하고 runtime 변경 여부를 별도 판단한다.
- out of scope:
  - shared process/reference rule의 auto-review promotion
- done when:
  - shared security rule의 explicit shared-language self-test와 host-language behavior가
    manifest에 구분되어 기록된다.
- validation:
  - `cd review-engine && uv run pytest tests/test_rule_self_tests.py tests/test_query_conversion.py -q`

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

`review-engine` rule self-test 변경:

```bash
cd review-engine && uv run pytest tests/test_rule_self_tests.py -q
cd review-engine && uv run pytest tests/test_query_conversion.py tests/test_expected_examples.py tests/test_multilang_regressions.py -q
```

C++ detector self-test gap 변경:

```bash
cd review-engine && uv run pytest tests/test_rule_self_tests.py tests/test_query_conversion.py tests/test_cpp_diff_contracts.py -q
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
