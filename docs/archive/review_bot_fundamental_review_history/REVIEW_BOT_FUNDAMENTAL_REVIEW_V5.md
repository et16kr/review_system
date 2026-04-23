# 리뷰 봇 근원 점검 및 개선 방향 보고서 (V5)

- 문서 상태: Current — 실행 기준 문서
- 작성일: 2026-04-21
- 작성 목적: `REVIEW_BOT_FUNDAMENTAL_REVIEW_V4.md`의 KPI/analytics 모델 문제를 보정하고,
  우리 리뷰 봇 시스템에 실제로 적용 가능한 최종 통합 기준을 제시한다.
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

## 0. Executive Summary

현재 `review-bot`의 구조적 방향은 맞다.

- inline-first
- detect / publish / sync 분리
- `ThreadSyncState` 중심 backlog
- feedback-aware
- explicit command parser

다음 단계의 핵심도 여전히 같다.

1. 신뢰도
2. context
3. actionability

다만 V5는 이전 통합본들과 다른 한 가지를 명확히 고정한다.

> **Prometheus는 운영 이벤트를 본다.**
> **품질 KPI는 distinct fingerprint analytics에서 계산한다.**

이 분리를 지키지 않으면 acceptance, conversion, signal/noise 같은 핵심 수치가
rerun / reopen / event 누적에 의해 왜곡된다.

## 1. 증거 층위 규칙

- `[code-verified]`
  - 현재 저장소 코드와 직접 대조 가능한 사실
- `[design-inference]`
  - 코드와 구조에 근거한 설계 해석
- `[market-informed]`
  - 외부 제품 문서, 블로그, vendor self-report 기반 참고치

## 2. 현재 시스템 지형

### 2.1 트리거 모델 `[code-verified]`

현재 `review-bot`은 **Note Hook mention 기반 수동 호출형 리뷰어**다.

- `Merge Request Hook`은 자동 리뷰 실행에 사용하지 않는다.
- review run 생성 경로는 note mention과 내부 API 중심이다.

### 2.2 파이프라인 `[code-verified]`

```
Note Hook / Internal API
        │
        ▼
     Detect
        │
        ▼
     Publish
        │
        ▼
       Sync
        │
        ├─ ThreadSyncState reconcile
        ├─ feedback ingest
        └─ general notes (summary / full-report / backlog / help)
```

### 2.3 현재 강점 `[code-verified]`

- inline-first UX
- queue 기반 phase 분리
- `ThreadSyncState` 기반 backlog
- feedback command 해석
- fingerprint + anchor_signature dedupe
- current-state backlog 모델
- worker-scoped SQLite test DB

### 2.4 현재 한계

- `[code-verified]` context가 현재 파일 중심
- `[design-inference]` verify phase 부재
- `[code-verified]` severity가 score 종속
- `[code-verified]` rule weight가 global
- `[design-inference]` acceptance / conversion을 직접 측정하지 않음
- `[code-verified]` `summarize`, `ask`, `apply` 부재
- `[code-verified]` 설정 표면 분산

### 2.5 `resolution_reason` 현재값 `[code-verified]`

현재 코드에 실제 존재하는 값:

- `anchor_changed`
- `no_longer_eligible`
- `resolve_failed`
- `remote_resolved`
- `remote_reopened`

Phase A에서 추가 검토하는 값:

- `fixed_in_followup_commit`
- `remote_resolved_manual_only`

## 3. 유지할 결정 / 재검토할 결정

### 3.1 유지할 결정

- inline-first review UX
- detect / publish / sync 분리
- `ThreadSyncState` 기반 backlog / analytics의 중심성
- feedback command를 thread reply에서 해석하는 방식
- path policy 기반 score 조정

### 3.2 재검토할 결정

- `severity = f(score)`
- `rule_no` global weight
- note-only trigger의 지속 범위
- run summary note의 append-only 여부
- `.review-bot.yaml` 도입 방식

## 4. 업계 비교 사용 규칙

> `[market-informed]` 내용은 방향성 참고치로만 사용한다.
> 내부 KPI 목표의 직접 근거로 사용하지 않는다.

업계에서 참고할 패턴:

1. `flag -> verify -> post`
2. learned rules / knowledge base
3. severity 정책 분리
4. walkthrough 별도 산출물
5. acceptance 계열 KPI
6. 검증된 auto-fix만 허용
7. repo-local config 수렴

## 5. 측정 모델 — V5의 핵심 변경점

### 5.1 왜 측정 모델을 분리해야 하는가

현재 코드에는 이미 두 가지 성격의 데이터가 공존한다.

1. **이벤트 계측**
   - publish 시 counter 증가
   - resolve 시 counter 증가
   - suppress 시 counter 증가

2. **distinct finding 분석**
   - analytics endpoint는 fingerprint latest meaningful state 기준
   - rule weight도 fingerprint 단위로 집계

즉, 코드베이스는 이미 아래 방향으로 설계되어 있다.

- 운영 관측은 event
- 품질 평가는 fingerprint

V5는 이를 문서 수준에서도 명시적으로 고정한다.

### 5.2 Plane A — Operational Metrics (Prometheus)

Prometheus는 아래를 본다.

- publish volume
- suppress volume
- resolve event volume
- verify attempt / drop
- feedback command event
- queue depth / duration / circuit breaker

이 plane의 목적:

- 운영 이상 감지
- 노이즈 추세 관찰
- phase별 처리량 파악

### 5.3 Plane B — Quality Analytics (DB / API / Rollup)

품질 KPI는 아래를 본다.

- distinct fingerprint
- terminal outcome
- resolution reason
- first surfaced timestamp
- fixed timestamp
- feedback outcome

이 plane의 목적:

- 실제로 도움이 되는 코멘트 비율 판단
- 학습 / suppression / verify 개선 효과 측정
- 제품 품질 KPI 판단

### 5.4 원칙

- Prometheus counter만으로 `acceptance`나 `conversion`을 정의하지 않는다.
- distinct finding이 필요한 KPI는 DB analytics 또는 materialized rollup에서 계산한다.
- Prometheus는 품질 KPI의 proxy를 보여줄 수는 있지만 canonical source는 아니다.

## 6. Canonical KPI 정의

### 6.1 운영 지표와 품질 KPI를 분리한다

운영 지표:

- `publish_volume_7d`
- `suppress_volume_7d`
- `feedback_ignore_rate_7d`
- `verify_drop_rate_7d`

품질 KPI:

- `fix_confirmation_rate_14d`
- `fix_conversion_rate_28d`
- `human_resolve_rate_14d`
- `false_positive_feedback_rate_14d`

### 6.2 운영 지표 — Prometheus 기반

Prometheus counter는 누적값이므로
window 기반으로 `increase(...)` 또는 recording rule을 사용한다.

예시:

```promql
sum(increase(findings_published_total[7d]))
```

```promql
sum(increase(feedback_commands_total{command=~"ignore|false-positive"}[7d]))
/
clamp_min(sum(increase(findings_published_total[7d])), 1)
```

```promql
sum(increase(verify_dropped_total[7d]))
/
clamp_min(sum(increase(verify_attempts_total[7d])), 1)
```

주의:

- raw `sum(counter)` 비율은 canonical KPI로 쓰지 않는다.
- regex matcher는 `warning|critical`처럼 사용한다.

### 6.3 품질 KPI — Distinct Fingerprint Analytics 기반

#### `fix_confirmation_rate_14d`

정의:

- 최근 14일 동안 resolved된 distinct fingerprint 중
  `resolution_reason = fixed_in_followup_commit`인 비율

식:

```text
fixed_distinct_14d / resolved_distinct_14d
```

#### `fix_conversion_rate_28d`

정의:

- 최근 28일 cohort에서 first-surfaced된 distinct fingerprint 중
  first surfaced 후 28일 이내에 `fixed_in_followup_commit`으로 전환된 비율

식:

```text
converted_cohort_28d / surfaced_cohort_28d
```

중요:

- 이 KPI는 **cohort-based**다.
- `published + resolved` 같은 event 합계로 대체하지 않는다.

#### `human_resolve_rate_14d`

정의:

- 최근 14일 resolved된 distinct fingerprint 중
  사람이 실제 resolve한 비율

초기에는 아래 두 값을 분리해서 본다.

- `fixed_in_followup_commit`
- `remote_resolved_manual_only`

### 6.4 Canonical KPI source 제안

V5는 아래 둘 중 하나를 권장한다.

1. 새 analytics endpoint
   - `/internal/analytics/finding-outcomes`
2. materialized rollup / scheduled aggregation

반환 예시:

```json
{
  "window": "28d",
  "project_ref": "group/repo",
  "surfaced_distinct": 120,
  "resolved_distinct": 70,
  "fixed_distinct": 48,
  "manual_resolved_distinct": 22,
  "ignored_distinct": 15,
  "false_positive_distinct": 9
}
```

### 6.5 왜 기존 `/internal/analytics/rule-effectiveness`와 방향이 맞는가

현재 analytics endpoint와 rule learning은 이미 distinct fingerprint 철학을 따른다.

- latest meaningful state per fingerprint
- reopened finding 처리
- rerun row가 earlier surfaced state를 덮지 않도록 설계

즉, V5의 canonical KPI source 분리는
새 철학을 추가하는 것이 아니라 **현재 코드 철학을 끝까지 밀어붙이는 것**이다.

## 7. Baseline과 Instrumentation 순서

### 7.1 Baseline v0 — 현재 지표

현재 코드에서 바로 볼 수 있는 것만 측정한다.

- `findings_published_total`
- `findings_resolved_total`
- `findings_suppressed_total`
- `/internal/analytics/rule-effectiveness`
- feedback event 빈도
- open backlog 규모

이 단계는 운영 관찰과 noisy 정도 파악용이다.

### 7.2 Instrumentation Phase

Phase A에서 아래를 구현한다.

- `resolution_reason` 확장
- severity taxonomy 확장
- `feedback_commands_total`
- `verify_attempts_total`
- `verify_dropped_total`
- distinct fingerprint outcome analytics endpoint 또는 rollup

### 7.3 Baseline v1 — 운영 지표 + 품질 KPI

배포 후 2주 운영 데이터를 기준으로 아래를 동시에 잡는다.

- Plane A operational metrics baseline
- Plane B quality KPI baseline

즉, V5의 baseline-first는 "한 종류의 숫자"가 아니라
"운영 baseline"과 "품질 baseline"을 함께 잡는 것을 뜻한다.

## 8. Phase 0 — Pre-check

### P0.1 트리거 모델

- (a) 현행 유지: note mention만 실행
- (b) 부분 확장: MR hook은 metadata refresh / sync / optional walkthrough trigger
- (c) 자동 리뷰 확장: baseline 확보 전 금지

권장 default는 (a)다.

### P0.2 `resolution_reason` semantics

현재값과 추가 후보의 의미를 명시적으로 고정한다.

### P0.3 KPI naming

모호한 `acceptance_rate` 대신 아래를 쓴다.

- `fix_confirmation_rate`
- `fix_conversion_rate`

### P0.4 config conflict rule

- 우선순위:
  - `.review-bot.yaml`
  - `policy.json`
  - env
- 값 충돌:
  - strict override
- 단일 파일 내 `allowed_rules ∩ suppressed_rules != ∅`
  - bot error

## 9. 강화된 로드맵

### Phase A (2-4주) — Trust Foundation

- `A1. resolution_reason 확장`
  - `fixed_in_followup_commit`
  - `remote_resolved_manual_only`
- `A2. severity / score 분리`
  - `nitpick / suggestion / warning / critical`
  - 기존 `low / medium / high`는 alias
- `A3. verify phase v1`
  - low-confidence finding에 LLM self-check
- `A4. distributed rate limit`
  - Redis sliding window
- `A5. instrumentation`
  - `feedback_commands_total{command}`
  - `verify_attempts_total{mode}`
  - `verify_dropped_total{mode, reason}`
- `A6. fingerprint outcome analytics`
  - `/internal/analytics/finding-outcomes` 또는 rollup 추가

### Phase B (4-8주) — Context

- syntax-aware review unit split
- related file retrieval
- finding-level second retrieval

### Phase C (8-12주) — Learning + UX

- `(project_ref, rule_no)` weight
- similarity-based learned suppression
- `.review-bot.yaml`
- `@review-bot summarize`
- `@review-bot ask <question>`

### Phase D (12주+) — Automation

- `@review-bot apply`
- low-priority collapsed output
- 조건부 multi-reviewer 병렬화

조건부 defer 해제 조건:

1. `fix_conversion_rate_28d` plateau
2. 단일 verify pipeline의 false-positive 저감 효과 정체

## 10. 상세 설계 스케치

### 10.1 Verify Phase 흐름

```text
Detect
  -> candidate
  -> verify_attempts_total.inc()
  -> self-check / pattern-check
  -> verify_dropped_total.inc() if dropped
  -> eligible
  -> publish
```

### 10.2 `finding-outcomes` analytics 설계 스케치

핵심 집계 단위는 fingerprint다.

필요한 최소 컬럼/파생값:

- `fingerprint`
- `project_ref`
- `rule_family`
- `first_surfaced_at`
- `first_resolved_at`
- `first_fixed_at`
- `latest_resolution_reason`
- `latest_feedback_command`

cohort 계산 예시:

1. `first_surfaced_at`이 지난 28일인 fingerprint 집합
2. 그 중 `first_fixed_at <= first_surfaced_at + 28d`
3. 비율 계산

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
  allowed_rules: [ORG-MEM-007]
  suppressed_rules: [ORG-STYLE-012]

paths:
  - glob: "tests/**"
    score_adjustment: -0.2
    suppress_rules: [ORG-PERF-001]
  - glob: "src/security/**"
    minimum_score: 0.8
    promote_rules: [ORG-SEC-*]

instructions: |
  이 repo는 대규모 storage engine 코어다.
  - 메모리 소유권과 예외 안전이 최우선.
  - 테스트 코드의 스타일 지적은 피한다.
  - suggestion 블록은 반드시 컴파일 가능해야 한다.

chat:
  ask_enabled: true
  ask_history_turns: 3
```

### 10.4 Walkthrough note

run summary와 walkthrough는 purpose를 분리한다.

- run summary
  - 이번 배치 게시 항목 운영 요약
- walkthrough
  - MR onboarding용 설명

예시:

```markdown
## 🤖 리뷰 봇 — MR 요약

**요지**: ownership API에 malloc→realloc 전환 2건, 테스트 3개 추가.

### 영향
- 수정된 symbol: `owner_alloc`, `owner_release`
- 호출부는 `src/storage/ownership/*.cpp`에 집중

### 주의해서 봐 주세요
- 🔴 `src/storage/ownership/ref.cpp:128` — realloc 실패 경로에서 원래 포인터 leak 가능
- 🟠 `src/storage/ownership/ref.cpp:214` — free() 직후 포인터 재사용 의심
```

## 11. 결론

V5의 최종 판단은 단순하다.

- 현재 리뷰 봇의 구조적 방향은 맞다.
- 가장 큰 기술 부채는 verify phase와 acceptance measurement다.
- context와 UX는 그 다음이다.
- KPI를 잘 세우려면 **Prometheus와 DB analytics를 분리**해야 한다.

즉, V5는 V4의 방향을 부정하는 문서가 아니라,
**V4가 잘못 잡은 KPI 데이터 소스를 바로잡아 실제로 쓸 수 있게 만든 문서**다.

## 부록 A. 현재 코드 참조점

- 파이프라인 엔트리: `review-bot/review_bot/worker.py`
- Detect/publish/sync: `review-bot/review_bot/bot/review_runner.py`
- Metrics 정의: `review-bot/review_bot/metrics.py`
- Rule effectiveness analytics: `review-bot/review_bot/api/main.py`
- Policy: `review-bot/review_bot/policy.py`
- Feedback / thread state: `review-bot/review_bot/db/models.py`

## 부록 B. 참고 자료 `[market-informed]`

- CodeRabbit docs / blog
- Greptile docs / 사례 글
- Graphite Diamond 관련 글
- Cursor Bugbot blog
- Ellipsis architecture / build notes
- Qodo Merge / PR-Agent docs
- Sourcery docs
- GitHub Copilot code review docs
