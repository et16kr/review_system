# Post-Review Immediate Fixes

## Purpose

이 문서는 `2026-04-24` `gpt-5.5` 리뷰 라운드가 끝난 뒤 바로 수정해야 할 항목만
후속 실행 순서로 정리한다.

원본 finding과 evidence의 source of truth는 아래 문서다.

- [CURRENT_STATE_REVIEW.md](/home/et16/work/review_system/docs/reviews/CURRENT_STATE_REVIEW.md:1)
- [REVIEW_FINDINGS_BACKLOG.md](/home/et16/work/review_system/docs/reviews/REVIEW_FINDINGS_BACKLOG.md:1)

이 문서는 구현 checklist가 아니라 post-review handoff 문서다. 각 항목을 실제로 고칠 때는
backlog entry의 evidence와 validation note를 다시 확인한다.

## Intake

즉시 수정 대상으로 보는 항목:

- `Post-review bucket=bug_fix`
- `Post-review bucket=roadmap_update`
- `Post-review bucket=remove`

즉시 수정 대상으로 보지 않는 항목:

- `Post-review bucket=keep`
- external quota, human review, 새 platform 권한, 새 UI/product contract가 필요한 deferred work
- review unit의 evidence/validation 기록 자체

## Execution Order

### 1. Gate Reliability

가장 먼저 닫는다. 이 항목이 열려 있으면 표준 검증 명령이 회귀 신호가 아니라 hang으로 끝날 수 있다.

- `B-cross-cutting-01` Make TestClient-backed gates bounded and diagnosable
  - Finding: `F-tests-01`
  - Severity: `medium`
  - 해야 할 일: `review-bot` API queue와 `review-platform` FastAPI/TestClient gate에 timeout과
    hang diagnostics를 추가하고, startup/lifespan hang을 분리 조사한다.
  - 완료 신호: `review-bot` API queue tests와 `review-platform` health/PR flow tests가
    outer timeout 없이 끝난다.

### 2. Review-Bot Contract Safety

runner, adapter, provider provenance, GitLab note UX의 contract drift를 먼저 줄인다.

- `B-review-bot-01` Fail or defer when GitLab note-trigger expected head never settles
  - Finding: `F-review-bot-02`
  - Severity: `medium`
  - 해야 할 일: expected head가 끝까지 settle되지 않으면 stale diff로 성공 처리하지 말고
    retryable failure 또는 pending/deferred state로 남긴다.

- `B-review-bot-02` Scope adapter thread and feedback identity explicitly
  - Finding: `F-review-bot-03`
  - Severity: `medium`
  - 해야 할 일: adapter thread/comment/event id가 global unique인지, review request scoped인지
    contract와 DB uniqueness를 맞춘다.

- `B-review-bot-03` Add model and endpoint provenance to lifecycle provider runtime
  - Finding: `F-provider-02`
  - Severity: `medium`
  - 해야 할 일: lifecycle provider runtime, state API, summary note, structured log에
    sanitized model/base URL/transport provenance를 추가한다.

- `B-review-bot-04` Post visible feedback for directed unknown note commands
  - Finding: `F-ux-03`
  - Severity: `low`
  - 해야 할 일: `@review-bot fullreport`처럼 directed unknown command에는 detect enqueue 없이
    GitLab 사용자에게 보이는 help/error note를 남긴다. incidental mention은 계속 조용히 무시한다.

### 3. Harness And Ops Automation Drift

local harness와 automation wrapper가 current contract를 검증하게 만든다.

- `B-review-platform-01` Update local harness bot bridge to key-based bot API
  - Finding: `F-architecture-02`
  - Severity: `medium`
  - 해야 할 일: `review-platform` BotClient가 제거된 legacy `pr_id` endpoint 대신
    `ReviewRequestKey` 기반 API를 쓰게 하거나, 지원하지 않는 harness control을 숨긴다.

- `B-ops-01` Retain blocked review-roadmap unit artifacts
  - Finding: `F-ops-02`
  - Severity: `medium`
  - 해야 할 일: review-roadmap automation의 blocked unit을 `/tmp` scratch가 아니라
    retained artifact로 남긴다.

- `B-ops-02` Bound OpenAI direct smoke preflight runtime
  - Finding: `F-ops-03`
  - Severity: `medium`
  - 해야 할 일: direct-smoke `curl` 호출에 connect/overall timeout 또는 outer timeout을 붙여
    automation loop가 멈추지 않게 한다.

### 4. Review-Engine Guardrails

rule/profile/coverage/authoring의 silent drift를 fail-fast로 바꾼다.

- `B-review-engine-01` Fail fast on unresolved or duplicate selected packs
  - Finding: `F-engine-02`
  - Severity: `medium`
  - 해야 할 일: missing `enabled_packs`/`shared_packs`와 duplicate selected pack을 loader에서
    조용히 건너뛰거나 덮어쓰지 않게 한다.

- `B-review-engine-02` Clarify or remove default profile configuration
  - Finding: `F-engine-03`
  - Severity: `medium`
  - 해야 할 일: `REVIEW_ENGINE_DEFAULT_PROFILE`이 runtime profile selection에 실제로 쓰이게 하거나
    operator가 오해하지 않도록 제거/rename한다.

- `B-review-engine-03` Add reverse coverage for canonical rules
  - Finding: `F-engine-04`
  - Severity: `medium`
  - 해야 할 일: source atom이 모든 canonical rule을 역방향으로 추적하는지 검증하거나
    명시적 예외 목록을 둔다.

- `B-review-engine-04` Reject unknown canonical YAML authoring keys
  - Finding: `F-engine-06`
  - Severity: `medium`
  - 해야 할 일: `fix_guidence`, `enabled_packz` 같은 typo가 Pydantic/YAML validation에서
    즉시 실패하도록 만든다.

### 5. Implementation Roadmap Updates

코드 수정은 아니지만 다음 구현 흐름을 바로 열어 주는 문서 보정이다.

- `B-docs-01` Split broad roadmap watch labels from still-open guardrail work
  - Finding: `F-docs-02`
  - Severity: `medium`
  - 해야 할 일: 닫힌 기반과 아직 남은 provider provenance, blocked artifact retention,
    direct-smoke timeout work를 `ROADMAP.md`에서 분리한다.

- `B-docs-02` Add private rule packaging roadmap owner
  - Finding: `F-docs-03`
  - Severity: `medium`
  - 해야 할 일: private rule packaging의 owner를 `ROADMAP.md` 또는 deferred readiness packet에 둔다.
    이번 문서 정리에서는 deferred owner를
    [rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:1)에
    추가했다.

### 6. Cleanup And Removal

동작 변경과 섞지 않고 별도 cleanup batch로 처리한다.

- `B-review-engine-05` Remove or relocate unowned Next.js scaffold files
  - Finding: `F-engine-08`
  - Severity: `low`
  - 해야 할 일: `review-engine/app/`가 accidental scaffold면 제거하고, fixture라면
    `examples/` 또는 `tests/fixtures/`로 옮겨 deterministic test에 연결한다.

- `B-docs-03` Remove orphan root workspace note
  - Finding: `F-docs-04`
  - Severity: `low`
  - 해야 할 일: root `review_system.md`가 외부 workflow에 쓰이지 않는지 확인한 뒤 제거하거나
    필요한 문장만 canonical docs로 병합한다.

- `B-ops-03` Rename local GitLab smoke internals away from TDE as primary surface
  - Finding: `F-ops-04`
  - Severity: `low`
  - 해야 할 일: lifecycle-named create/bootstrap/replay entrypoint를 primary로 두고,
    `tde` 이름은 compatibility wrapper 또는 fixture name으로만 남긴다.

## Deferred Work Boundary

아래는 지금 바로 고칠 항목이 아니라 deferred 문서에서 착수 조건을 관리한다.

- Provider/ranking/density tuning
  - owner: [provider_and_model_work.md](/home/et16/work/review_system/docs/deferred/provider_and_model_work.md:1)
  - 즉시 선행 작업: provider runtime provenance와 direct-smoke timeout은 먼저 고친다.

- Manual rule editor and broader authoring UX
  - owner: [rule_authoring_and_editor.md](/home/et16/work/review_system/docs/deferred/rule_authoring_and_editor.md:1)
  - 즉시 선행 작업: unknown YAML key rejection과 pack/profile fail-fast guardrail을 먼저 고친다.

- Multi-SCM adapter expansion
  - owner: [platform_expansion.md](/home/et16/work/review_system/docs/deferred/platform_expansion.md:1)
  - 즉시 선행 작업: local harness bot bridge drift는 platform expansion이 아니라 current harness bug로 먼저 고친다.

- Auto-fix automation
  - owner: [automation_work.md](/home/et16/work/review_system/docs/deferred/automation_work.md:1)
  - 즉시 선행 작업: roadmap automation artifact retention과 direct-smoke timeout은 auto-fix와 별개로 먼저 고친다.

## Neither Immediate Nor Deferred

둘 다에 해당하지 않는 내용은 있다. 이번 리뷰의 `info` finding 대부분은 현재 방향을 유지한다는
근거이며, 별도 실행 항목으로 만들지 않는다.

- Product direction: 기존 Git review surface 중심 전략은 유지한다.
- Architecture: canonical `ReviewRequestKey` identity와 runner-owned lifecycle boundary는 유지한다.
- Engine state: 현재 번들 기준 canonical YAML, generated dataset, runtime retrieval selection은 일치한다.
- Rule operations: minimal rule lifecycle CLI는 현재 범위가 맞다.
- UX: 6개 note command와 report-style reading path는 유지한다.
- Ops: deterministic gate와 runtime smoke, direct provider smoke를 분리하는 원칙은 유지한다.
- Review metadata: skipped validation, evidence level, validation policy 같은 기록은 작업 후보가 아니라
  후속 판단의 근거다.
