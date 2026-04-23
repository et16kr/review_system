# Review Engine Rule Expansion Plan

## 목적

이 문서는 현재 멀티 랭귀지 rule corpus가 닫힌 뒤,
언어별 rule 수를 더 늘릴지 판단하는 기준과 실행 순서를 정리한다.

핵심 결론은 아래와 같다.

- 현재 seed source bundle 기준 core canonicalization은 완료 상태다.
- 따라서 rule 보강은 최적화의 선행조건이 아니다.
- rule 보강은 새 source/corpus를 늘리는 범위 확장 작업이다.
- 최적화는 현재 corpus의 ranking, provider phrasing, comment density를 안정화하는 작업이다.
- rule 보강을 하면 그 뒤에는 반드시 최적화 루프로 다시 흡수한다.

즉 실행 순서는 기본적으로 아래와 같다.

1. 현재 corpus 기준 최적화와 운영 telemetry를 먼저 안정화한다.
2. 얇은 언어만 targeted rule expansion으로 보강한다.
3. 새 rule이 들어간 언어는 ranking / smoke / provider 품질을 다시 튜닝한다.

## 현재 기준

현재 `rule_sources/coverage_matrix.yaml` 기준으로 모든 source atom은
`mapped` 또는 `reference_only`로 분류되어 있고 `pending`은 없다.

따라서 아래 숫자는 "공식 가이드라인 전체 대비 완성도"가 아니라
"현재 커밋된 seed source bundle 대비 적절성"으로 해석한다.

| 언어 | source atoms | 고유 rule 수 | 판단 | 다음 액션 |
|---|---:|---:|---|---|
| `cpp` | 8 | 54 | 충분 | rule 추가보다 ranking / false-positive 튜닝 우선 |
| `c` | 7 | 16 | 적절 | POSIX/C safety blind spot이 보일 때만 보강 |
| `cuda` | 46 | 54 | 충분 | capability별 ranking / phrasing / duplicate density 튜닝 우선 |
| `python` | 13 | 28 | 적절 | 운영 샘플 기반으로 Django/FastAPI blind spot만 선택 보강 |
| `typescript` | 14 | 26 | 적절 | React/Next.js ranking과 provider phrasing 튜닝 우선 |
| `javascript` | 9 | 19 | 보강 여지 | browser/runtime/security 일반 rule 보강 후보 |
| `java` | 10 | 19 | 보강 여지 | concurrency/resource/API boundary rule 보강 후보 |
| `go` | 6 | 12 | 얇음 | 우선 보강 후보 |
| `rust` | 9 | 17 | 보강 여지 | unsafe/FFI/pinning/error boundary 보강 후보 |
| `bash` | 7 | 14 | 적절 | shell safety 운영 샘플 기준 선택 보강 |
| `sql` | 17 | 29 | 충분 | rule 추가보다 dialect/ranking drift 튜닝 우선 |
| `yaml` | 18 | 28 | 충분 | CI/K8s/schema/product context routing 튜닝 우선 |
| `dockerfile` | 6 | 13 | 얇음 | 우선 보강 후보 |
| `shared` | 6 | 15 | 적절 | telemetry 기반 공통 security/process rule만 선택 보강 |

## 우선순위

### P0. 최적화 먼저

바로 다음 작업은 broad rule expansion이 아니다.
현재 corpus로 아래를 먼저 안정화한다.

- wrong-language telemetry 운영 루프
- provider phrasing / draft normalization 품질
- retrieval / ranking calibration
- comment density / duplicate suppression
- mixed-language smoke와 evaluation snapshot

이유는 rule을 더 추가하면 top-k ranking과 comment density가 다시 흔들리기 때문이다.
현재 corpus의 품질 기준을 먼저 고정해야 이후 rule expansion 효과를 분리해서 볼 수 있다.

### P1. 얇은 언어 targeted expansion

최적화 기준이 잡힌 뒤 가장 먼저 보강할 언어는 아래다.

1. `go`
   - error wrapping / sentinel error / context cancellation
   - goroutine lifecycle / channel ownership
   - HTTP handler boundary validation
   - database transaction and resource cleanup

2. `dockerfile`
   - multi-stage runtime hardening
   - non-root runtime user
   - BuildKit secret mount
   - digest pinning / provenance / SBOM-friendly build
   - package manager cache and layer hygiene

P1은 "많이 늘리기"가 아니라,
자동 리뷰에서 실제 defect claim으로 이어질 high-signal rule만 추가한다.

### P2. 선택적 보강

다음 언어는 운영 telemetry나 expected examples에서 blind spot이 확인될 때 보강한다.

- `javascript`
  - browser DOM trust boundary
  - fetch / abort / promise rejection ownership
  - module side effect and runtime config boundary
- `java`
  - executor/thread lifecycle
  - resource cleanup and transaction boundary
  - serialization/deserialization trust boundary
- `rust`
  - unsafe block justification
  - FFI ownership boundary
  - pinning / async cancellation
  - error conversion and panic boundary

### P3. 성숙 언어는 telemetry-driven only

아래 언어는 rule 수 자체보다 정확도와 순위 안정성이 더 중요하다.

- `cpp`
- `cuda`
- `sql`
- `yaml`
- `python`
- `typescript`
- `c`
- `bash`

새 rule은 반복되는 blind spot이 운영 데이터로 확인될 때만 추가한다.
그 외에는 ranking, trigger pattern, provider phrasing, smoke fixture를 먼저 조정한다.

## Rule Expansion 수용 기준

새 rule bundle은 아래 항목을 한 묶음으로 닫아야 한다.

1. source 문서 추가 또는 기존 source 문서 갱신
2. `coverage_matrix.yaml` source atom 추가
3. canonical pack/profile/policy YAML 추가 또는 갱신
4. query detector pattern과 hinted rule 연결
5. expected example 또는 targeted regression 추가
6. 필요하면 prompt profile/context 추가
7. `ingest_guidelines` 결과 확인
8. `review-engine` 전체 테스트 통과
9. bot publish 흐름에 영향이 있으면 `review-bot` 테스트와 smoke 재검증

source atom이 추가됐는데 canonical rule, detector, example 중 하나가 빠지면
그 rule expansion은 완료로 보지 않는다.

## 최적화 문서와의 관계

이 문서는 `docs/REVIEW_ENGINE_MULTI_LANGUAGE_FOLLOWUP_OPTIMIZATION_PLAN.md`와 분리한다.

- 이 문서:
  - 새 rule source/corpus를 늘릴지 판단한다.
  - 언어별 보강 우선순위를 관리한다.
  - 새 rule 추가의 완료 기준을 정의한다.
- 최적화 문서:
  - 이미 들어온 corpus의 ranking, provider phrasing, comment density를 튜닝한다.
  - wrong-language telemetry와 smoke를 운영 회귀 방지 루프로 고정한다.

rule expansion이 끝난 언어는 다시 최적화 문서의 검증 루프로 들어간다.

## 검증 계획

기본 검증은 아래를 유지한다.

```bash
cd review-engine && uv run python -m review_engine.cli.ingest_guidelines
cd review-engine && uv run pytest -q
cd review-bot && uv run pytest -q
cd review-platform && uv run pytest tests/test_pr_flow.py -q
```

bot publish나 language routing에 영향이 있으면 아래도 실행한다.

```bash
bash ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture synthetic-mixed-language
```

GitLab lifecycle 또는 sync에 영향이 있으면 아래까지 실행한다.

```bash
bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

## 현재 결론

지금 당장 rule 보강이 최적화보다 우선은 아니다.

권장 순서는 아래다.

1. 현재 corpus 기준 최적화와 telemetry 운영 루프를 먼저 고정한다.
2. `go`, `dockerfile`을 targeted expansion 후보로 준비한다.
3. `javascript`, `java`, `rust`는 운영 blind spot이 확인될 때 선택 보강한다.
4. `cpp`, `cuda`, `sql`, `yaml`은 rule 추가보다 ranking과 provider 품질 튜닝을 우선한다.
