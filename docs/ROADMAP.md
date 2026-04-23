# Roadmap

## Purpose

이 문서는 앞으로 해야 할 일을 한 곳에서 관리한다.
이미 완료된 설계 문서나 요구사항 초안은 유지하지 않고, 현재 시점의 우선순위와 완료 기준만 남긴다.

## Already Closed

아래는 더 이상 active work document를 따로 둘 필요가 없는 항목이다.

- Review-bot Phase A Trust Foundation
  - runner-level verify path
  - `fixed_in_followup_commit` / `remote_resolved_manual_only`
  - `finding_lifecycle_events`
  - `GET /internal/analytics/finding-outcomes`
- Multi-language core canonicalization
  - current seed source bundle coverage 완료
  - language/profile/context/dialect runtime routing
  - provider C++ fixed prior 제거
- CUDA native capability expansion
  - pipeline async
  - thread block cluster
  - TMA
  - WGMMA
- Smoke fixture expansion baseline
  - lifecycle smoke entrypoint
  - synthetic mixed-language fixture
  - curated polyglot fixture
  - CUDA targeted fixture

이 항목들은 새 기능 개발 대상이 아니라 회귀 방지와 운영 최적화 대상으로 본다.

## Execution Order

### 1. Wrong-Language Telemetry Loop

가장 먼저 운영 데이터를 고정한다.

- `GET /internal/analytics/wrong-language-feedback`를 정기 점검한다.
- `ops/scripts/capture_wrong_language_telemetry.py`로 snapshot을 남긴다.
- `ops/scripts/build_wrong_language_backlog.py`로 backlog Markdown을 만든다.
- `high` priority pair/path/profile 조합부터 detector blind spot을 고친다.
- 수정 후 mixed-language smoke와 telemetry snapshot으로 재발 여부를 확인한다.

완료 기준:

- 반복 오분류를 detector backlog로 바로 전환할 수 있다.
- detector miss, thread 대상 오류, policy mismatch를 구분할 수 있다.

### 2. Provider / Ranking / Density Tuning

현재 corpus 기준 품질을 먼저 안정화한다.

- provider별 title/summary/fix guidance 길이와 claim strength 편차를 줄인다.
- language/profile/context별 top-k ranking drift를 regression으로 고정한다.
- same-line/category duplicate suppression과 file round-robin batch 품질을 점검한다.
- CUDA 코멘트는 stream/sync/device ownership 근거가 먼저 드러나는지 별도 확인한다.

완료 기준:

- 동일 finding class에서 provider별 phrasing 편차가 줄어든다.
- rule을 더 추가하지 않아도 현재 corpus의 false-positive와 under-trigger가 안정된다.

### 3. Smoke And Evaluation Hardening

튜닝 결과를 계속 잡아낼 수 있게 fixture contract를 강화한다.

- `review-engine` expected examples와 diff contracts를 유지한다.
- `ops/fixtures/review_smoke/*/expected_smoke.json` contract를 확장한다.
- `synthetic-mixed-language`, `curated-polyglot`, `cuda-targeted` smoke를 유지한다.
- 실제 provider comparison은 release gate가 아니라 tuning backlog로 둔다.

완료 기준:

- daily deterministic smoke는 network 없이 통과한다.
- routing, expected rule, wrong-language telemetry contract가 fixture별로 검증된다.

### 4. Targeted Rule Expansion

최적화 기준이 잡힌 뒤 얇은 언어만 작게 확장한다.

우선 후보:

- `go`
  - error wrapping / sentinel error
  - context cancellation
  - goroutine/channel lifecycle
  - HTTP handler boundary validation
  - transaction/resource cleanup
- `dockerfile`
  - multi-stage runtime hardening
  - non-root runtime user
  - BuildKit secret mount
  - digest pinning / provenance
  - package cache/layer hygiene

선택 후보:

- `javascript`
- `java`
- `rust`

성숙 축은 telemetry-driven으로만 추가한다.

- `cpp`
- `cuda`
- `sql`
- `yaml`
- `python`
- `typescript`
- `c`
- `bash`

Rule expansion 완료 기준:

1. source 문서 또는 source atom 추가
2. coverage matrix 갱신
3. canonical pack/profile/policy 갱신
4. query detector와 hinted rule 연결
5. expected example 또는 targeted regression 추가
6. ingest 결과 확인
7. engine/bot/smoke 영향 검증

### 5. Review-Bot Context And UX

탐지량을 늘리기보다 신뢰도와 설명력을 높인다.

- syntax-aware review unit split
- related file retrieval
- finding-level second retrieval
- `(project_ref, rule_no)` 또는 유사 granularity learned weight
- similarity-aware suppression / memory
- `.review-bot.yaml` 설정 수렴
- `summarize`, `ask`, walkthrough note
- must-fix / should-fix / coaching tier 표현
- run-level summary/general note lifecycle 고도화
- reviewer/team preference 반영

완료 기준:

- 전체 backlog와 “왜 이 항목이 보였는가”가 사용자에게 더 잘 설명된다.
- project-local feedback이 global rule quality를 왜곡하지 않는다.

### 6. Organization Rule Extension

공개 core와 private organization extension의 경계를 정리한다.

권장 순서:

1. schema / loader / policy parser
2. priority resolver
3. ingest export format
4. retrieval rerank
5. prompt composer
6. detector plugin
7. public/private CI split

결정 필요:

- `pack_weight`를 profile별로만 둘지 runtime feature flag도 둘지
- `reference_only`를 conflict action으로 둘지 reviewability로만 표현할지
- API/DB에서 `source_family` legacy alias를 언제 제거할지
- extension loading 실패를 운영에서 fail-fast로 강제할지

### 7. Multi-SCM Adapter Expansion

GitLab 다음 순서는 아래다.

1. GitHub adapter
2. Gerrit adapter

GitHub가 먼저인 이유:

- PR thread/status/check 개념이 GitLab과 상대적으로 가깝다.
- Gerrit은 patchset 중심 모델이라 `review_request_id`와 `head_sha` mapping 비용이 더 크다.

### 8. Automation

아래는 후순위다.

- `@review-bot apply`
- low-risk patch bundle
- multi-reviewer parallel agent
- IDE 실시간 리뷰

재평가 조건:

- `fix_conversion_rate_28d`가 2 phase 이상 plateau
- 단일 verify/ranking/provider tuning의 false-positive 저감 효과가 정체

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
