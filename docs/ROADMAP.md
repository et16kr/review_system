# Roadmap

## Purpose

이 문서는 앞으로 해야 할 일을 한 곳에서 관리한다.
완료된 설계 문서나 요구사항 초안은 유지하지 않고, 현재 코드 상태와 다음 실행 순서만 남긴다.

마지막 코드 상태 점검일: `2026-04-23`

상태 표기:

- `closed`: 새 기능 개발 대상이 아니며 회귀 방지와 운영 최적화만 한다.
- `active`: 바로 작업할 우선순위가 높고, 한 번에 묶을 수 있는 실행 단위가 있다.
- `partial`: 일부 코드 골격이나 테스트는 있으나 운영 완료 기준에는 못 미친다.
- `not_started`: 현재 코드에 구현이 없다.

## Current Code Snapshot

- `review-engine`은 `cpp`, `c`, `cuda`, `python`, `typescript`, `javascript`, `java`, `go`, `rust`, `bash`, `sql`, `yaml`, `dockerfile` rule root를 가지고 있다.
- 현재 rule count는 public/shared seed 기준 총 `344`개다. 이 중 `248`개는 auto/default reviewable이고 `96`개는 `reference_only`다.
- `rule_sources/coverage_matrix.yaml` 기준 current seed corpus에는 `pending` source atom이 없다.
- `review-bot` adapter 구현은 `local_platform`과 `gitlab`뿐이다. GitHub/Gerrit adapter 코드는 아직 없다.
- GitLab trigger는 MR note의 `@review-bot ...` 또는 `/review-bot ...` 명령뿐이다. MR open/update만으로는 자동 inline review를 게시하지 않는다.
- 지원 note command는 `review`, `full-report`, `backlog`, `help`다. `apply`, `ask`, `summarize` 같은 automation/interactive command는 아직 없다.
- `review-engine`에는 extension rule root, prompt overlay, entry point, detector plugin, strict loading 골격이 있다. 다만 private/public CI split과 운영 배포 계약은 아직 정리되지 않았다.
- `review-bot`에는 hunk 기반 review unit split, 큰 add-only hunk chunking, file context fetch, optional codebase similarity search가 있다. AST/syntax-aware split이나 project-scoped memory는 아직 없다.
- wrong-language analytics는 `smoke/production/unknown` provenance, `triage_cause`, `actionability`를 반환한다. smoke fixture의 synthetic feedback은 detector backlog에서 기본 분리된다.

## Already Closed

아래는 active feature work가 아니라 회귀 방지와 운영 최적화 대상으로 본다.

| Area | Closed scope |
| --- | --- |
| Review-bot Phase A Trust Foundation | runner-level verify path, `fixed_in_followup_commit`, `remote_resolved_manual_only`, `finding_lifecycle_events`, `GET /internal/analytics/finding-outcomes` |
| Multi-language core canonicalization | current seed source bundle coverage, language/profile/context/dialect runtime routing, provider C++ fixed prior 제거 |
| CUDA native capability expansion | pipeline async, thread block cluster, TMA, WGMMA |
| Smoke fixture expansion baseline | lifecycle smoke entrypoint, synthetic mixed-language fixture, curated polyglot fixture, CUDA targeted fixture |
| Wrong-language telemetry loop hardening | provenance/cause/actionability classifier, smoke 분리, detector fix backlog section, telemetry snapshot warning |

## Execution Order

### 1. Provider / Ranking / Density Tuning

상태: `partial`

현재 코드 상태:

- OpenAI provider와 deterministic stub provider가 있다.
- OpenAI provider는 language/profile/context/dialect runtime hint와 category별 prompt hint를 사용한다.
- runner-level verify는 구현되어 있으나 기본값은 `BOT_VERIFY_ENABLED=0`이다.
- engine rerank는 similarity, pack weight, base score, severity, pattern boost, specificity, tier boost를 조합한다.
- publish 단계에는 batch cap, file round-robin, per-file cap, per-rule cap, same-line/category duplicate suppression이 있다.
- rule effectiveness 기반 score weight는 전역 `rule_no` 단위이며, project-local granularity는 아직 아니다.
- provider별 phrasing/claim-strength를 비교하는 golden corpus나 regression gate는 아직 없다.

다음 실행 단위:

1. 현재 smoke/corpus에서 provider별 title/summary/fix guidance 길이와 claim strength를 비교한다.
2. same-line/category duplicate suppression과 file round-robin 결과를 fixture contract로 고정한다.
3. CUDA finding은 stream/sync/device ownership 근거가 제목과 요약 앞부분에 드러나는지 별도 샘플로 확인한다.
4. tuning 결과는 rule expansion보다 먼저 regression으로 고정한다.

완료 기준:

- 같은 finding class에서 provider별 phrasing 편차가 줄어든다.
- rule을 더 추가하지 않아도 현재 corpus의 false-positive와 under-trigger가 안정된다.
- density 관련 회귀가 smoke나 deterministic evaluation에서 잡힌다.

### 2. Smoke And Evaluation Hardening

상태: `partial`

현재 코드 상태:

- `review-engine`에는 `evaluate_examples`, `evaluate_diff_contracts` CLI가 있다.
- `review-engine/examples`에는 multilang, CUDA, safe/unsafe 예제가 있다.
- `ops/fixtures/review_smoke`에는 `synthetic-mixed-language`, `curated-polyglot`, `cuda-targeted` fixture가 있다.
- `expected_smoke.json`은 expected language tags, expected engine languages/rules, forbidden language tags, required paths, wrong-language telemetry flow를 검증한다.
- mixed-language smoke는 실행 중 provider를 `stub/stub`으로 전환했다가 복구한다.
- local GitLab 기반 smoke는 강력하지만 일반 PR CI로 돌리기에는 무겁다.

다음 실행 단위:

1. deterministic engine evaluation과 local GitLab smoke의 역할을 분리해 release gate와 tuning backlog를 나눈다.
2. `expected_smoke.json`에 rule/routing/density contract를 필요한 만큼 확장한다.
3. smoke JSON artifact와 telemetry snapshot을 baseline으로 남기는 운영 절차를 고정한다.
4. smoke가 만드는 synthetic wrong-language event는 운영 backlog에서 분리한다.

완료 기준:

- daily deterministic smoke는 network 없이 통과한다.
- routing, expected rule, density, wrong-language telemetry contract가 fixture별로 검증된다.
- local GitLab smoke는 pre-release 또는 adapter/lifecycle 변경 시 표준 검증으로 유지된다.

### 3. Targeted Rule Expansion

상태: `partial`

현재 코드 상태:

- current seed corpus coverage는 완료 상태라서 무작정 rule을 넓히는 단계는 아니다.
- `go`는 `project_go` pack 12개 rule을 가지고 있고 cleanup, context propagation, goroutine ownership, ignored error, panic, reference concurrency guidance를 이미 다룬다.
- `go` gap은 sentinel error, `errors.Is/As`, HTTP handler boundary validation, transaction/resource cleanup의 더 구체적 detector와 regression이다.
- `dockerfile`은 13개 rule을 가지고 있고 latest tag, non-root runtime, apt cache/layer hygiene, broad copy, remote ADD, curl pipe shell을 다룬다.
- `dockerfile` gap은 BuildKit secret mount, digest/provenance 세분화, multi-stage runtime hardening의 auto-reviewable detector다.
- `javascript`, `java`, `rust`는 baseline/deepening pack이 있으나 현재 우선순위는 telemetry와 provider/ranking 안정화 뒤다.
- `cpp`, `cuda`, `sql`, `yaml`, `python`, `typescript`, `c`, `bash`는 성숙 축으로 보고 telemetry-driven으로만 추가한다.

다음 실행 단위:

1. telemetry나 smoke에서 under-trigger가 확인된 얇은 gap 하나를 고른다.
2. source atom 또는 source 문서를 추가한다.
3. coverage matrix, pack/profile/policy, detector hinted rule, expected example 또는 diff contract를 함께 갱신한다.
4. ingest와 engine/bot/smoke 영향 검증을 같은 PR 범위에 묶는다.

완료 기준:

- source 문서 또는 source atom 추가
- coverage matrix 갱신
- canonical pack/profile/policy 갱신
- query detector와 hinted rule 연결
- expected example 또는 targeted regression 추가
- ingest 결과 확인
- engine/bot/smoke 영향 검증

### 4. Review-Bot Context And UX

상태: `partial`

현재 코드 상태:

- hunk 기반 review unit split과 큰 add-only hunk chunking이 있다.
- adapter가 지원하면 head 파일 내용 일부를 file context로 가져온다.
- `review-engine`에는 `/codebase/index`와 `/codebase/search`가 있고, bot은 similar code를 evidence/provider input에 저장할 수 있다.
- `full-report`, `backlog`, `help` general note UX가 있다.
- current backlog와 feedback suppress 상태는 report에서 분리된다.
- syntax-aware AST split, related file retrieval, finding-level second retrieval은 아직 없다.
- `.review-bot.yaml` 설정, `summarize`, `ask`, walkthrough note, must-fix/should-fix/coaching tier, reviewer/team preference는 아직 없다.
- learned weight는 전역 rule effectiveness 기반이고 `(project_ref, rule_no)` granularity가 아니다.
- codebase similarity collection은 project-scoped memory로 분리되어 있지 않다.

다음 실행 단위:

1. hunk 기반 unit split의 한계를 측정하고 syntax-aware split이 필요한 언어를 고른다.
2. related file retrieval과 project-scoped codebase index를 분리 설계한다.
3. full-report/backlog note에 “왜 이 항목이 보였는가” 설명을 작게 추가한다.
4. project-local feedback이 global rule quality를 왜곡하지 않도록 learned weight granularity를 정한다.

완료 기준:

- 전체 backlog와 “왜 이 항목이 보였는가”가 사용자에게 더 잘 설명된다.
- project-local feedback이 global rule quality를 왜곡하지 않는다.
- context retrieval이 false-positive를 줄이는지 deterministic fixture로 확인된다.

### 5. Organization Rule Extension

상태: `partial`

현재 코드 상태:

- `REVIEW_ENGINE_EXTENSION_RULE_ROOTS`와 `REVIEW_ENGINE_EXTENSION_PROMPT_ROOTS`가 있다.
- `review_engine.rule_extensions` entry point를 통해 rule root, prompt root, detector plugin을 discovery할 수 있다.
- extension rule root는 public root와 같이 pack/profile/policy loader에 합성된다.
- extension prompt overlay는 `PromptComposer`에 합성된다.
- detector plugin hook은 `QueryDetectorManager`에 연결되어 있다.
- priority resolver는 `pack_weight`, `priority_tier`, explicit override/exclusion을 반영한다.
- ingest summary는 organization policy record count와 extension rule roots를 반환한다.
- tests는 filesystem extension, entry point extension, invalid spec strict/fallback, prompt overlay, rerank priority를 검증한다.

아직 남은 결정:

- `pack_weight`를 profile별로만 둘지 runtime feature flag도 둘지
- `reference_only`를 conflict action으로 둘지 reviewability로만 표현할지
- API/DB에서 `source_family` legacy alias를 언제 제거할지
- extension loading 실패를 운영에서 fail-fast로 강제할지
- public/private CI split과 private rule packaging contract를 어떻게 둘지

다음 실행 단위:

1. 실제 private extension 샘플 root를 하나 만들고 CI에서 public-only와 private-enabled를 분리한다.
2. extension failure policy를 dev/prod별로 문서화하고 설정 예제를 추가한다.
3. `source_family` alias 제거 또는 장기 호환 방침을 결정한다.

완료 기준:

- public core는 private extension 없이 항상 동작한다.
- private extension은 명시 설정으로만 로드된다.
- private rule이 retrieval/rerank/prompt/detector에서 일관되게 우선순위를 가진다.
- CI에서 public/private 경계가 깨지면 바로 잡힌다.

### 6. Multi-SCM Adapter Expansion

상태: `not_started`

현재 코드 상태:

- 구현 adapter는 `local_platform`과 `gitlab`뿐이다.
- `ReviewSystemAdapterV2` protocol은 meta/diff/thread/upsert/resolve/status/feedback/file/general-note 경계를 정의한다.
- GitHub Actions는 YAML review context로는 지원하지만 GitHub PR adapter는 없다.
- Gerrit adapter 코드는 없다.

권장 순서:

1. GitHub adapter
2. Gerrit adapter

GitHub가 먼저인 이유:

- PR thread/status/check 개념이 GitLab과 상대적으로 가깝다.
- Gerrit은 patchset 중심 모델이라 `review_request_id`와 `head_sha` mapping 비용이 더 크다.

완료 기준:

- GitHub PR metadata/diff/thread/status/check mapping이 `ReviewSystemAdapterV2`에 맞는다.
- GitLab과 GitHub가 같은 lifecycle analytics schema를 공유한다.
- GitHub smoke 또는 replay fixture가 최소 하나 있다.

### 7. Automation

상태: `not_started`

현재 코드 상태:

- note command parser는 `review`, `full-report`, `backlog`, `help`만 인식한다.
- `@review-bot apply`, low-risk patch bundle, multi-reviewer parallel agent, IDE 실시간 리뷰 구현은 없다.
- auto-fix line payload는 provider schema에 있으나 운영 patch application flow와 연결되어 있지 않다.

재평가 조건:

- `fix_conversion_rate_28d`가 2 phase 이상 plateau
- 단일 verify/ranking/provider tuning의 false-positive 저감 효과가 정체
- low-risk fix class가 충분히 반복되고 reviewer trust가 안정됨

완료 기준:

- patch 생성, 권한, audit, rollback, reviewer approval 경계가 명확하다.
- 자동 수정은 low-risk class로 제한된다.
- 기존 Git review UI에서 사람이 승인하기 전에는 mergeable state를 바꾸지 않는다.

## Validation Baseline

일반 변경:

```bash
cd review-engine && uv run pytest -q
cd review-bot && uv run pytest -q
cd review-platform && uv run pytest tests/test_pr_flow.py -q
```

Rule/retrieval 변경:

```bash
cd review-engine && uv run python -m review_engine.cli.ingest_guidelines
uv run --project review-engine python -m review_engine.cli.evaluate_examples
uv run --project review-engine python -m review_engine.cli.evaluate_diff_contracts
```

GitLab/lifecycle 변경:

```bash
bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

Multilanguage/routing 변경:

```bash
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture synthetic-mixed-language
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture curated-polyglot --project-ref root/review-system-curated-polyglot-smoke
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture cuda-targeted --project-ref root/review-system-cuda-smoke
```
