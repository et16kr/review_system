# Review Bot Fundamental Review Enhanced

- 문서 상태: Draft for decision
- 작성일: 2026-04-21
- 작성 목적: `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`의 방향성은 유지하되,
  현재 저장소 코드 기준으로 사실관계와 우선순위를 보정한 실행 기준 문서를 제공한다.
- 대상 독자: 리뷰 봇 구현 담당자, 설계 의사결정자, AI agent
- 관련 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md`
  - `docs/REVIEW_BOT_BACKLOG_ANALYTICS_AND_COMMAND_UX_DESIGN.md`
  - `docs/REVIEW_BOT_REDESIGN_DESIGN.md`

## 0. Executive Summary

현재 `review-bot`은 여전히 "inline-first, lifecycle-aware review bot"으로서
기본 골격이 잘 잡혀 있다.
`detect -> publish -> sync`, fingerprint 기반 dedupe, `ThreadSyncState` 기반 backlog,
feedback command 해석, explicit command parser 같은 핵심 축은 유지해도 된다.

다만 다음 개선을 추진할 때는 두 가지를 먼저 분명히 해야 한다.

1. 현재 시스템은 `Merge Request Hook` 기반 자동 리뷰어가 아니라
   `Note Hook mention` 기반 수동 호출형 리뷰어다.
2. 외부 벤치마크 수치는 참고용일 뿐, 내부 KPI 목표의 직접 근거가 아니다.

따라서 다음 투자 우선순위는 아래처럼 재정렬하는 편이 맞다.

1. `Phase 0`: 트리거 모델과 측정 전제 정리
2. `Phase A`: 신뢰도 강화
3. `Phase B`: context retrieval 강화
4. `Phase C`: 학습 루프와 UX 강화
5. `Phase D`: 자동화 확장

핵심 메시지는 원문과 같다.
지금 필요한 것은 "더 복잡한 탐지"보다
"검증, 측정, context, actionability"다.

## 1. 현재 상태 재정리

### 1.1 현재 코드 기준으로 확인된 사실

- 리뷰 실행 트리거는 기본적으로 GitLab note mention이다.
- `Merge Request Hook`은 현재 자동 리뷰 실행에 사용하지 않는다.
- worker는 `detect`, `publish`, `sync` queue를 연쇄 실행한다.
- diff 분석은 C/C++ 파일에 한정된다.
- engine 호출에는 `file_context`가 최대 4000자까지 포함된다.
- `search_codebase(top_k=2)` 결과가 evidence에 함께 저장된다.
- severity는 현재 `score -> low/medium/high` 매핑이다.
- rule effectiveness weight는 현재 `rule_no` 단위 global weight다.
- feedback command는 thread reply에서 `ignore`, `false-positive`, `later`, `allow`를 해석한다.
- `full-report` / `backlog`는 현재 `ThreadSyncState` 기반 current-state backlog 모델을 사용한다.
- `full-report` / `backlog` / `help` general note는 same-purpose upsert를 우선한다.
- run summary note는 현재 append-only 성격이 강하다.
- 테스트 DB는 worker-scoped SQLite 파일로 분리되어 있다.
- webhook rate limit은 process-local memory bucket이다.

### 1.2 현재 강점

- `Inline-first`
  - canonical UI가 GitLab discussion thread라는 점은 여전히 적절하다.
- `Lifecycle-aware`
  - detect / publish / sync 분리는 실패 국소화에 유리하다.
- `Feedback-aware`
  - human reply가 suppression과 scoring에 실제로 반영된다.
- `Current-state backlog`
  - backlog를 최신 run row가 아니라 실제 thread state 중심으로 본다.
- `Operationally conservative`
  - explicit command parser, inline anchor 실패 시 suppress, process-local rate-limit 주석 등은 운영 감각이 좋다.

### 1.3 현재 한계

- 검증 phase가 없다.
- retrieval이 현재 파일 중심이며 multi-hop context가 약하다.
- review unit split이 syntax-aware가 아니라 hunk/line 중심이다.
- severity가 score의 파생값이다.
- rule learning이 per-project가 아니라 global rule 단위다.
- acceptance metric이 없다.
- `ask`, `apply` 같은 interactive actionability가 없다.
- repo-local config 표면이 `policy.json + env`로 분산되어 있다.
- 트리거 모델이 note mention 중심이라 자동 freshness 기능을 붙이기 어렵다.

## 2. 판단

### 2.1 유지할 결정

- inline-first review UX
- detect / publish / sync 분리
- fingerprint + anchor_signature 기반 thread 수명주기 관리
- feedback command를 thread reply에서 해석하는 방식
- `ThreadSyncState` 기반 backlog / analytics 접근
- path policy 기반 score 조정과 suppress / allow 훅

### 2.2 재검토할 결정

- `severity = f(score)` 구조
- `rule_no` global weight
- note-only trigger 구조를 자동 기능 확장과 동시에 유지할 것인지 여부
- summary note를 append-only로 둘지 same-purpose upsert로 수렴시킬지 여부
- `policy.json + env` 중심 설정 구조

### 2.3 아직 서두르지 말아야 할 영역

- cross-repo analysis
- multi-language 대확장
- IDE 실시간 리뷰 통합
- multi-agent reviewer 병렬화

이 영역은 현재 KPI와 acceptance baseline이 잡히기 전에는 후순위다.

## 3. 먼저 결정해야 할 전제

### 3.1 이벤트 / 트리거 모델

현재 시스템은 "mention-driven manual reviewer"다.
이 전제는 walkthrough 자동 게시, follow-up commit 추적, fresh sync 보장 방식에 직접 영향을 준다.

이 문서는 아래 incremental 방향을 권장한다.

- 기본 inline review 실행은 계속 note mention 기반으로 유지
- 대신 MR hook을 "metadata refresh / lightweight sync / optional walkthrough trigger" 용도로만 점진 도입
- 자동 inline publish는 acceptance baseline이 확보되기 전에는 도입하지 않음

이 방식의 장점은 아래와 같다.

- 현재 UX와 운영 비용을 크게 흔들지 않는다.
- walkthrough와 acceptance tracking의 freshness를 조금씩 개선할 수 있다.
- 자동 리뷰 오남발 risk를 피할 수 있다.

### 3.2 acceptance metric의 의미

acceptance는 단순 `resolved`와 동일하지 않다.
최소한 아래 상태를 구분해야 한다.

- `fixed_in_followup_commit`
- `remote_resolved_manual_only`
- `no_longer_eligible`
- `remote_reopened`
- `anchor_changed`

즉, "thread가 닫혔다"와 "코드가 실제로 수정되었다"를 분리해야 한다.

### 3.3 외부 벤치마크의 사용 규칙

CodeRabbit, Greptile, Diamond, Bugbot, Ellipsis, Qodo 같은 제품 비교는 계속 유용하다.
다만 사용 규칙을 명시해야 한다.

- 외부 수치는 `market-informed` 참고치로만 사용
- 내부 KPI 목표는 실제 baseline 측정 후 설정
- vendor self-report는 문서 본문에서 명시

## 4. 강화된 로드맵

### Phase 0 (0-2주): 전제 정리

P0.1 `trigger model` 명시

- note mention 기반 review 실행은 유지
- MR hook을 무시할지, metadata/sync용으로 부분 활용할지 결정
- walkthrough 자동 게시가 필요하다면 trigger source를 별도 필드로 남김

P0.2 `resolution_reason` 체계 확장

- 기존 `remote_resolved`, `no_longer_eligible`, `anchor_changed` 외
  `fixed_in_followup_commit`, `remote_resolved_manual_only`를 추가 검토
- naming은 현재 모델 필드명 `resolution_reason`으로 통일

P0.3 측정 규칙 문서화

- acceptance, ignore_rate, signal_ratio의 정의를 먼저 고정
- vendor metric은 부록 참고치로 격하

### Phase A (2-4주): 신뢰도 강화

A1. acceptance tracking 추가

- sync phase에서 thread가 resolved로 전환될 때 follow-up diff 근거를 추가 판정
- 코드 변경이 확인되면 `fixed_in_followup_commit`
- 근거가 없으면 `remote_resolved_manual_only`

A2. severity / score 분리

- `FindingDecision.severity`는 provider나 engine이 제시할 수 있게 확장
- score는 publish gating 용도로 축소
- 새로운 severity 체계는 `nitpick / suggestion / warning / critical`
- 기존 `low / medium / high`는 호환용 alias 또는 migration 경로를 명시

A3. verify phase 옵션 도입

- 1차: low-confidence finding에 대해 LLM self-check
- 2차: rule-specific 패턴은 regex/AST 기반 재검증 훅 추가
- 드롭 이유는 `verify:*` namespace로 수집

A4. distributed rate limit

- process-local `deque`를 Redis-backed sliding window로 교체
- 단일 GitLab IP가 여러 인스턴스에 분산될 때도 일관되게 제어

A5. metrics 보강

- `review_comments_resolved_total{resolution_reason,rule_no}`
- `review_feedback_commands_total{command}`
- `verify_phase_drop_total{reason}`
- acceptance는 raw counter와 derived dashboard로 분리

### Phase B (4-8주): context 강화

B1. syntax-aware review unit split

- 현재 80라인 added chunk split 대신
  함수/메서드 경계를 우선하는 review unit 전략을 도입
- 첫 단계는 C/C++ 대상 tree-sitter 또는 이에 준하는 구조 추출

B2. related file retrieval

- touched symbol 기준 정의/참조 1-hop excerpt를 주입
- `file_context` 하나에 몰아넣기보다
  `primary_file_context + related_contexts` 식으로 구조화하는 편이 낫다

B3. finding-level second retrieval

- diff-level retrieval과 별개로 finding별 mini-query를 한 번 더 수행
- 유사 과거 finding과 human feedback을 근거로 품질 보정

### Phase C (8-12주): 학습과 UX

C1. `(project_ref, rule_no)` 단위 weight

- 동일 rule이 repo마다 다르게 작동한다는 현실을 반영
- 데이터가 적은 rule은 Bayesian smoothing으로 보정

C2. similarity-based learned suppression

- 초기에는 문자열 유사도 기반으로도 충분
- 이후 embedding / vector index는 실제 규모가 확인된 뒤 도입

C3. `.review-bot.yaml` 도입

- `policy.json`과 env 일부를 수렴
- 단, migration은 한 번에 갈아엎기보다 `policy.json` 우선/후순위 규칙을 명확히 두고 점진 이행

C4. walkthrough note

- 1차는 on-demand `@review-bot summarize`
- 2차는 MR hook 기반 optional auto-post
- 현재 summary note와 구분되는 목표는 아래 세 가지다.
  - 변경 요지 설명
  - 영향 symbol / 함수 범위
  - top finding 요약

C5. `@review-bot ask <question>`

- thread context + diff + 관련 파일 excerpt 기반 답변
- history는 짧게 유지하고, 답변은 thread reply로 게시

### Phase D (12주+): 자동화 확장

D1. `@review-bot apply`

- high-confidence + small patch + build/lint pass 조합에서만 허용
- patch 적용 후 branch push
- merge는 사람이 결정

D2. collapsed low-priority output

- `nitpick` / `suggestion`은 기본 접힘 모드
- review noise를 줄이고 warning 이상을 먼저 보이게 함

D3. multi-reviewer 병렬화

- acceptance plateau가 오고 단일 pipeline 한계가 확인될 때만 검토
- 현재 단계에서는 과투자 가능성이 높다

## 5. 상세 설계 보정 포인트

### 5.1 summary note와 walkthrough note를 분리한다

현재 summary note는 존재하지만 walkthrough는 아니다.
두 개를 분리해서 생각하는 편이 설계가 깔끔하다.

- `run summary`
  - 이번 배치에서 게시된 항목 요약
  - 운영 로그 성격
- `walkthrough`
  - 이 MR이 무엇을 바꾸는지 설명
  - 사람 리뷰어의 onboarding 성격

run summary를 walkthrough로 오해하면 요구사항이 계속 엇갈린다.

### 5.2 metrics는 baseline-first로 간다

원문은 acceptance 목표치를 꽤 공격적으로 제시했지만,
현재는 내부 baseline 자체가 없다.

권장 방식은 아래와 같다.

1. 2주간 baseline 측정
2. ignore / false-positive / manual-only resolve 분포 확인
3. 이후 단계별 개선 목표를 "절대 수치"보다 "baseline 대비 개선폭"으로 설정

예시:

- Phase A 목표
  - verify 도입 후 ignore_rate 20% 감소
- Phase B 목표
  - context 강화 후 acceptance_rate 10pt 이상 개선

이 접근이 현재 팀 상태에 더 안전하다.

### 5.3 `.review-bot.yaml`은 설정 수렴이지 기능 확장이 아니다

repo-local config 도입은 중요하지만,
이를 "새로운 기능 묶음"처럼 밀기보다
"설정 표면 정리"로 보는 편이 현실적이다.

우선 수렴해야 할 항목은 아래 정도면 충분하다.

- minimum publish score
- severity policy
- suppressed / allowed rules
- path policies
- repo-specific reviewer instructions

chat history, autofix 정책, advanced retrieval knob까지
한 번에 넣으면 스키마가 불안정해질 가능성이 높다.

## 6. KPI 가이드

### 6.1 최소 KPI

- `acceptance_rate`
  - 실제 fix 근거가 확인된 해결 비율
- `ignore_rate`
  - `bot:ignore`, `bot:false-positive` 비율
- `signal_ratio`
  - warning 이상 비중
- `verify_drop_rate`
  - verify stage가 얼마나 실제로 노이즈를 제거하는지

### 6.2 해석 규칙

- `resolved`는 acceptance가 아니다
- `suppressed` 감소만으로 성공을 판단하지 않는다
- published count 증가는 성공 지표가 아니다
- baseline 없는 목표 수치는 문서에 고정하지 않는다

## 7. 결론

강화된 판단은 아래와 같다.

- 현재 구조는 유지 가치가 높다.
- 가장 큰 기술 부채는 "검증 phase 부재"와 "트리거/측정 전제 미정리"다.
- context 강화는 필요하지만, verify와 measurement보다 앞서지 않는다.
- walkthrough, ask, apply 같은 UX 기능은 신뢰도 기반이 깔린 뒤 붙여야 한다.
- 외부 제품 비교는 계속 참고하되, 내부 기준은 반드시 내부 데이터로 정한다.

즉, 이 문서의 최종 권고는 다음 한 줄로 요약할 수 있다.

`review-bot`의 다음 단계는 "더 많이 지적하는 봇"이 아니라
"더 믿을 수 있고, 더 맥락을 알고, 더 실행 가능한 제안을 하는 봇"이어야 한다.
