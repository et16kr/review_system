# Review Engine Smoke Fixture Expansion Design

## 목적

이 문서는 현재 local GitLab smoke와 mixed-language smoke를
더 범용적인 다언어 회귀 검증 수단으로 확장하기 위한 설계를 정리한다.

핵심 목표는 다음과 같다.

- legacy-domain fixture에 과하게 의존하지 않는 smoke 체계를 만든다.
- 여러 언어와 runtime context가 섞인 실제적인 PR/MR 예제를 확보한다.
- smoke가 네트워크, 외부 저장소 최신 상태, 라이선스 이슈에 흔들리지 않도록 한다.
- review-engine의 language routing, retrieval, provider phrasing과 review-bot의
  detect/publish/sync lifecycle을 같은 흐름 안에서 검증한다.

## 현재 상태

현재 smoke는 크게 두 계열이다.

| Smoke | 현재 역할 | 한계 |
| --- | --- | --- |
| `ops/scripts/smoke_local_gitlab_tde_review.sh` | GitLab MR 재시드, baseline review, incremental replay, human reply, resolve, sync, lifecycle invariant 검증 | 이름과 fixture가 legacy TDE 시나리오에 묶여 있어 범용 smoke로 읽기 어렵다. |
| `ops/scripts/smoke_local_gitlab_multilang_review.sh` | `markdown + yaml + sql + FastAPI` 조합에서 language tag, wrong-language feedback, telemetry 흐름 검증 | repo-local synthetic fixture라 재현성은 좋지만 실제 오픈소스 프로젝트의 복합 구조를 충분히 대표하지는 않는다. |

따라서 기존 smoke를 제거하기보다는 역할을 분리한다.

- TDE smoke는 우선 **lifecycle smoke**로 재명명 가능한 compatibility wrapper로 유지한다.
- mixed-language smoke는 안정적인 synthetic fixture를 baseline으로 유지한다.
- GitHub 등 외부 저장소는 live dependency가 아니라 **pinned external-derived fixture**로 흡수한다.

## 설계 원칙

1. Smoke 실행 중 외부 GitHub를 직접 clone/fetch하지 않는다.
2. 외부 예제는 고정 commit SHA, 가져온 파일 목록, license, 변환 내역을 manifest로 남긴다.
3. 실제 저장소 전체를 vendoring하지 않고, review에 필요한 최소 diff 또는 최소 파일 slice만 둔다.
4. daily smoke는 빠르고 결정적이어야 하므로 repo-local fixture만 사용한다.
5. 외부-derived fixture는 언어/프로필 blind spot을 보강하는 targeted regression으로 먼저 둔다.
6. fixture가 커질수록 comment 개수보다 routing, expected finding, wrong-language telemetry contract를 우선 검증한다.
7. provider 품질 검증은 `stub/stub` deterministic smoke와 분리해서 선택 실행한다.

## Smoke 레이어

### L0. Engine-Only Evaluation

목적은 GitLab이나 bot 없이 retrieval contract와 language/profile detection을 빠르게 검증하는 것이다.

대상 자산:

- `review-engine/examples/expected_retrieval_examples.json`
- `review-engine/examples/cpp_diff_contracts.json`
- `review-engine/examples/multilang_diffs/`
- 앞으로 추가될 external-derived diff fixture

권장 명령:

```bash
uv run --project review-engine python -m review_engine.cli.evaluate_examples
uv run --project review-engine python -m review_engine.cli.evaluate_diff_contracts
uv run --project review-engine pytest review-engine/tests -q
```

### L1. Repo-Local Synthetic Mixed-Language Smoke

목적은 빠르고 재현 가능한 end-to-end mixed-language baseline을 유지하는 것이다.

현재 `ops/scripts/smoke_local_gitlab_multilang_review.sh`가 이 역할을 한다.
이 레이어에는 network나 external fixture download를 넣지 않는다.

검증 축:

- markdown 비검토 경로
- YAML / SQL / Python language tag
- framework file routing
- wrong-language reply 저장
- telemetry aggregation
- compact comment format

### L2. Local GitLab Lifecycle Smoke

목적은 GitLab adapter와 review-bot lifecycle invariant를 검증하는 것이다.

현재 `ops/scripts/smoke_local_gitlab_tde_review.sh`가 이 역할을 한다.
기존 파일명은 compatibility entrypoint로 유지하고,
범용 이름의 아래 alias를 표준 entrypoint로 사용한다.

```bash
ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

검증 축:

- MR 재시드
- baseline review
- incremental replay
- stale head 보정
- human reply 수집
- resolve 이후 sync
- open thread 감소
- feedback event 증가

### L3. External-Derived Curated Fixture Smoke

목적은 실제 오픈소스 프로젝트 구조에서 흔한 다언어 조합을 작은 fixture로 재현하는 것이다.

이 레이어는 외부 저장소를 smoke 시점에 직접 읽지 않는다.
대신 별도 준비 단계에서 고정 SHA의 일부 파일 또는 diff를 가져와
repo-local fixture로 저장한다.

예상 실행 형태:

```bash
bash ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture curated-polyglot \
  --json-output /tmp/review-bot-curated-polyglot-smoke.json
```

현재 multilang smoke script는 fixture profile 선택을 지원한다.
외부-derived fixture는 같은 layout과 `--fixture` entrypoint에
pinned source manifest를 추가하는 방식으로 흡수한다.

### L4. Provider Quality Comparison

목적은 deterministic smoke에서 잡기 어려운 provider phrasing 품질 편차를 별도로 보는 것이다.

이 레이어는 release gate가 아니라 수동 또는 야간 점검으로 둔다.

검증 축:

- `stub/stub` 결과와 실제 provider 결과의 finding category 차이
- 제목 길이와 claim strength
- language/profile별 prompt routing
- 과한 generic comment 또는 overclaim
- CUDA, Kubernetes, CI, SQL처럼 context-specific 근거가 필요한 comment 품질

## 외부 후보 저장소

외부 저장소는 "그대로 실행 가능한 테스트 프로젝트"가 아니라
"작은 review fixture를 만들기 좋은 source corpus"로 취급한다.

| 후보 | 용도 | 가져올만한 slice | 비고 |
| --- | --- | --- | --- |
| [open-telemetry/opentelemetry-demo](https://github.com/open-telemetry/opentelemetry-demo) | polyglot microservice, observability, Docker/Kubernetes, config 조합 | service 일부, Dockerfile, Kubernetes/compose/config 파일 | 범용 mixed-language smoke의 1순위 후보 |
| [GoogleCloudPlatform/microservices-demo](https://github.com/GoogleCloudPlatform/microservices-demo) | cloud-native microservice, Kubernetes, gRPC, deployment manifest | Kubernetes manifest, service code 일부, Dockerfile | Kubernetes/YAML context 검증에 좋음 |
| [supabase/supabase](https://github.com/supabase/supabase) | TypeScript/Next.js, config, database-centric project shape | frontend/backend TS slice, config, SQL 또는 migration-like fixture | TypeScript와 product/config routing 검증에 좋음 |
| [NVIDIA/cuda-samples](https://github.com/NVIDIA/cuda-samples) | CUDA targeted regression | stream/sync/memory/kernel launch 관련 최소 diff | CUDA는 별도 targeted smoke로 두는 편이 좋음 |
| [realworld-apps/realworld](https://github.com/realworld-apps/realworld) | 같은 product를 여러 framework/language로 구현한 예제 탐색 | 특정 framework 구현 1-2개에서 최소 diff 추출 | 직접 smoke보다 후보 탐색 corpus 성격이 강함 |

## Fixture Manifest

외부-derived fixture는 manifest를 반드시 가진다.

제안 경로:

```text
ops/fixtures/review_smoke/external_sources.yaml
ops/fixtures/review_smoke/curated-polyglot/
ops/fixtures/review_smoke/cuda-targeted/
review-engine/examples/external_multilang_diffs/
```

manifest 필드 예시:

```yaml
fixtures:
  - fixture_id: curated-polyglot-otel-demo
    source_repo: https://github.com/open-telemetry/opentelemetry-demo
    source_ref: "<pinned commit sha>"
    license: Apache-2.0
    imported_paths:
      - src/example-service/example.go
      - kubernetes/example.yaml
      - docker-compose.yml
    stored_paths:
      - ops/fixtures/review_smoke/curated-polyglot-otel-demo/
    transformations:
      - reduced to minimal review diff
      - removed generated files and large assets
    expected_languages:
      - go
      - yaml
      - dockerfile
    expected_contexts:
      - kubernetes
      - docker
    smoke_tier: targeted
```

## Fixture Layout

각 fixture는 baseline branch와 feature branch를 재현할 수 있어야 한다.

제안 layout:

```text
ops/fixtures/review_smoke/
  curated-polyglot/
    manifest.yaml
    base/
    feature/
    expected_smoke.json
  cuda-targeted/
    manifest.yaml
    base/
    feature/
    expected_smoke.json
```

`expected_smoke.json`에는 최소한 아래를 둔다.

```json
{
  "fixture_id": "synthetic-mixed-language",
  "default_project_ref": "root/review-system-multilang-smoke",
  "expected_language_tags": ["yaml", "python", "sql"],
  "expected_engine_languages": ["yaml", "python", "sql"],
  "expected_engine_rules": {
    ".gitlab-ci.yml": ["YAML.CI.6"],
    "api/routes/items.py": ["PY.FAPI.1"]
  },
  "forbidden_language_tags": ["cpp"],
  "minimum_review_comments": 1,
  "required_paths": [".gitlab-ci.yml", "api/routes/items.py"],
  "wrong_language_feedback": {
    "detected_language_id": "yaml",
    "expected_language_id": "markdown",
    "reply_body": "@review-bot wrong-language markdown"
  }
}
```

## 구현 계획

### Phase 1. 이름과 역할 정리

- `smoke_local_gitlab_tde_review.sh`는 유지한다.
- 새 alias `smoke_local_gitlab_lifecycle_review.sh`를 추가한다.
- docs와 runbook에서는 lifecycle smoke라는 역할명을 우선 사용한다.
- 기존 TDE setup 문서는 compatibility / legacy fixture 문맥으로 남긴다.

### Phase 2. Fixture Manifest 도입

- `ops/fixtures/review_smoke/`를 추가한다.
- synthetic fixture와 external-derived fixture를 같은 manifest 구조로 설명한다.
- 아직 외부 코드를 vendoring하지 않아도 manifest schema와 README를 먼저 고정한다.
- smoke script는 `--fixture <fixture-id>`로 fixture profile을 고를 수 있게 한다.
- `expected_smoke.json`을 script와 engine-only test가 함께 읽어
  required/forbidden language tag, 최소 comment 수, optional wrong-language feedback target을 검증한다.

### Phase 2.5. Engine-Only Fixture Contract Validator

GitLab smoke를 매번 돌리지 않아도 fixture가 깨졌는지 빠르게 볼 수 있어야 한다.
따라서 `ops/fixtures/review_smoke/*/expected_smoke.json`은
`review-engine` 테스트에서 repo-local contract로도 검증한다.

검증 범위:

- `base/`, `feature/`, `expected_smoke.json` 경로 존재
- expected language tag가 실제 feature 파일 확장자 또는 review path와 충돌하지 않는지 확인
- `expected_engine_languages`가 있으면 publish contract와 engine/detect fixture 언어를 분리해서 확인
- markdown 같은 non-reviewable path가 required tag에 들어가지 않았는지 확인
- fixture가 legacy organization-specific corpus를 다시 참조하지 않는지 확인
- CUDA targeted fixture는 최소 하나 이상의 `cuda` engine language contract를 가진다.

### Phase 3. Curated Polyglot Fixture 추가

- 1차 repo-local fixture는 `curated-polyglot`으로 추가한다.
- 외부-derived slice의 1순위는 OpenTelemetry Demo 또는 Google microservices-demo에서 작은 slice를 만든다.
- smoke 대상은 Dockerfile, YAML, service code, config 조합으로 제한한다.
- fixture는 base/feature diff가 명확해야 한다.
- expected smoke contract는 language tag와 forbidden tag 중심으로 시작한다.
- engine-only contract는 Go, Dockerfile, Kubernetes YAML의 representative rule을 함께 고정한다.

### Phase 4. CUDA Targeted Fixture 추가

- NVIDIA cuda-samples를 source corpus로 삼되,
  실제 fixture는 최소 CUDA diff로 축소한다.
- CUDA fixture는 mixed-language smoke에 바로 섞기보다 targeted smoke로 먼저 둔다.
- CUDA language tag, profile routing, sync/stream/kernel 관련 rule hit를 확인한다.

### Phase 5. Provider Comparison 선택 실행

- deterministic smoke는 `stub/stub`로 유지한다.
- 실제 provider 비교는 별도 flag 또는 별도 script로 둔다.
- 결과는 release gate가 아니라 tuning backlog로 저장한다.

## 완료 기준

- TDE 이름에 의존하지 않는 lifecycle smoke entrypoint가 있다.
- mixed-language smoke가 fixture profile을 선택할 수 있다.
- 외부-derived fixture를 추가할 때는 source repo, pinned ref, license, imported path,
  transformation을 추적한다.
- daily smoke는 외부 네트워크 없이 통과한다.
- curated polyglot fixture에서 최소 3개 이상의 language/context 축을 검증한다.
- CUDA targeted fixture에서 CUDA language/profile routing을 검증한다.
- wrong-language telemetry와 smoke output이 fixture별로 비교 가능하다.

## 리스크와 대응

| 리스크 | 대응 |
| --- | --- |
| 외부 저장소가 바뀌어 smoke가 흔들림 | smoke 시점에는 live fetch 금지, pinned SHA와 vendored minimal fixture 사용 |
| 라이선스 / attribution 누락 | manifest에 license와 source URL 필수화 |
| fixture가 너무 커져 smoke가 느려짐 | 최소 diff만 저장하고 full project vendoring 금지 |
| expected finding이 provider에 따라 흔들림 | daily smoke는 language tag/routing 중심, provider 품질은 별도 comparison으로 분리 |
| 오픈소스 fixture가 실제 운영 도메인과 다름 | synthetic fixture와 external-derived fixture를 함께 유지 |
| CUDA fixture가 일반 mixed-language smoke를 느리게 함 | CUDA는 targeted smoke에서 먼저 안정화한 뒤 필요 시 mixed smoke에 일부 편입 |

## 관련 문서

- `docs/REVIEW_ENGINE_MULTI_LANGUAGE_FOLLOWUP_OPTIMIZATION_PLAN.md`
- `docs/REVIEW_ENGINE_EVALUATION_HARNESS.md`
- `docs/REVIEW_ENGINE_CUDA_NATIVE_CAPABILITY_EXPANSION_PLAN.md`
- `docs/REVIEW_BOT_WRONG_LANGUAGE_TELEMETRY_OPERATIONS.md`
- `docs/GITLAB_TDE_REVIEW_SETUP.md`
- `ops/README.md`
