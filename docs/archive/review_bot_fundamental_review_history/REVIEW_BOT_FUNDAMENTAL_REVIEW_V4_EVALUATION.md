# Review Bot Fundamental Review V4 Evaluation

- 문서 상태: Assessment
- 작성일: 2026-04-21
- 대상 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V3_META_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V4.md`
- 관련 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V3.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V4.md`

## 0. 평가 요약

`REVIEW_BOT_FUNDAMENTAL_REVIEW_V3_META_EVALUATION.md`는 유효한 메타 평가 문서다.
특히 V3의 label migration 의존, `.review-bot.yaml` 충돌 규칙, verify metric label set,
조건부 defer 기준을 짚은 점은 실제로 도움이 된다.

`REVIEW_BOT_FUNDAMENTAL_REVIEW_V4.md`도 V3보다 한 단계 더 좋아진 문서다.
하지만 아직 그대로 "Current — 실행 기준 문서"로 고정하기에는 부족하다.

핵심 이유는 하나다.

> V4는 KPI의 **정의는 distinct finding 품질 지표**로 설명하면서,
> 실제 계산식은 **Prometheus event counter 합계**에 기대고 있다.

이 불일치는 단순 문장 문제가 아니라 측정 체계를 잘못 설계하게 만든다.

최종 판단은 아래와 같다.

- `V3_META_EVALUATION`: 유효, 유지 가치 높음
- `V4`: 방향은 적절하지만 KPI/analytics 설계가 아직 합당하지 않음
- 다음 통합본은 `V4`를 버리는 것이 아니라,
  **운영 이벤트 계측(Prometheus)** 과 **품질 KPI 분석(DB/distinct fingerprint)** 을 분리하는 방향으로 고쳐야 한다

## 1. `V3_META_EVALUATION` 평가

### 1.1 잘된 점

- V3가 V2보다 나아진 이유를 구조적으로 설명했다.
- label migration, severity taxonomy migration, `.review-bot.yaml` 충돌 규칙,
  `verify_dropped_total{mode}` value set, multi-reviewer defer 조건 같은
  "놓치기 쉬운 구현 전제"를 잘 드러냈다.
- V4에서 보강해야 할 체크리스트 역할을 충분히 한다.

### 1.2 한계

`V3_META_EVALUATION`은 아래 두 가지를 놓쳤다.

1. **Counter를 raw sum으로 나누는 KPI 설계 문제**
   - Prometheus counter는 누적값이므로 KPI는 보통 `increase()` 또는 recording rule window로 계산해야 한다.
2. **event counter와 distinct finding KPI의 의미 차이**
   - `findings_published_total` / `findings_resolved_total`은 lifecycle event counter이고,
     문서가 말하는 acceptance / conversion은 distinct fingerprint 기반 품질 지표다.

즉, `V3_META_EVALUATION`은 V3의 "문서 내부 일관성"은 잘 잡았지만,
V4로 넘어갈 때 필요한 "측정 모델 자체의 적합성"까지는 충분히 보지 못했다.

## 2. `V4`가 잘한 점

### 2.1 문서 구조

- trigger model이 명확하다.
- `resolution_reason` 현재값과 추가 후보를 구분한다.
- baseline-v0 / instrumentation / baseline-v1의 순서를 유지한다.
- `.review-bot.yaml` vs `policy.json` 충돌 정책을 문서화했다.
- multi-reviewer 병렬화를 폐기하지 않고 조건부 defer로 남겼다.

### 2.2 실행 전제 정리

- `findings_resolved_total` label 확장이 선행 의존이라는 점을 명시했다.
- 새 severity taxonomy가 없으면 `signal_ratio` PromQL이 유효하지 않다는 경고를 달았다.
- `feedback_commands_total{command}`와 `verify_*{mode,...}`의 label 집합을 닫힌 값으로 제한했다.

이 부분들은 V3보다 분명히 좋아졌다.

## 3. `V4`의 핵심 문제

### 3.1 High — KPI 데이터 소스가 잘못 잡혀 있다

V4는 아래 KPI를 canonical하게 정의한다.

- `fix_confirmation_rate`
- `fix_conversion_rate`

그런데 계산식은 아래 Prometheus counter를 기반으로 둔다.

- `findings_published_total`
- `findings_resolved_total`

문제는 현재 코드에서 이 counter들이 **distinct finding**이 아니라
**decision row / publication event / resolution event** 단위라는 점이다.

코드 근거:

- publish 시점마다 `findings_published_total` 증가
  - [review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:599)
- resolve 시 fingerprint에 대응하는 active decision row마다 `findings_resolved_total` 증가
  - [review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1492)

반면 현재 analytics / learning 로직은 이미 distinct fingerprint를 기준으로 판단하려고 한다.

- latest meaningful state per fingerprint
  - [api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:437)
- rule weight도 fingerprint 단위로 집계
  - [review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1621)

즉, 코드베이스의 품질 판단 철학은 이미 아래다.

- **운영 이벤트는 counter**
- **품질 평가는 fingerprint**

V4는 이 둘을 다시 섞어 버렸다.
이 상태로 구현하면 KPI가 rerun, reopen, duplicate row, batch 재게시의 영향을 직접 받는다.

### 3.2 High — `fix_conversion_rate` 식이 개념적으로도 잘못됐다

V4는 `fix_conversion_rate`를 아래처럼 둔다.

- 정의: surfaced finding 중 실제 fix 비율
- 식: `fixed / (published + resolved)`

하지만 `resolved`는 대체로 과거에 이미 `published`였던 finding의 후속 lifecycle event다.
즉, `published + resolved`는 같은 finding를 두 번 세는 구조에 가깝다.

이 식은 아래 둘 중 어느 쪽으로도 해석이 어렵다.

- distinct surfaced finding 비율
- publication event 대비 fix event 비율

따라서 이 KPI는 Prometheus counter 비율로 정의할 수 없다.
새 통합본에서는 아래처럼 분리해야 한다.

- `fix_confirmation_rate(window)`
  - resolved distinct finding 중 fix evidence 확인 비율
- `fix_conversion_rate(cohort_window, sla_window)`
  - cohort 기간에 first-surfaced된 distinct fingerprint 중 SLA 안에 fixed로 전환된 비율

즉, conversion은 **cohort-based analytics**여야 한다.

### 3.3 High — counter ratio에 시간 창이 없다

V4의 PromQL은 대부분 아래 형태다.

- `sum(findings_resolved_total{...}) / sum(findings_resolved_total)`
- `sum(feedback_commands_total{...}) / sum(findings_published_total)`

하지만 Prometheus counter는 누적값이다.
운영 KPI나 baseline을 보려면 보통 일정 기간의 `increase(...)` 또는 recording rule 기반 window를 써야 한다.

시간 창이 없으면 아래 문제가 생긴다.

- 프로세스 재시작 / scrape 이력 길이 영향
- 오래된 노이즈가 현재 비율에 계속 남음
- baseline-v1 2주 측정이라는 문서 목적과 쿼리 정의가 불일치

즉, V4는 V3의 "baseline 순서 문제"는 고쳤지만,
정작 Prometheus counter를 baseline window에 맞게 쓰는 방법은 아직 고치지 못했다.

### 3.4 Medium — PromQL regex 예시가 부정확하다

V4는 아래처럼 쓴다.

- `severity=~"warning\|critical"`
- `command=~"ignore\|false-positive"`

PromQL regex 예시로는 보통 `warning|critical`처럼 쓰는 편이 맞고,
현재 표기는 불필요하거나 부정확한 escape를 포함한다.

이 문제 자체는 KPI source mismatch보다 작지만,
"실행 기준 문서"에서 그대로 복붙할 수 있는 쿼리를 제공한다는 목표에는 어긋난다.

### 3.5 Medium — fallback KPI도 여전히 proxy 이상으로 쓰기 어렵다

V4의 baseline-v0 fallback은 아래를 제안한다.

- resolve 비율 proxy
- high-priority 비중 proxy
- suppress 비율

이 자체는 나쁘지 않다.
다만 이것도 raw counter 합계를 바로 나누는 구조라
`baseline-v0 운영 관찰용 proxy`로만 제한되어야 한다.

문서에서 이 점을 더 강하게 못 박는 편이 좋다.

## 4. 우리 리뷰 봇 시스템 개선에 적절한가?

### 4.1 `V3_META_EVALUATION`

적절하다.
이 문서는 시스템 자체를 개선하는 문서라기보다
문서 품질과 설계 논리를 정리하는 데 적합하다.

### 4.2 `V4`

절반은 적절하고, 절반은 아직 아니다.

적절한 부분:

- trigger / backlog / severity / verify / context / UX 투자 순서
- label migration 전제 명시
- config conflict rule
- condition-based defer

부적절한 부분:

- canonical KPI를 Prometheus counter 비율로 설계한 부분
- cohort가 필요한 conversion KPI를 event counter로 처리한 부분
- baseline window와 query semantics를 끝까지 일치시키지 못한 부분

따라서 `V4`는 "구조와 제품 방향"은 적절하지만,
"측정 체계와 KPI 정의"는 아직 합당하지 않다.

## 5. 다음 통합본에서 해결해야 할 원칙

다음 문서는 아래 원칙을 따라야 한다.

1. **Prometheus는 운영 이벤트 계측용으로 제한**
   - publish volume
   - suppress volume
   - verify attempt/drop
   - feedback command event

2. **품질 KPI는 distinct fingerprint analytics로 계산**
   - DB / API / materialized rollup 기반
   - `latest meaningful state per fingerprint` 철학과 일치

3. **Counter KPI는 반드시 window 함수 사용**
   - `increase(...[7d])`
   - 또는 recording rule

4. **conversion KPI는 cohort 기반으로 정의**
   - first surfaced cohort
   - SLA window 내 fixed 전환

5. **Fallback proxy와 canonical KPI를 문서에서 분리**
   - proxy는 운영 관찰용
   - canonical은 품질 판단용

## 6. 최종 판단

`REVIEW_BOT_FUNDAMENTAL_REVIEW_V3_META_EVALUATION.md`는 유효하다.
`REVIEW_BOT_FUNDAMENTAL_REVIEW_V4.md`는 방향은 좋지만 아직 final current 문서로는 부족하다.

가장 중요한 이유는 아래 한 줄로 요약된다.

> V4는 `review-bot`이 이미 distinct fingerprint 기반으로 품질을 판단하고 있다는 사실을
> KPI 설계에서 끝까지 지키지 못했다.

따라서 다음 통합 문서는
**"Prometheus = 운영 이벤트" / "DB analytics = 품질 KPI"** 로 모델을 분리한 V5여야 한다.
