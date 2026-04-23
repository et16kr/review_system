# Roadmap

## Purpose

이 문서는 앞으로 해야 할 일만 관리한다.
현재 구현 상세는 [CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)에 두고,
로드맵에는 완료된 기반 요약과 남은 실행 단위만 남긴다.

마지막 코드 상태 점검일: `2026-04-23`

상태 표기:

- `active`: 바로 작업할 우선순위가 높고, 한 번에 묶을 수 있는 실행 단위가 있다.
- `partial`: 일부 코드 골격이나 테스트는 있으나 운영 완료 기준에는 못 미친다.
- `not_started`: 현재 코드에 구현이 없다.
- `watch`: 새 기능 개발 대상은 아니며 회귀 방지와 운영 관찰만 한다.

## Completed Foundation

아래 항목은 새 로드맵 작업이 아니라 유지/회귀 방지 대상으로 본다.

| Area | 완료된 기반 |
| --- | --- |
| Review-bot Phase A Trust Foundation | runner-level verify path, lifecycle event history, finding outcomes analytics |
| Multi-language core canonicalization | current seed corpus coverage, language/profile/context/dialect routing, provider C++ fixed prior 제거 |
| CUDA native capability expansion | pipeline async, thread block cluster, TMA, WGMMA rule/profile 축 |
| Smoke fixture baseline | lifecycle smoke, mixed-language, curated polyglot, CUDA targeted fixture |
| Wrong-language telemetry loop | provenance/cause/actionability 분리, smoke event와 detector backlog 분리 |
| Provider quality / density gate | packaged provider quality corpus, deterministic `stub` gate, OpenAI opt-in skip path, fixture `density_contract` |

## Execution Order

### 1. Provider / Ranking / Density Tuning

상태: `active`

남은 작업:

1. `OPENAI_API_KEY`가 있는 환경에서 OpenAI comparison artifact를 수집한다.
2. OpenAI와 `stub` 결과의 title/summary/fix guidance 길이, claim strength, evidence anchoring을 사람이 검토한다.
3. `docs/baselines/review_bot/provider_ranking_density_*.md`를 운영 window별로 갱신해 tuning 전후 차이를 비교한다.
4. ranking weight를 조정해야 할 경우 먼저 deterministic regression을 추가하고, rule expansion보다 앞서 고정한다.
5. project-local feedback이 필요한지 판단하고, 필요하면 전역 `rule_no` weight와 분리하는 설계를 만든다.

완료 기준:

- provider별 phrasing 편차와 과한 단정이 baseline에서 추적된다.
- density 관련 회귀가 deterministic test 또는 smoke contract에서 잡힌다.
- ranking 변경은 baseline diff와 함께 설명 가능하다.

### 2. Smoke And Evaluation Hardening

상태: `partial`

남은 작업:

1. deterministic engine evaluation과 local GitLab smoke의 역할을 `release gate`와 `pre-release smoke`로 분리한다.
2. smoke JSON artifact와 telemetry snapshot을 정기 baseline으로 남기는 절차를 고정한다.
3. fixture별 실제 signal에 맞춰 `density_contract`를 세분화한다.
4. synthetic wrong-language smoke event가 운영 backlog에 섞이지 않는지 정기 snapshot에서 확인한다.

완료 기준:

- network 없는 deterministic gate와 local GitLab smoke의 책임이 문서/명령에서 분리된다.
- routing, expected rule, density, wrong-language telemetry contract가 fixture별로 검증된다.
- local GitLab smoke는 adapter/lifecycle 변경 시 표준 검증으로 유지된다.

### 3. Targeted Rule Expansion

상태: `partial`

남은 작업:

1. telemetry나 smoke에서 under-trigger가 확인된 얇은 gap 하나를 고른다.
2. source atom 또는 source 문서를 추가한다.
3. coverage matrix, pack/profile/policy, detector hinted rule을 함께 갱신한다.
4. expected example 또는 targeted diff contract를 추가한다.
5. ingest, engine evaluation, bot regression, 관련 smoke 영향을 같은 작업 범위에서 검증한다.

우선 후보:

- Go: sentinel error, `errors.Is/As`, HTTP handler boundary validation, transaction/resource cleanup.
- Dockerfile: BuildKit secret mount, digest/provenance 세분화, multi-stage runtime hardening.

완료 기준:

- source, coverage, rule/policy, detector, regression, ingest 검증이 한 번에 들어간다.
- rule 추가가 provider/ranking/density baseline을 악화시키지 않는다.

### 4. Review-Bot Context And UX

상태: `partial`

남은 작업:

1. hunk 기반 review unit split의 한계를 측정하고 syntax-aware split이 필요한 언어를 고른다.
2. related file retrieval과 project-scoped codebase index를 분리 설계한다.
3. `full-report`/`backlog` note에 “왜 이 항목이 보였는가” 설명을 작게 추가한다.
4. project-local feedback이 global rule quality를 왜곡하지 않도록 learned weight granularity를 정한다.
5. `.review-bot.yaml`, `summarize`, `ask`, walkthrough note의 우선순위를 재평가한다.

완료 기준:

- backlog와 surfacing reason이 사용자에게 더 잘 설명된다.
- project-local feedback이 global quality metric을 왜곡하지 않는다.
- context retrieval이 false-positive를 줄이는지 deterministic fixture로 확인된다.

### 5. Organization Rule Extension

상태: `partial`

남은 작업:

1. 실제 private extension 샘플 root를 하나 만든다.
2. CI에서 public-only와 private-enabled 경로를 분리한다.
3. extension failure policy를 dev/prod별로 문서화하고 설정 예제를 추가한다.
4. `source_family` legacy alias 제거 또는 장기 호환 방침을 결정한다.
5. `pack_weight`, `reference_only`, conflict action의 운영 표현 방식을 확정한다.

완료 기준:

- public core는 private extension 없이 항상 동작한다.
- private extension은 명시 설정으로만 로드된다.
- private rule priority가 retrieval/rerank/prompt/detector에서 일관된다.
- public/private 경계가 깨지면 CI에서 잡힌다.

### 6. Multi-SCM Adapter Expansion

상태: `not_started`

남은 작업:

1. GitHub PR adapter를 `ReviewSystemAdapterV2`에 맞춰 설계한다.
2. GitHub metadata/diff/thread/status/check mapping을 구현한다.
3. GitHub smoke 또는 replay fixture를 최소 하나 만든다.
4. GitLab과 GitHub가 같은 lifecycle analytics schema를 공유하는지 검증한다.
5. GitHub 안정화 뒤 Gerrit patchset 모델을 별도 설계한다.

완료 기준:

- GitHub PR review lifecycle이 GitLab과 같은 bot runner를 공유한다.
- adapter 차이는 `ReviewSystemAdapterV2` 경계 안에 머문다.
- GitHub smoke가 최소 happy path를 검증한다.

### 7. Automation

상태: `not_started`

남은 작업:

1. `@review-bot apply`를 하기 전에 low-risk fix class와 권한 모델을 정의한다.
2. patch 생성, audit, rollback, reviewer approval 경계를 설계한다.
3. provider `auto_fix_lines` payload를 실제 patch application flow와 연결할지 결정한다.
4. multi-reviewer parallel agent나 IDE 실시간 리뷰는 trust metric이 안정된 뒤 재평가한다.

재평가 조건:

- `fix_conversion_rate_28d`가 2 phase 이상 plateau.
- verify/ranking/provider tuning만으로 false-positive 저감이 정체.
- low-risk fix class가 충분히 반복되고 reviewer trust가 안정됨.

완료 기준:

- 자동 수정은 low-risk class로 제한된다.
- 사람이 승인하기 전에는 기존 Git review UI의 mergeable state를 바꾸지 않는다.
- audit/rollback 경로가 명확하다.

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

Provider/ranking/density 변경:

```bash
cd review-bot && uv run pytest tests/test_multilang_smoke_fixture.py tests/test_provider_quality.py -q
cd review-bot && uv run python -m review_bot.cli.evaluate_provider_quality --provider stub
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
