# Review Engine Multi-Language Exhaustive Review

## 목적

이 문서는 2026-04-23 기준으로 수행한
멀티 랭귀지 / CUDA / Altibase 제거 변경 전수 점검 결과와
실제 수정 사항을 기록한다.

이번 점검의 목표는 아래 세 가지였다.

- runtime language/profile routing이 generic 경로를 과승격하지 않는지 확인
- retrieval/runtime contract가 Altibase 제거 의도와 실제 shipped corpus 사이에서 어긋나지 않는지 확인
- 수정 후 전체 테스트와 재현 샘플로 다시 검증해 결과를 고정

## 범위

이번 점검은 아래 영역을 포함했다.

- `review-engine` language registry / retrieval / example corpus / contract tests
- `review-bot` language registry
- `review-platform` validation path
- 관련 docs 중 evaluation harness / historical report drift

local GitLab smoke나 bot publish/sync 동작 자체는
초기 수정 단계에서는 직접 영향 범위 밖으로 봤지만,
추가 전수 점검 단계에서 multilang smoke까지 다시 검증했다.

## 수정된 발견 사항

### 1. Generic `app/*.ts`, `src/app/*.ts`, `pages/*.ts`의 Next.js 오분류 수정

문제:

- 기존 registry는 `app/`, `src/app/`, `pages/`, `src/pages/` 경로만으로
  `nextjs_frontend`를 부여할 수 있었다.
- 그 결과 generic TypeScript 파일도 `TS.NEXT.*` 규칙 후보로 들어갈 수 있었다.

수정:

- `review-engine/review_engine/languages/registry.py`
- `review-bot/review_bot/language_registry.py`

변경 내용:

- Next.js 승격을 path-only 조건에서
  `next.config` / `next/*` import 같은 명시적 신호 또는
  `page.tsx`, `layout.tsx`, `route.ts`, `middleware.ts`,
  `_app.tsx`, `_document.tsx`, `_error.tsx` 같은
  framework-specific filename 신호가 있을 때로 좁혔다.

확인 결과:

- `app/server.ts` -> `typescript/default`
- `src/app/service.ts` -> `typescript/default`
- `pages/service.ts` -> `typescript/default`
- `app/api/users/route.ts` -> `typescript/nextjs_frontend/app_router`

### 2. Generic `models/*.sql`, `src/models/*.sql`의 dbt/warehouse 오분류 수정

문제:

- 기존 SQL runtime inference는 `/models/` 경로 자체를 dbt 신호로 받아들였다.
- 그 결과 generic SQL도 `dbt_warehouse`나 `analytics` 맥락으로 승격되어
  `SQL.WH.*` 또는 `SQL.DBT.*`가 잘못 섞일 수 있었다.

수정:

- `review-engine/review_engine/languages/registry.py`
- `review-bot/review_bot/language_registry.py`

변경 내용:

- dbt path token에서 `/models/`를 제거했다.
- dbt 승격은 `dbt/` 루트, dbt-specific source token,
  또는 `snapshots/macros/seeds` 같은 더 강한 신호가 있을 때만 일어나게 조정했다.

확인 결과:

- `models/report.sql` -> `sql/default/generic/generic`
- `src/models/report.sql` -> `sql/default/generic/generic`
- `dbt/models/orders.sql` -> `sql/dbt_warehouse/analytics/generic`

### 3. `review-engine` 내부 Altidev4 corpus / contract / 전용 회귀 테스트 제거

문제:

- `review-engine` shipped corpus 안에
  `examples/altidev4*`, `expected_retrieval_examples.json`,
  `cpp_diff_contracts.json`, 전용 회귀 테스트가 남아 있었다.
- 이는 "Altibase 완전 제거" 의도와 실제 repo contract가 어긋난 상태였다.

수정:

- Altidev4 snippet/diff example 제거
- Altidev4 manifest 제거
- Altidev4 전용 테스트 제거
- `expected_retrieval_examples.json`에서 Altidev4 입력 제거
- `cpp_diff_contracts.json`을 repo-local generic C++ diff 예제로 재구성
  - 현재 baseline: `examples/manual_memory.diff`

추가 보호 장치:

- `review-engine/tests/test_expected_examples.py`
  - shipped retrieval example spec에 `altidev4` / `altibase`가 다시 들어오지 않는지 검사
- `review-engine/tests/test_cpp_diff_contracts.py`
  - generic diff contract manifest가 repo-local non-Altibase fixture만 쓰는지 검사

## 추가한 회귀 테스트

다음 케이스를 새로 고정했다.

- `review-engine/tests/test_language_registry.py`
  - generic `app/*.ts`, `src/app/*.ts`, `pages/*.ts`, `models/*.sql`, `src/models/*.sql`
    가 default로 남는지 확인
- `review-bot/tests/test_language_registry.py`
  - bot registry도 동일한 분류 결과를 내는지 확인
- `review-engine/tests/test_multilang_regressions.py`
  - generic `app/server.ts`에서 `TS.NEXT.*`가 새지 않는지 확인
  - generic `models/report.sql`에서 `SQL.DBT.*`, `SQL.WH.*`가 새지 않는지 확인
- `review-engine/tests/test_expected_examples.py`
  - removed Altibase corpus reference 재유입 방지
- `review-engine/tests/test_cpp_diff_contracts.py`
  - generic C++ diff contract manifest 유효성 검증

## 최종 검증

### 1. Targeted regression tests

실행:

```bash
cd review-engine && uv run pytest tests/test_language_registry.py tests/test_multilang_regressions.py tests/test_expected_examples.py tests/test_cpp_diff_contracts.py -q
cd review-bot && uv run pytest tests/test_language_registry.py -q
```

결과:

- `review-engine`: `36 passed`
- `review-bot`: `7 passed`

### 2. Full test suites

실행:

```bash
cd review-engine && uv run pytest -q
cd review-bot && uv run pytest -q
```

결과:

- `review-engine`: `100 passed in 47.34s`
- `review-bot`: `158 passed in 56.17s`

### 3. Direct runtime spot checks

직접 재현 결과:

- `app/server.ts` -> profile `default`, rules `[]`
- `models/report.sql` -> profile `default`, rules `[]`
- `app/api/users/route.ts` -> profile `nextjs_frontend/app_router`, rules `['TS.NEXT.1']`
- `dbt/models/orders.sql` -> profile `dbt_warehouse/analytics`, rules `['SQL.DBT.1', 'SQL.1', 'SQL.4']`

### 4. Altibase reference scan

실행:

```bash
rg -n 'altidev4|Altidev4|altibase|Altibase' \
  review-engine/review_engine \
  review-engine/examples \
  review-engine/data \
  review-engine/rules \
  review-engine/rule_sources \
  review-engine/README.md
```

결과:

- runtime / examples / rules / data / README 기준으로
  Altibase / Altidev4 reference 미검출

주의:

- 테스트 코드에는 "재유입 방지" assertion 때문에 문자열 자체가 남아 있다.
- 즉 shipped surface에서는 제거됐고,
  tests에는 removal guard로만 남아 있는 상태다.

### 5. Additional cross-project validation

추가 실행:

```bash
cd review-platform && uv run pytest tests/test_pr_flow.py -q
bash ops/scripts/smoke_local_gitlab_multilang_review.sh
```

결과:

- `review-platform`: `3 passed in 1.09s`
- multilang local GitLab smoke: 성공
  - MR: `root/review-system-multilang-smoke!8`
  - review state: `last_status=success`
  - bot comment count: `4`
  - required tags 확인: `[봇 리뷰][yaml]`, `[봇 리뷰][sql]`, `[봇 리뷰][python]`
  - wrong-language telemetry pair 확인: `yaml -> markdown`

### 6. Historical doc drift follow-up

repo-wide scan에서는 runtime 바깥의 historical 문서에도
Altidev4 reference가 남아 있는 것을 확인했다.

대상:

- `IMPLEMENTATION_PROGRESS.md`
- `COMPLETION_REPORT.md`
- `SELF_CODE_REVIEW.md`

조치:

- 각 문서 상단에 historical snapshot임을 명시하는 warning note를 추가했다.
- 최신 기준 문서로 `AGENTS.md`,
  `docs/REVIEW_ENGINE_MULTI_LANGUAGE_EXHAUSTIVE_REVIEW.md`,
  `docs/REVIEW_ENGINE_EVALUATION_HARNESS.md`,
  `docs/API_CONTRACTS.md`,
  `docs/OPERATIONS_RUNBOOK.md`를 안내하도록 정리했다.

## 남은 리스크

- 이번 수정은 language routing과 example corpus 정리에 집중되어 있다.
- `review_runner` publish/sync 흐름은 추가 smoke까지 통과했지만,
  이번 턴에서 실제로 바뀐 코드는 언어 분류와 corpus 정리 중심이었다.
- 이후 bot publication formatting이나 multi-language smoke 스크립트까지 다시 만질 경우에는
  `ops/scripts/smoke_local_gitlab_multilang_review.sh`를 추가로 돌리는 것이 안전하다.
