# 리뷰 봇 근원 점검 및 개선 방향 보고서 (V3)

- 문서 상태: Current — 실행 기준 문서
- 작성일: 2026-04-21
- 작성 목적: `REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md`의 KPI/metric/phase ordering 문제를 보정하고,
  현재 저장소 기준 실행 가능한 통합 설계 기준을 제공한다.
- 관련 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2_EVALUATION.md`

## 0. Executive Summary

현재 `review-bot`은 여전히 "inline-first, lifecycle-aware, feedback-aware" 구조로서
기본 방향이 맞다.
유지해야 할 핵심은 아래 다섯 가지다.

1. inline discussion을 canonical UI로 둔다.
2. `detect -> publish -> sync` 파이프라인을 유지한다.
3. `ThreadSyncState`를 current backlog의 source of truth로 둔다.
4. feedback command를 thread reply에서 해석한다.
5. next investment는 "탐지량 증가"보다 "신뢰도, context, actionability"에 둔다.

V3는 V2의 방향을 유지하면서 아래 세 가지를 바로잡는다.

- baseline 측정과 새 instrumentation 도입 순서를 분리한다.
- `acceptance_rate`의 모호함을 제거한다.
- metric naming과 query 예시를 현재 코드 계열과 맞춘다.

핵심 메시지는 변하지 않는다.

> `review-bot`의 다음 단계는 "더 많이 지적하는 봇"이 아니라
> "더 믿을 수 있고, 더 맥락을 알고, 더 실행 가능한 제안을 하는 봇"이어야 한다.

## 1. 증거 층위 규칙

이 문서의 주장은 세 층위로 구분한다.

- `[code-verified]`
  - 현재 저장소 코드와 직접 대조 가능한 사실
- `[design-inference]`
  - 코드와 구조를 바탕으로 한 설계 해석
- `[market-informed]`
  - 외부 제품 문서, 블로그, 벤더 self-report 기반 참고치

명시적 태그가 없는 문장은 기본적으로 `[design-inference]`로 본다.

## 2. 현재 시스템 지형

### 2.1 트리거 모델 `[code-verified]`

현재 `review-bot`은 **Note Hook mention 기반 수동 호출형 리뷰어**다.

- GitLab `Merge Request Hook`은 자동 리뷰 실행에 사용하지 않는다.
- `Note Hook`에서 bot mention이 있을 때만 review run이 생성된다.
- 내부 API `POST /internal/review/runs`는 별도 수동/내부 트리거다.

이 전제는 아래 기능의 설계에 직접 영향을 준다.

- walkthrough 자동 게시
- acceptance freshness
- sync 주기
- optional auto-trigger 범위

### 2.2 파이프라인 개요 `[code-verified]`

```
GitLab Note Hook
     │
     ▼
[ Webhook API ]
     │  review / full-report / backlog / help
     ▼
[ Detect Queue ] ──► EngineClient (/review/diff, search_codebase, circuit breaker)
     ▼
[ FindingEvidence + FindingDecision ]
     │  - fingerprint
     │  - anchor_signature
     │  - score_final
     ▼
[ Publish Queue ]
     │  - upsert inline comment
     │  - publish batch dedupe
     │  - run summary note
     ▼
[ Sync Queue ]
     │  - ThreadSyncState reconcile
     │  - feedback ingest
     │  - resolution_reason update
     ▼
[ backlog / full-report / help ]
```

### 2.3 현재 강점 `[code-verified]`

- inline-first UX
- queue 기반 detect / publish / sync 분리
- `ThreadSyncState` 기반 backlog 관리
- reply 기반 feedback command 해석
- fingerprint + anchor_signature dedupe
- path policy 기반 score 조정
- current-state backlog view
- explicit command parser
- worker-scoped SQLite test DB
- process-local rate-limit의 한계를 코드 주석에서 이미 경고하고 있음

### 2.4 현재 한계

- `[code-verified]` context는 현재 파일 `file_context` 4000자 중심
- `[design-inference]` review unit split이 lexical / hunk 중심
- `[design-inference]` verify phase 부재
- `[code-verified]` severity는 현재 `low / medium / high`
- `[code-verified]` rule weight는 `rule_no` global weight
- `[design-inference]` 실제 코드 수정 유발 여부를 직접 측정하지 않음
- `[code-verified]` `ask`, `summarize`, `apply` command 없음
- `[code-verified]` 설정 표면이 `policy.json + env`로 분산

### 2.5 현재 `resolution_reason` 상태값 `[code-verified]`

현재 코드에서 확인되는 `resolution_reason` 값은 아래다.

- `remote_resolved`
- `no_longer_eligible`
- `anchor_changed`
- `resolve_failed`
- `remote_reopened`

새 설계에서 추가 검토하는 값은 아래다.

- `fixed_in_followup_commit`
- `remote_resolved_manual_only`

즉, 문서에서는 **현재값**과 **추가 후보**를 반드시 구분해 서술해야 한다.

## 3. 유지할 결정 / 재검토할 결정

### 3.1 유지할 결정

- inline-first review UX
- detect / publish / sync 분리
- feedback command를 thread reply에서 해석하는 방식
- `ThreadSyncState` 중심 backlog / analytics 접근
- path policy 기반 score 조정
- run summary와 full-report / backlog를 보조 인터페이스로 두는 구조

### 3.2 재검토할 결정

- `severity = f(score)` 구조
- `rule_no` global weight
- note-only trigger를 언제까지 유지할지
- run summary note의 append-only 여부
- `.review-bot.yaml` 도입 범위와 우선순위

## 4. 업계 비교에 대한 사용 규칙

> 이 절의 수치와 제품 특징은 `[market-informed]`이며,
> vendor self-report를 포함한다.
> 방향성 참고치로만 사용하고 내부 KPI 목표의 직접 근거로 사용하지 않는다.

업계에서 참고할 패턴은 아래다.

1. `flag -> verify -> post`
2. learned rules / knowledge base
3. severity의 정책 분리
4. walkthrough의 별도 산출물화
5. acceptance 계열 KPI 사용
6. 검증된 auto-fix만 허용
7. repo-local config 수렴

## 5. Gap 분석

### 5.1 신뢰도 (Must-fix)

- acceptance를 직접 측정하지 못한다
- verify phase가 없다
- severity와 score가 섞여 있다

### 5.2 Context (High)

- 단일 파일 중심 context
- syntax-aware가 아닌 review unit split
- finding-level retrieval 부재

### 5.3 Learning (High)

- `(project_ref, rule_no)` 단위 학습 부재
- similarity-based suppression 부재

### 5.4 UX / Actionability (High)

- walkthrough 부재
- `ask` 부재
- `apply` 부재

### 5.5 운영 / Observability (Medium)

- process-local rate limit
- metric 체계가 다음 단계 KPI를 직접 뒷받침하지 못함
- config 표면 분산

## 6. Phase 0 — Pre-check

Phase 0는 구현 phase가 아니라,
Phase A 전에 확정해야 할 결정 목록이다.

### P0.1 트리거 모델 결정

선택지는 아래 세 가지다.

- (a) 현행 유지: MR hook 무시, note mention만 실행
- (b) 부분 확장: MR hook은 metadata refresh / sync / optional walkthrough trigger만 수행
- (c) 자동 리뷰 확장: MR hook이 자동 review까지 트리거

권장 default는 (a)다.
walkthrough 자동 게시가 필요해지는 시점에만 (b)를 검토한다.
(c)는 acceptance baseline 확보 전까지 금지한다.

### P0.2 `resolution_reason` 의미 확정

현재값과 추가 후보의 semantics를 문서와 코드에서 동일하게 맞춘다.

- 현재값:
  - `remote_resolved`
  - `no_longer_eligible`
  - `anchor_changed`
  - `resolve_failed`
  - `remote_reopened`
- 추가 후보:
  - `fixed_in_followup_commit`
  - `remote_resolved_manual_only`

### P0.3 KPI 용어 확정

V3에서는 모호한 `acceptance_rate` 대신 아래 두 개를 구분한다.

- `fix_confirmation_rate`
  - resolved된 것 중 실제 fix 근거가 확인된 비율
- `fix_conversion_rate`
  - surfaced된 것 중 실제 fix 근거가 확인된 비율

문서 외부 커뮤니케이션에서 `acceptance_rate`라는 말을 쓴다면
기본값은 `fix_conversion_rate`로 간주하되,
대시보드에는 별도 이름으로 표기하는 것을 권장한다.

## 7. Baseline과 Instrumentation 순서

V2의 가장 큰 문제는 baseline과 instrumentation이 같은 시점에 필요한 것처럼 적힌 점이었다.
V3는 이를 두 단계로 분리한다.

### 7.1 Baseline v0 — 현재 지표 기준

아직 구현되지 않은 분류나 metric을 쓰지 않고,
현재 코드에서 바로 측정 가능한 것만 본다.

수집 항목:

- `findings_published_total`
- `findings_resolved_total`
- `findings_suppressed_total`
- `/internal/analytics/rule-effectiveness`
- feedback command 빈도
- inline publish 실패 분포
- open thread / backlog 규모

이 단계의 목적은 "현재 상태가 어느 정도 noisy한가"를 잡는 것이다.

### 7.2 Instrumentation Phase — 새 metric 추가

Phase A에서 아래를 구현한다.

- `resolution_reason` 확장
- 새 severity taxonomy
- verify counter
- feedback command counter
- resolved counter의 label 확장 또는 계열 보강

### 7.3 Baseline v1 — 새 지표 기준 soak

Instrumentation 배포 후 짧은 운영 구간을 둔다.
이때부터 아래 지표를 canonical KPI로 사용한다.

- `fix_confirmation_rate`
- `fix_conversion_rate`
- `signal_ratio`
- `ignore_rate`
- `verify_drop_rate`

즉, baseline-first를 유지하되
"현재 지표 baseline"과 "새 지표 baseline"을 나눠 보는 것이 V3의 기준이다.

## 8. KPI 및 Instrumentation

### 8.1 metric naming 원칙

현재 코드가 이미 `findings_*` 계열을 사용하므로,
V3는 가능한 한 이 계열을 확장한다.

권장 원칙:

- 기존 counter rename은 피한다
- 필요한 경우 label 확장 또는 sibling counter 추가
- 새 이름 체계가 필요해도 migration 문서 없이는 wholesale rename 금지

### 8.2 최소 KPI 정의

| KPI | 정의 | 권장 기반 |
| --- | --- | --- |
| `fix_confirmation_rate` | resolved finding 중 실제 fix 근거가 확인된 비율 | `sum(findings_resolved_total{resolution_reason="fixed_in_followup_commit"}) / sum(findings_resolved_total)` |
| `fix_conversion_rate` | surfaced finding 중 실제 fix로 이어진 비율 | `sum(findings_resolved_total{resolution_reason="fixed_in_followup_commit"}) / sum(findings_published_total)` |
| `signal_ratio` | high-priority finding 비중 | `sum(findings_published_total{severity=~"warning|critical"}) / sum(findings_published_total)` |
| `ignore_rate` | ignore/false-positive feedback 비중 | `sum(feedback_commands_total{command=~"ignore|false-positive"}) / sum(findings_published_total)` |
| `verify_drop_rate` | verify 대상 중 drop 비율 | `sum(verify_dropped_total) / sum(verify_attempts_total)` |

### 8.3 Prometheus metric 권장안

기존 계열 확장 기준:

- `findings_published_total{severity, rule_family}`
- `findings_resolved_total{rule_family, resolution_reason}`
- `findings_suppressed_total{reason}`

새로 필요한 최소 counter:

- `feedback_commands_total{command}`
- `verify_attempts_total{mode}`
- `verify_dropped_total{mode, reason}`

권장사항:

- Prometheus에는 `rule_no` 대신 기본적으로 `rule_family`를 사용
- `rule_no` 단위 drill-down은 API analytics나 warehouse 쪽으로 분리
- Prometheus에서 top-N / `__other__` 같은 동적 grouping은 구현 복잡도가 높으므로
  metric label 설계에서 회피하는 편이 낫다

### 8.4 해석 규칙

- `resolved`는 곧 fix가 아니다
- `suppressed` 감소만으로 성공을 판단하지 않는다
- published count 증가를 성공 지표로 쓰지 않는다
- vendor benchmark를 직접 목표 수치로 고정하지 않는다

### 8.5 1차 목표 설정 방식

V3는 절대 목표치를 문서에 박지 않는다.
아래처럼 개선폭으로 관리한다.

- verify 도입 후 `ignore_rate` 20% 이상 감소
- context 강화 후 `fix_conversion_rate` 10pt 이상 개선
- walkthrough 도입 후 reviewer onboarding 시간 정성 피드백 개선

## 9. 강화된 로드맵

### Phase A (2-4주) — Trust Foundation

- `A1. resolution_reason 확장`
  - `fixed_in_followup_commit`
  - `remote_resolved_manual_only`
- `A2. severity / score 분리`
  - `warning / critical / suggestion / nitpick`
  - 기존 `low / medium / high`는 migration alias
- `A3. verify phase v1`
  - low-confidence finding에 LLM self-check 적용
- `A4. distributed rate limit`
  - Redis sliding window 도입
- `A5. instrumentation 추가`
  - `feedback_commands_total`
  - `verify_attempts_total`
  - `verify_dropped_total`
  - `findings_resolved_total`에 `resolution_reason` label 확장 검토

### Phase B (4-8주) — Context

- syntax-aware review unit split
- related file retrieval
- finding-level second retrieval

### Phase C (8-12주) — Learning + UX

- `(project_ref, rule_no)` weight
- similarity-based learned suppression
- `.review-bot.yaml` 도입
- `@review-bot summarize`
- `@review-bot ask <question>`

### Phase D (12주+) — Automation

- `@review-bot apply`
- low-priority collapsed output
- 조건부 multi-reviewer 병렬화

## 10. 상세 설계 스케치

### 10.1 Verify Phase 흐름

```
Detect → FindingDecision(state=eligible, confidence=c)
         │
         ▼
   if c < VERIFY_THRESHOLD:
         │
         ▼
   LLM_self_check(prompt=[finding, evidence, change_snippet])
         │
         ▼
   {is_real_bug: bool, reasons: [str], new_confidence: float}
         │
   is_real_bug == False → state=suppressed, reason="verify:llm_self_check"
   new_confidence < minimum → state=suppressed, reason="verify:low_confidence"
```

- 위치:
  - `review_runner.py`의 `_build_decision` 이후 verify hook

### 10.2 Acceptance / Fix Tracking

새 설계의 핵심은 `resolved`를 둘로 쪼개 보는 것이다.

- `fixed_in_followup_commit`
  - resolved 시점 이후 commit diff가 `file_path:line_no ± 3 lines`를 실제로 변경
- `remote_resolved_manual_only`
  - 사용자가 resolve는 했지만 코드 변경 근거는 없음

이 구분이 있어야 아래 둘이 동시에 가능해진다.

- "resolved된 것 중 실제 수정 비율"
- "surfaced된 것 중 실제 수정 전환 비율"

### 10.3 `.review-bot.yaml` 스키마 초안

```yaml
version: 1

review:
  minimum_publish_score: 0.65
  severity_thresholds:
    critical: 0.9
    warning: 0.75
    suggestion: 0.6
    nitpick: 0.4
  collapsed_severities: [nitpick, suggestion]
  allowed_rules: [ALTI-MEM-007]
  suppressed_rules: [ALTI-STYLE-012]

paths:
  - glob: "tests/**"
    score_adjustment: -0.2
    suppress_rules: [ALTI-PERF-001]
  - glob: "src/security/**"
    minimum_score: 0.8
    promote_rules: [ALTI-SEC-*]

instructions: |
  이 repo는 Altibase storage engine 코어다.
  - 메모리 소유권과 예외 안전이 최우선.
  - 테스트 코드의 스타일 지적은 피한다.
  - suggestion 블록은 반드시 컴파일 가능해야 한다.

chat:
  ask_enabled: true
  ask_history_turns: 3
```

우선순위는 아래를 권장한다.

- `.review-bot.yaml`
- `policy.json`
- env

단, 실제 migration은 점진적으로 진행한다.

### 10.4 Walkthrough 노트 포맷

```markdown
## 🤖 리뷰 봇 — MR 요약

**요지**: ownership API에 malloc→realloc 전환 2건, 테스트 3개 추가.

### 영향
- 수정된 symbol: `owner_alloc`, `owner_release` (호출 사이트 7곳)
- 호출부는 `src/storage/ownership/*.cpp`에 집중

### 주의해서 봐 주세요
- 🔴 `src/storage/ownership/ref.cpp:128` — realloc 실패 경로에서 원래 포인터 leak 가능
- 🟠 `src/storage/ownership/ref.cpp:214` — free() 직후 포인터 재사용 의심

> 전체 backlog는 `@review-bot backlog`로 확인할 수 있습니다.
```

run summary와 walkthrough는 purpose를 분리한다.

- run summary
  - 이번 배치 게시 항목 운영 요약
- walkthrough
  - MR onboarding용 설명

## 11. 결론

V3의 최종 권고는 아래와 같다.

- 현재 구조는 유지 가치가 높다.
- 가장 큰 기술 부채는 여전히 verify phase 부재와 acceptance 측정 부재다.
- context 강화는 중요하지만 trust foundation 뒤에 온다.
- UX 고도화는 신뢰도 기반 위에서 붙여야 한다.
- KPI는 vendor claim이 아니라 내부 baseline과 개선폭으로 관리한다.

즉, V3는 방향을 다시 뒤집는 문서가 아니라
**V2의 KPI/metric/phase ordering 문제를 정리해 실제 구현 순서가 보이게 만든 문서**다.

## 부록 A. 현재 코드 참조점

- 파이프라인 엔트리: `review-bot/review_bot/worker.py`
- Detect/publish/sync: `review-bot/review_bot/bot/review_runner.py`
- Command parser: `review-bot/review_bot/api/main.py`
- GitLab adapter: `review-bot/review_bot/review_systems/gitlab.py`
- Policy: `review-bot/review_bot/policy.py`
- Analytics endpoint: `review-bot/review_bot/api/main.py` (`/internal/analytics/rule-effectiveness`)
- Metrics 정의: `review-bot/review_bot/metrics.py`
- Test DB isolation: `review-bot/tests/conftest.py`

## 부록 B. 참고 자료 `[market-informed]`

아래 자료는 방향성 참고치로만 사용한다.

- CodeRabbit docs / blog
- Greptile docs / 사례 글
- Graphite Diamond 관련 글
- Cursor Bugbot blog
- Ellipsis architecture / build notes
- Qodo Merge / PR-Agent docs
- Sourcery docs
- GitHub Copilot code review docs
