# Review Bot Fundamental Review Evaluation

- 문서 상태: Review / Assessment
- 작성일: 2026-04-21
- 대상 문서: `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
- 대상 독자: 구현 담당자, 설계 의사결정자, AI agent
- 관련 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
  - `docs/REVIEW_BOT_BACKLOG_ANALYTICS_AND_COMMAND_UX_DESIGN.md`
  - `docs/REVIEW_BOT_REDESIGN_DESIGN.md`

## 0. 평가 요약

`docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`는 방향성 측면에서는 유효하다.
특히 현재 `review-bot`의 구조를 "inline-first, lifecycle-aware, feedback-aware" 시스템으로 파악한 점과,
다음 투자 우선순위를 "신뢰도 -> context -> actionability"로 잡은 점은 설계적으로 설득력이 있다.

다만 현재 저장소 기준으로 보면, 이 문서는 아직 "구현 기준 문서"보다는
"토론용 전략 메모"에 가깝다.
아래 네 가지 보정이 필요하다.

1. 현재 시스템의 트리거 모델이 note mention 중심이라는 전제가 빠져 있다.
2. 테스트 SQLite 관련 지적 중 일부는 이미 해결되어 stale finding이 되었다.
3. 경쟁 제품 비교 수치 상당수가 vendor self-report이므로 의사결정 근거로 쓸 때 주의가 필요하다.
4. 일부 용어와 스키마 필드명이 실제 코드와 다르게 적혀 있다.

결론적으로 원문은 "방향성 검토 자료"로는 타당하지만,
그대로 실행 로드맵의 기준 문서로 삼기에는 보완이 필요하다.

## 1. 평가 기준

이번 평가는 아래 세 층위로 나누어 판단한다.

- `code-verified`
  - 현재 저장소 코드와 직접 대조해 사실 여부를 확인할 수 있는 주장
- `design-inference`
  - 코드와 제품 구조를 바탕으로 해석할 수 있으나, 일부는 설계자의 의도를 추론한 주장
- `market-informed`
  - 외부 제품 문서/블로그/벤더 주장에 의존하는 비교나 벤치마크

원문은 세 층위가 섞여 있는데, 이를 명시적으로 분리하지 않아
"확인된 사실"과 "시장 참고치"가 같은 무게로 읽힐 위험이 있다.

## 2. 원문이 잘 짚은 부분

### 2.1 현재 구조에 대한 진단

아래 항목은 현재 코드와 대체로 잘 맞는다.

- `detect -> publish -> sync` 파이프라인 분리
  - `review_bot.worker`, `review_bot.bot.review_runner`
- `ThreadSyncState`를 중심으로 한 backlog / current-state 모델
  - `review_bot.bot.review_runner._current_backlog_entries`
- thread reply 기반 feedback command 수용
  - `ignore`, `false-positive`, `later`, `allow`
- 단일 파일 중심 context 주입
  - `file_context` 최대 4000자
- score 기반 severity 계산
  - 현재는 `low / medium / high`
- rule-level effectiveness weight
  - 현재는 `rule_no` 단위 global weight
- process-local webhook rate limit
  - 메모리 `deque` 기반
- C/C++ 중심 review scope
  - `CPP_EXTENSIONS` 기준

즉, 원문이 말하는 "현재 구조의 골격"은 과장이라기보다 대체로 코드 기반 관찰에 가깝다.

### 2.2 방향성 판단

아래 판단도 타당하다.

- 검증 phase 부재가 신뢰도 측면의 핵심 부채라는 지적
- context retrieval이 현재 파일 중심이라는 지적
- severity와 score를 분리해야 한다는 문제 제기
- per-project 학습 단위가 필요하다는 제안
- walkthrough / ask / apply 같은 actionability 강화가 다음 단계라는 판단

특히 "엔진을 더 복잡하게 만드는 것"보다
"검증, context, actionability"를 우선하자는 결론은 현재 코드베이스 상태에 잘 맞는다.

## 3. 보정이 필요한 지점

### 3.1 트리거 모델 전제가 빠져 있다

원문은 acceptance tracking, MR 오픈 시 walkthrough 자동 게시, follow-up commit 추적 같은 기능을
비교적 바로 붙일 수 있는 것처럼 서술한다.
하지만 현재 구현은 아래와 같은 명확한 제약을 가진다.

- GitLab webhook 진입점은 존재하지만,
  `Merge Request Hook`은 의도적으로 무시한다.
- 실제 review run 생성은 note mention 기반이다.
- 즉, 현재 시스템은 "always-on background reviewer"가 아니라
  "explicitly summoned reviewer"에 가깝다.

이 제약은 아래 제안의 난이도와 선행 과제를 바꾼다.

- acceptance metric의 freshness
- MR 오픈 시 walkthrough 자동 게시
- commit 기반 추적 시점 정의
- sync phase가 언제 얼마나 자주 실행되는가

따라서 원문의 Phase A / C 일부는 기능 추가가 아니라
"이벤트 모델 변경"이 선행되는 작업으로 재정의되어야 한다.

### 3.2 테스트 SQLite finding은 stale하다

원문은 "테스트가 공유 SQLite라 병렬 CI에 취약하다"는 한계를 적었다.
하지만 현재 테스트 설정은 이미 worker/process별 SQLite 파일을 사용한다.

- `review-bot/tests/conftest.py`에서 `BOT_DATABASE_URL`을 worker-scoped로 설정

즉, 이 항목은 과거 시점의 설계 우려로는 의미가 있었지만,
현재 저장소 기준 "미해결 문제"로 남겨두면 오해를 만든다.

이 지점은 다음처럼 고쳐 쓰는 편이 적절하다.

- 기존 문제는 해결됨
- 남은 과제는 "per-test transaction isolation"이나
  "더 빠른 병렬 fixture 전략" 정도로 축소됨

### 3.3 외부 벤치마크 수치의 증거 강도가 약하다

원문은 Greptile, Diamond, Bugbot, CodeRabbit 등을 비교하면서
catch rate, false positive, resolution rate 같은 수치를 적극적으로 인용한다.

이 자체가 잘못은 아니지만, 대부분이 아래 유형이다.

- vendor documentation
- vendor blog
- vendor interview/홍보성 정리글
- 2차 요약 자료

따라서 이런 수치는 아래처럼 다뤄야 한다.

- 방향성 참고치로는 사용 가능
- 내부 KPI 목표의 직접 근거로는 사용 금지
- 문서 내에서 "self-reported" 또는 "market claim"이라고 명시

원문처럼 수치를 강한 근거처럼 배치하면,
내부 제품의 KPI 설계가 시장 홍보 수치에 끌려갈 수 있다.

### 3.4 용어와 스키마 필드명이 일부 어긋난다

원문은 `resolved_reason`이라는 표현을 사용하지만,
현재 모델 필드는 `resolution_reason`이다.

이 차이는 사소해 보이지만 설계 문서에서는 중요하다.
DB migration, metrics label, API payload를 구현하는 시점에 그대로 혼선을 만든다.

문서에서는 아래 중 하나로 통일해야 한다.

- 현재 구현 용어인 `resolution_reason` 유지
- 새 용어를 쓰고 싶다면, 변경 의도를 별도 migration 항목으로 명시

### 3.5 "요약 부재"보다는 "요약이 제한적"이 더 정확하다

원문은 walkthrough 부재를 지적하는데,
현재 구현에는 run-level summary note 자체는 존재한다.
다만 이것은 아래 성격이다.

- 게시된 finding 요약 중심
- 변경 이유 설명이나 symbol 영향 분석은 없음
- same-purpose upsert가 아니라 append-only

따라서 원문의 문제의식은 맞지만, 표현은 아래처럼 보정하는 편이 정확하다.

- "요약이 없다"가 아니라
- "현재 summary note는 존재하지만 walkthrough 역할을 하지는 못한다"

## 4. 활용 권고

현재 기준으로 원문을 활용하는 방법은 아래가 적절하다.

### 4.1 그대로 유지해도 되는 역할

- 구조 점검용 배경 문서
- 경쟁 제품 동향을 빠르게 훑는 전략 메모
- 다음 투자 영역을 거칠게 정렬하는 자료

### 4.2 그대로 구현 기준으로 쓰면 안 되는 역할

- 상세 실행 로드맵의 기준 문서
- KPI 수치의 직접 근거
- 스키마/필드 변경의 authoritative source

### 4.3 권장 후속 조치

- 원문은 그대로 두고, 평가 문서와 보강 문서를 companion으로 추가
- 구현 우선순위는 보강 문서를 기준으로 재정렬
- 외부 수치는 "market-informed" 부록으로 격하
- note-triggered 구조와 auto-triggered 구조를 명시적으로 분리해서 기술

## 5. 최종 판단

`docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`는
"현재 방향이 완전히 틀렸는가?"라는 질문에는 `아니오`라고 답할 수 있는 문서다.
오히려 핵심 구조 진단과 큰 방향은 꽤 잘 맞는다.

하지만 "지금 바로 구현팀이 따라야 할 기준 문서인가?"라는 질문에는
아직 `부분적으로만`이라고 보는 것이 맞다.

현재 저장소 기준 최종 평가는 아래와 같다.

- 방향성 타당성: 높음
- 사실관계 정확도: 대체로 높음, 일부 stale finding 존재
- 실행 기준 문서로서의 완성도: 중간
- 외부 비교 근거의 엄밀성: 보강 필요

따라서 원문은 폐기할 문서가 아니라,
"방향성은 유지하되 실행 기준은 보강 문서로 넘겨야 하는 문서"로 평가한다.
