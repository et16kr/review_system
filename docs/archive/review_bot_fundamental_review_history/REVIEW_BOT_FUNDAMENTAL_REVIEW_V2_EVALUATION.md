# Review Bot Fundamental Review V2 Evaluation

- 문서 상태: Assessment
- 작성일: 2026-04-21
- 대상 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md`
- 관련 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md`

## 0. 평가 요약

`REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md`와
`REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md`는 앞선 세 문서보다 확실히 전진한 산출물이다.

- `META_EVALUATION`은 문서 병합 판단 근거를 잘 정리했다.
- `V2`는 실제로 "실행 기준 문서"에 가까운 구조를 만들었다.
- 특히 trigger model 명시, baseline-first 원칙, walkthrough와 run summary 분리,
  vendor self-report 경계선 설정은 모두 유효하다.

다만 `V2`는 아직 그대로 최종 기준 문서로 고정하기에는
**KPI 정의와 instrumentation 절에서 실행 순서 및 정의 일관성이 부족하다**.
핵심 문제는 아래 다섯 가지다.

1. baseline 측정 시점과 새 metric 도입 시점이 뒤섞여 있다.
2. `acceptance_rate` 정의가 문서 내부에서 서로 다르다.
3. metric 이름과 PromQL 예시가 현재 코드 계열과 어긋난다.
4. `META_EVALUATION`의 일부 표현은 "코드 검증" 범위를 넓게 말한다.
5. `V2`의 현재 상태 설명에서 `resolution_reason` 값 일부가 빠져 있다.

따라서 권장 방향은 아래와 같다.

- `META_EVALUATION`은 이력 문서로 유지
- `V2`는 보관하되 current에서 내리거나 superseded 처리
- 위 문제를 반영한 새 통합본 `V3`를 current 기준 문서로 승격

## 1. 잘된 점

### 1.1 `META_EVALUATION`

- 원본 / Evaluation / Enhanced의 장단점을 균형 있게 재평가했다.
- "원본 폐기"가 아니라 "원본의 해상도는 살리고 오류는 교정"이라는 병합 원칙이 설득력 있다.
- V2로 무엇을 가져가고 무엇을 버려야 하는지 판단 축을 제공한다.

### 1.2 `V2`

- trigger model을 Note Hook mention 중심으로 명시했다.
- 증거 층위(`code-verified`, `design-inference`, `market-informed`)를 도입했다.
- walkthrough와 run summary를 분리했다.
- `resolution_reason` 명칭을 일관되게 사용했다.
- `.review-bot.yaml`을 "기능 확장"이 아니라 "설정 수렴"으로 다뤘다.
- multi-reviewer 병렬화를 "조건부 defer"로 재정의해 이전 문서보다 균형이 좋아졌다.

## 2. 남은 문제

### 2.1 baseline과 implementation의 순서가 충돌한다

`V2`는 baseline-first를 표방하면서도,
baseline 절에서 이미 아직 존재하지 않는 분류 체계와 metric을 전제한다.

문제 예시:

- 현재 severity는 `low / medium / high`인데,
  KPI 표는 `warning / critical`을 바로 사용한다.
- 현재 `resolution_reason`에는 `fixed_in_followup_commit`가 없는데,
  baseline KPI 정의는 이를 이미 분자로 사용한다.

즉, 현재 문서 구조는 아래 둘을 동시에 요구한다.

- "Phase A 전에 baseline을 측정한다"
- "Phase A에서 baseline 계산에 필요한 새 상태와 metric을 만든다"

이 구조는 실행 시 혼선을 만든다.

올바른 흐름은 아래 둘 중 하나다.

1. `baseline-v0`
   - 현재 존재하는 metric만으로 먼저 측정
2. `instrumentation phase`
   - 새 `resolution_reason`, 새 severity 체계, 새 counter 추가
3. `baseline-v1`
   - 새 metric 기반으로 다시 짧은 soak 기간 측정

또는

1. baseline-first 원칙을 포기하고
2. 먼저 instrumentation을 넣은 뒤
3. 그 이후의 운영 데이터를 baseline으로 정의

V2는 둘 중 어느 쪽인지가 모호하다.

### 2.2 `acceptance_rate` 정의가 일관되지 않다

V2 내부에는 두 정의가 공존한다.

- KPI 표:
  - `fixed_in_followup_commit / review_comments_resolved_total`
- 상세 설계:
  - `fixed_in_followup_commit / (published + resolved)`

이 차이는 사소하지 않다.

- 전자는 "resolved된 것 중 실제 fix 근거가 확인된 비율"에 가깝다.
- 후자는 "surfaced된 것 중 실제 fix로 이어진 비율"에 가깝다.

둘 다 의미는 있지만 같은 이름을 쓰면 안 된다.
새 통합본에서는 아래처럼 분리하는 것이 바람직하다.

- `fix_confirmation_rate`
  - `fixed_in_followup_commit / resolved_total`
- `fix_conversion_rate`
  - `fixed_in_followup_commit / surfaced_total`

필요하면 `acceptance_rate`는 둘 중 하나의 alias로 두되,
문서 본문에서는 가능하면 모호한 이름을 피하는 편이 좋다.

### 2.3 metric 계열과 PromQL 예시가 구현 기준으로는 거칠다

현재 코드의 Prometheus counter는 `findings_*` 계열이다.

- `findings_published_total`
- `findings_resolved_total`
- `findings_suppressed_total`

반면 V2는 `review_comments_*` 계열을 새 기준처럼 사용한다.
이 자체는 가능하지만, 아래가 비어 있다.

- 기존 `findings_*`를 rename할지
- 새 counter를 병행 추가할지
- dashboard/query migration을 어떻게 할지

또한 PromQL 예시도 구현용 표현으로는 부정확하다.

- `severity="warning|critical"`
- `command="ignore|false-positive"`

이 표현은 예시 문맥은 이해되지만,
실제 쿼리 문서로는 regex matcher(`=~`) 또는 합산식을 써야 더 정확하다.

### 2.4 `META_EVALUATION`의 "코드 검증" 표현은 조금 과하다

`META_EVALUATION`은 5개 critique가 "코드로 모두 검증된다"고 적는다.
하지만 다섯 번째 항목인 vendor self-report 성격 지적은
코드 검증이라기보다 출처 성격 분석에 가깝다.

결론 자체는 유지해도 되지만,
표현은 아래처럼 보수적으로 쓰는 편이 낫다.

- "코드 또는 문서 출처 성격으로 검증된다"
- "코드 검증 + source analysis를 통해 수용 가능성이 확인된다"

### 2.5 `resolution_reason` 현재값 설명이 불완전하다

V2의 파이프라인 그림은 아래 값만 적는다.

- `remote_resolved`
- `no_longer_eligible`
- `anchor_changed`

하지만 현재 코드에는 아래 값도 이미 존재한다.

- `resolve_failed`
- `remote_reopened`

상태 머신 문서에서 현재값 목록이 불완전하면
후속 migration 설계에서 누락이 생길 수 있다.

## 3. 문서 수준 최종 판정

### 3.1 `META_EVALUATION`

유효하다.
이력 문서이자 병합 판단 근거 문서로 유지할 가치가 충분하다.

다만 current 실행 기준 문서가 되기보다는
"왜 V2가 그렇게 생겼는지 설명하는 평가 문서" 역할이 적절하다.

### 3.2 `V2`

매우 강한 통합본이다.
앞선 원본 / Evaluation / Enhanced보다 한 단계 더 좋은 문서다.

하지만 아래 이유로 final current 문서로 고정하기에는 이르다.

- KPI 정의 충돌
- baseline 단계 순서 불명확
- metric naming migration 미정
- 현재 상태값 문서화 누락 일부

즉, 판정은 아래와 같다.

- 방향성: 매우 좋음
- 구조: 매우 좋음
- 실행 가능성: 좋음
- 계측 정의 완성도: 추가 보강 필요

## 4. V3에서 반드시 반영할 사항

1. baseline을 `baseline-v0`와 `baseline-v1`로 분리한다.
2. `acceptance_rate`를 둘로 분해하거나, 하나의 canonical 정의로 고정한다.
3. metric 계열은 기존 `findings_*`를 확장하는 방식으로 정리한다.
4. PromQL 예시는 실제 쿼리 문법에 맞게 쓴다.
5. `resolution_reason` 현재값과 추가 후보를 구분해서 적는다.
6. `META_EVALUATION`의 방법론은 살리되,
   "코드 검증" 표현은 source analysis 포함 형태로 톤다운한다.

## 5. 권장 산출물 구성

권장 파일 구성은 아래와 같다.

| 문서 | 상태 | 역할 |
| --- | --- | --- |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW.md` | archival | 원본 방향성 메모 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md` | archival | 1차 평가 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md` | archival | 1차 보강본 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md` | archival | 2차 메타 평가 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md` | archival or superseded | 강한 통합본, 단 KPI 정의 보강 전 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_V3.md` | current | KPI/metric 정의까지 정리된 실행 기준 문서 |

## 6. 결론

이번 단계에서 가장 중요한 판단은 단순하다.

- `META_EVALUATION`은 유지한다.
- `V2`는 매우 좋지만 마지막 한 번 더 다듬어야 한다.
- 새 통합본은 "문장 보정"보다 "측정 정의 정리"가 핵심이다.

즉, 다음 문서는 방향을 다시 갈아엎는 V3가 아니라,
**V2의 KPI/metric/phase ordering 문제를 수리한 V3**여야 한다.
