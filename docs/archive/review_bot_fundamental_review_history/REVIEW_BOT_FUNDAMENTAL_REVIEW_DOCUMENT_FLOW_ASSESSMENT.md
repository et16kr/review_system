# Review Bot Fundamental Review Document Flow Assessment

- 문서 상태: Assessment
- 작성일: 2026-04-21
- 작성 목적: `REVIEW_BOT_FUNDAMENTAL_REVIEW` 계열 문서들의 생성 흐름이
  실제로 개선 방향으로 수렴하고 있는지, 아니면 같은 쟁점을 반복 왕복하고 있는지 평가한다.
- 관련 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V3.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V3_META_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V4.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V4_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V5.md`

## 0. 결론 요약

이 문서 흐름은 **제자리걸음은 아니다**.
전체적으로는 분명히 좋아지고 있으며, 큰 방향은 상당 부분 수렴했다.

다만 모든 축이 매끄럽게 전진한 것은 아니다.
특히 **KPI / baseline / measurement model** 영역에서는
한동안 같은 문제를 더 정밀하게 다시 건드리느라
"핑퐁처럼 보이는 왕복"이 실제로 있었다.

최종 판단은 아래와 같다.

- 구조와 제품 방향은 점점 더 명확해졌고, 상호 수렴했다.
- 문서의 사실성도 점차 좋아졌다.
- 측정 체계는 중간에 흔들렸지만, V5에서 상당 부분 바로잡혔다.
- 따라서 전체 흐름은 **"부분적 재논쟁을 포함한 점진적 수렴"** 으로 보는 것이 가장 정확하다.

## 1. 지금 흐름은 제자리걸음인가?

아니다.
적어도 아래 세 가지 기준으로 보면 전진이 있었다.

1. **핵심 구조 판단이 계속 유지되었다**
   - `detect -> publish -> sync`
   - inline-first
   - fingerprint 중심 backlog / learning
   - feedback-aware review loop

2. **초기 문서의 부정확한 부분이 계속 보정되었다**
   - `resolved_reason` vs `resolution_reason`
   - stale한 SQLite 진술
   - 외부 벤더 수치 사용 방식
   - 현재 코드에 실제 존재하는 상태값과 설계 후보값의 구분

3. **문서가 점점 더 실행 기준 문서에 가까워졌다**
   - trigger model 명시
   - baseline-first 원칙
   - `.review-bot.yaml`의 성격 정리
   - condition-based defer
   - KPI naming 정교화
   - 운영 계측과 품질 분석의 분리

즉, "같은 얘기를 반복만 했다"기보다
초기에는 큰 방향을 잡고,
중간에는 설계 전제를 정리하고,
후반에는 측정 모델을 바로잡는 식으로 문서의 밀도가 올라갔다.

## 2. 실제로 수렴한 내용

아래 항목들은 버전이 바뀌어도 뒤집히지 않았고,
오히려 더 명시적으로 굳어졌다.

### 2.1 제품 / 구조 방향

- `review-bot`의 현재 골격은 유지할 가치가 있다.
- 가장 큰 기술 부채는 verify phase와 measurement다.
- context / retrieval 강화는 필요하지만 verify보다 앞서지 않는다.
- UX / command / automation은 그 다음 단계다.

### 2.2 트리거 모델

- 현재 시스템은 note mention 기반 수동 호출형으로 본다.
- MR hook은 있어도 즉시 자동 리뷰 게시가 아니라
  metadata refresh / sync / optional walkthrough trigger 성격으로 다룬다.
- 자동 inline publish는 baseline 확보 전에는 금지 또는 후순위로 본다.

### 2.3 설정 수렴 방향

- `.review-bot.yaml`은 기능 확장이 아니라 설정 수렴으로 본다.
- `policy.json`을 즉시 제거하는 방식보다 점진 migration을 선호한다.
- 충돌 규칙은 문서로 고정해야 한다는 방향이 정착되었다.

### 2.4 장기 투자 우선순위

- multi-reviewer 병렬화는 "불필요하니 버린다"가 아니라
  verify / context 개선 이후 비용-효과를 다시 보자는
  condition-based defer로 수렴했다.

## 3. 핑퐁이 실제로 있었던 지점

핑퐁처럼 보인 부분은 주로 "문서 철학"이 아니라
"측정 정의를 실제 구현 가능한 형태로 내리는 과정"에서 발생했다.

### 3.1 `acceptance_rate`의 의미

초기에는 `acceptance_rate`라는 한 단어에
아래 두 의미가 섞여 있었다.

- 해결된 것 중 실제 fix가 확인된 비율
- 게시된 것 중 실제 fix로 이어진 비율

이 문제는 이후 `fix_confirmation_rate`,
`fix_conversion_rate`로 나누는 방향으로 개선되었다.

### 3.2 baseline-first와 instrumentation 순서

문서가 baseline-first를 주장하면서도,
정작 baseline 계산에 필요한 새 metric / label / 상태값이
아직 없다는 점이 뒤늦게 문제로 드러났다.

그래서 이후 문서에서는 아래처럼 정리되었다.

- `baseline v0`
- instrumentation phase
- `baseline v1`

이건 같은 말을 반복한 것이 아니라,
측정 체계를 실제 운영 순서에 맞게 수정한 과정이다.

### 3.3 Prometheus event counter와 품질 KPI의 혼용

가장 큰 왕복은 여기였다.

중간 문서에서는 distinct finding 품질 KPI를 설명하면서도,
계산은 `findings_published_total`, `findings_resolved_total` 같은
Prometheus event counter 합계에 기대는 문제가 있었다.

하지만 현재 코드의 analytics / learning 쪽은 이미
distinct fingerprint 철학을 따르고 있다.

즉, 문서가 한동안 아래 둘을 완전히 분리하지 못했다.

- 운영 이벤트 관찰
- 품질 KPI 판단

이 문제는 V5에서 다음 원칙으로 정리되었다.

- Prometheus = 운영 이벤트
- DB / API / rollup = distinct fingerprint 기반 품질 KPI

따라서 이 구간은 "헛바퀴"라기보다
더 깊은 설계 오류가 후반에 드러나서 수정된 케이스에 가깝다.

## 4. 서로의 주장을 무시한 것인가?

강하게 "무시했다"고 볼 근거는 크지 않다.
더 정확한 표현은 아래에 가깝다.

> 핵심 지적은 대체로 반영되었지만,
> 그 지적의 의미가 다음 버전에서 끝까지 일관되게 구현되지는 않은 경우가 있었다.

### 4.1 Claude가 Codex 주장을 무시했는가?

대체로 아니었다.

예를 들어 아래는 이후 문서들에서 실제로 흡수되었다.

- trigger model 명시
- baseline-first 원칙
- `resolution_reason` 명칭 일관화
- `.review-bot.yaml`의 설정 수렴 관점
- condition-based defer

다만 KPI 영역에서는 "문제 의식은 수용했지만
계산 모델까지 완전히 바꾸지는 못한" 사례가 있었다.
V4가 여기에 해당한다.

### 4.2 Codex가 Claude 주장을 무시했는가?

이 역시 대체로 아니었다.

아래 항목들은 이후 평가와 통합 문서에서 계속 수용되었다.

- baseline을 절대 목표치보다 개선폭 중심으로 보자는 관점
- config migration을 점진적으로 가져가자는 관점
- label value set과 충돌 규칙을 명시해야 한다는 관점
- 문서 내부 일관성을 높여야 한다는 메타 평가 관점

즉, 양쪽은 서로 다른 축을 더 강하게 본 적은 있어도,
핵심 주장을 배척하면서 역행한 것은 아니다.

## 5. 버전별로 보면 무엇이 좋아졌는가

### 5.1 원본 → Evaluation / Enhanced

- 사실 오류와 표현 부정확성을 짚기 시작했다.
- trigger model, field naming, stale observation 같은
  기본 전제를 정리하기 시작했다.

### 5.2 Enhanced / Meta → V2 / V3

- baseline-first 원칙이 들어왔다.
- trigger model이 문서 전제로 고정되었다.
- `resolution_reason` 현재값과 설계 후보를 분리하는 방향이 생겼다.
- `.review-bot.yaml`을 설정 수렴으로 본다는 관점이 명확해졌다.

### 5.3 V3 / V3 Meta → V4

- config conflict rule,
  verify metric label set,
  condition-based defer가 더 구체화되었다.
- 하지만 KPI source 모델은 여전히 흔들렸다.

### 5.4 V4 → V5

- 가장 중요한 측정 모델 correction이 일어났다.
- 운영 지표와 품질 KPI가 드디어 분리되었다.
- conversion KPI를 cohort 기반 analytics로 봐야 한다는 점이 반영되었다.
- current code의 fingerprint 철학과 문서 KPI 정의가 더 잘 맞게 되었다.

## 6. 현재 시점의 판단

현재 기준으로는 `V5`가 가장 적절한 통합 문서다.

이 판단의 이유는 아래와 같다.

- 구조 방향을 유지한다.
- 기존 문서들의 좋은 판단을 대부분 흡수한다.
- 중간 버전에서 흔들린 KPI / analytics 문제를 보정한다.
- current code와 measurement model의 정합성이 가장 높다.

즉, 지금은 "문서가 계속 흔들린다"기보다
"핵심 논쟁점이 거의 정리되어, 실행 기준 문서를 하나로 수렴시킬 수 있는 상태"에 더 가깝다.

## 7. 아직 남아 있는 위험

문서 흐름이 좋아졌다고 해서
이제 아무 쟁점도 없다는 뜻은 아니다.

남은 위험은 주로 아래와 같다.

1. **정책 제안과 현재 구현 사실이 다시 섞일 위험**
   - 예: `.review-bot.yaml` 우선순위는 아직 설계 결정이지 현재 코드 사실은 아니다.

2. **합의된 원칙이 다음 문서에서 다시 느슨해질 위험**
   - 예: 품질 KPI를 다시 event counter 비율로 단순화하는 회귀

3. **open issue와 closed issue가 섞여 다시 왕복할 위험**
   - 이미 결정된 것과 아직 논의 중인 것을 문서가 분리하지 않으면
     비슷한 메타 평가가 반복될 수 있다.

## 8. 앞으로 제자리걸음을 막는 방법

다음 단계에서 가장 효과적인 장치는
새로운 긴 통합 문서를 계속 쓰는 것보다
"이미 합의된 원칙"을 고정하는 짧은 decision log를 두는 것이다.

권장 규칙:

1. 이미 합의된 사항은 `decision log`에 고정한다.
2. 새 버전 문서는 open issue와 변경분만 다룬다.
3. 각 주장에 `code-verified` / `design-inference` / `market-informed` 표시를 유지한다.
4. 새 통합 문서는 "이전 버전에서 무엇을 유지했고, 무엇을 바꿨는가"를 명시한다.

이렇게 하면 같은 문제를 매번 처음부터 다시 논쟁하지 않게 된다.

## 9. 최종 판단

이 문서 흐름은 **점점 더 완전해지고 있다**.
다만 그 과정이 항상 직선형은 아니었고,
측정 체계 쪽에서는 실제로 몇 차례 재논쟁이 있었다.

그래도 전체적으로 보면:

- 서로의 핵심 주장을 대체로 흡수해 왔다.
- 구조 방향은 안정적으로 수렴했다.
- 가장 어려웠던 KPI / measurement 문제도 V5에서 상당 부분 정리되었다.

따라서 이 흐름은
**"서로 무시하며 제자리걸음"** 이 아니라,
**"부분적 핑퐁을 거친 점진적 수렴"** 으로 평가하는 것이 타당하다.
