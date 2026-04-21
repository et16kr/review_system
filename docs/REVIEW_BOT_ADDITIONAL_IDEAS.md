# Review Bot Additional Ideas

- 문서 상태: Active Backlog Ideas
- 작성일: 2026-04-21
- 작성 배경: 유사한 사내 리뷰 봇 사례와 현재 시스템을 비교한 뒤, 현 시점에서 추가 가치가 큰 아이디어만 정리한다.

## 1. 비교 결론

지인 사례의 큰 뼈대는 현재 시스템과 매우 비슷하다.

- 기존 Git code review UI에 bot을 붙인다.
- C++ 가이드를 수집해 ChromaDB 같은 vector DB에 넣는다.
- 변경 코드와 관련 가이드를 함께 AI에 넘겨 리뷰 코멘트나 수정 방향을 만든다.
- 한 번에 일부만 게시하고, 다음 push나 재요청에서 추가 리뷰를 이어 간다.

현재 시스템은 이 기본 아이디어를 더 운영형으로 확장한 상태에 가깝다.

- GitLab-first lifecycle과 inline thread update/reopen/resolve를 다룬다.
- 규칙 corpus를 `active`, `reference`, `excluded`로 정제해 내부 규칙을 우선한다.
- AI가 가이드를 임의로 고르기보다, retrieval/applicability/scoring이 먼저 후보를 좁히고 AI는 설명과 수정 가이드에 집중한다.
- dedupe, feedback, sync, migration, runbook, security/retention 문서까지 갖춰 운영 기준이 더 명확하다.

즉, 구조적 완성도와 운영 안정성은 현재 시스템이 더 낫다. 반면 사용자 체감 UX에서는 지인 사례가 던진 문제, 특히 "처음부터 전체를 더 보고 싶다"는 요구를 우리도 받아들일 필요가 있다.

## 2. 놓치고 있는 핵심 아이디어

### 2.1 Full Report / Backlog View

현재 시스템은 inline batch cap을 둔 운영 모델이 맞다. 다만 사용자는 "왜 이것만 보였는지"를 바로 이해하기 어렵다.

추가 제안:

- `@review-bot full-report` 같은 명령으로 이번 run의 전체 후보를 별도 overview note 또는 artifact로 제공
- inline 게시분, 대기 중인 high-confidence 항목, low-priority coaching 항목을 구분 표시
- 각 항목에 `게시됨`, `보류됨`, `낮은 우선순위`, `중복 억제`, `근거 부족` 같은 상태를 함께 노출

판단:

- 가장 우선순위가 높다.
- 지인 사례의 불만을 가장 직접적으로 해소한다.
- inline noise를 늘리지 않고도 "전체를 보고 싶다"는 요구를 만족시킬 수 있다.

### 2.2 "왜 이 10개만 보였는가" 설명

현재 시스템은 lifecycle-aware batch selection을 하고 있지만, 사용자에게는 selection logic이 잘 보이지 않는다.

추가 제안:

- summary note에 `이번에 게시된 10개 / 대기 중 7개 / 억제 14개`처럼 상태별 총계를 추가
- 기존 open thread update/reopen이 새 finding보다 우선됐음을 설명
- rule family cap, weak anchor suppression, duplicate suppression 같은 주요 억제 이유를 짧게 노출

판단:

- full-report보다 구현 난이도가 낮고 체감 효과가 빠르다.
- 운영자와 개발자 모두가 현재 출력 정책을 신뢰하기 쉬워진다.

### 2.3 반복 지적 / Ignore UX 정책 재정렬

현재 시스템은 이 영역에서 절반은 맞고 절반은 과도하다.

현재 상태:

- 같은 finding이 다시 검출되어도 기존 thread를 재사용하려는 방향은 이미 있다.
- incremental run에서는 unchanged open thread를 새로 다시 끌어올리지 않는다.
- `bot:ignore`와 `bot:allow` 같은 명시적 human feedback command도 이미 지원한다.
- 하지만 full/manual 재검토에서는, 아직 열려 있는 기존 thread가 같은 anchor로 다시 검출되면 reminder reply를 추가로 남기는 방향으로 구현돼 있다.
- 일반 `resolve`는 명시적 ignore가 아니라 score penalty에 가깝다. 즉 사용자가 "이번에는 넘어가자"는 뜻으로 resolve해도, 시스템은 이를 완전한 suppress 신호로 보지 않는다.

이 구조는 "수정이 안 됐으면 다시 지적해도 된다"는 원칙에는 맞지만, 사용자 체감 UX에는 다소 거칠 수 있다. 특히 first-class ignore 버튼이 없는 상태에서는 "이미 본 말을 또 듣는 느낌"이 강해질 수 있다.

권장 기본 정책:

- 반복 검출은 허용한다.
- 반복 게시는 제한한다.
- open thread가 그대로 남아 있으면 기본값으로는 새 reminder reply를 또 달지 않는다.
- 대신 기존 open thread를 canonical state로 유지하고, 필요하면 summary/full-report에서 "여전히 남아 있음"만 알려 준다.
- resolved thread는 코드가 실제로 다시 바뀌었거나 anchor/body가 의미 있게 변했을 때만 inline 재등장시키는 편이 좋다.
- 사용자가 명시적으로 `ignore`, `false-positive`, `later`, `allow`를 줄 수 있는 first-class feedback 경로가 필요하다.

구체 제안:

- 기본 모드에서는 full/manual rerun의 open-thread reminder reply를 끈다.
- reminder는 opt-in 명령 또는 운영자 모드에서만 켠다.
- `resolve`는 "완전 suppress"가 아니라 "잠재 재검토 후보"로 유지하되, `resolved + unchanged` 상태는 inline보다 backlog/full-report에서만 재노출한다.
- `bot:ignore` 외에도 `bot:later`, `bot:false-positive` 같은 명시 명령을 추가한다.
- summary에 `이미 열린 이슈 3건은 재게시하지 않고 backlog로 유지` 같은 문구를 넣어 현재 정책을 설명한다.

판단:

- 사용자 피로도를 줄이기 위해 우선순위가 높다.
- 현재 시스템의 thread lifecycle 강점을 해치지 않으면서도 더 자연스러운 UX를 만들 수 있다.
- 이 항목은 full-report/backlog view와 같이 설계해야 효과가 크다.

### 2.4 Must-Fix / Should-Fix / Coaching 티어

지인 사례가 반복할수록 점점 덜 중요한 내용을 보여 주는 구조였다면, 현재 시스템은 그것을 더 명시적으로 tiering할 수 있다.

추가 제안:

- `must-fix`: merge 전에 바로 보는 항목
- `should-fix`: 이번 MR에서 수정 권장
- `coaching`: 다음 작업에서 참고할 개선 포인트

판단:

- 단순 score ordering보다 훨씬 읽기 쉽다.
- "처음부터 전부 알려 달라"는 요구를 받아들이면서도 중요도 구분을 유지할 수 있다.

### 2.5 Patch Bundle / Safe Autofix Mode

현재도 suggestion block은 유용하지만, 더 나아가 여러 finding을 한 번에 정리한 patch bundle이나 safer autofix 후보를 만들 수 있다.

추가 제안:

- 같은 파일의 low-risk 수정안을 묶어 제안
- 규칙별 confidence와 변경 범위를 기준으로 `safe autofix`만 분리
- inline comment에는 이유를, 별도 patch artifact에는 실제 수정안을 제공

판단:

- 리뷰 체감 가치를 크게 높일 수 있다.
- 다만 C++ 코드베이스 특성상 보수적으로 시작해야 한다.

### 2.6 Reviewer / Team Preference Profile

현재 시스템은 feedback learning이 들어가 있지만, 출력 정책을 사용자나 팀 단위로 더 명시적으로 조정할 수 있다.

추가 제안:

- 팀별 rule family cap
- reviewer별 coaching 항목 on/off
- 특정 경로 또는 모듈에 대한 stricter mode

판단:

- 운영 고도화 단계에서 중요하다.
- 조직별 선호 차이를 문서와 코드 정책으로 흡수하기 좋다.

### 2.7 Evidence Transparency 강화

사용자가 리뷰를 신뢰하려면 "어떤 가이드가 선택됐고, 왜 이 코드에 적용됐는지"가 더 잘 보여야 한다.

추가 제안:

- 각 finding에 사용된 규칙 id와 선택 근거를 더 명시적으로 표시
- 비슷한 과거 코드 또는 유사 패턴이 있다면 evidence snippet으로 함께 제시
- `왜 applicable인가`를 자연어 한 줄로 보여 주기

판단:

- 현재 시스템의 강점인 deterministic retrieval을 더 잘 드러내 준다.
- "AI가 그냥 말한다"는 인상을 줄이고 신뢰도를 높인다.

## 3. 그대로 가져오지 않는 편이 좋은 것

아래는 지인 사례에서 영감을 받을 수는 있지만, 현재 시스템에 그대로 복제하지 않는 편이 좋은 항목이다.

- 모든 finding을 처음부터 inline으로 다 게시하는 방식
  - noise와 review fatigue를 빠르게 키운다.
  - inline batch와 별도 full-report를 분리하는 편이 낫다.
- AI가 가이드를 자유롭게 선정하는 방식
  - 현재 시스템처럼 deterministic retrieval과 policy가 먼저 후보를 줄이는 편이 auditability와 재현성이 좋다.
- 단순 "상위 5개" 고정 컷
  - 현재처럼 thread lifecycle과 dedupe를 우선하는 selection이 운영에는 더 적합하다.

## 4. 우선순위 제안

### P0

- full-report / backlog view
- summary에 게시/보류/억제 총계와 selection 이유 추가
- 반복 지적 / ignore UX 정책 재정렬

### P1

- must-fix / should-fix / coaching tier
- patch bundle / safe autofix mode
- first-class `ignore/later/false-positive/allow` 피드백 명령

### P2

- reviewer / team preference profile
- evidence transparency와 explainability 강화

## 5. 최종 판단

현재 시스템은 "지인 시스템의 상위 호환 운영형 버전"에 더 가깝다. 이미 더 나은 점은 많다.

- 운영 구조와 lifecycle이 더 성숙하다.
- 규칙 정제와 내부 정책 우선순위가 더 강하다.
- AI를 설명과 triage 쪽으로 제한해 신뢰도를 관리하기 쉽다.

다만 다음 단계에서 가장 중요한 제품 과제는 여전히 남아 있다.

- 사용자가 전체 backlog를 보고 싶어 하는 요구를 어떻게 충족할 것인가
- 지금 보인 항목과 아직 보이지 않은 항목의 차이를 어떻게 설명할 것인가

즉, 지금 필요한 것은 탐지 엔진을 새로 바꾸는 일보다, 현재 엔진과 lifecycle 위에 더 나은 가시성과 UX를 얹는 일이다.
