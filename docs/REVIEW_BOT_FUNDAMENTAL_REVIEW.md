# 리뷰 봇 근원 점검 및 개선 방향 보고서

- 문서 상태: Current — Primary Development Document
- 작성일: 2026-04-21
- 작성 목적: `REVIEW_BOT_FUNDAMENTAL_REVIEW` 계열 토론과 평가를 하나의 개발 기준 문서로 통합한다.
- 함께 볼 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_DECISION_LOG.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_DETAILED_DESIGN.md`

## 0. Executive Summary

현재 `review-bot`의 큰 방향은 맞다.

- inline-first
- `detect -> publish -> sync` 분리
- fingerprint + anchor_signature 기반 dedupe
- `ThreadSyncState` 중심 backlog
- feedback-aware suppression / backlog 처리

이 구조를 뒤집을 필요는 없다.
지금 필요한 것은 "더 많이 잡아내는 봇"이 아니라
"더 믿을 수 있고, 더 맥락을 알고, 더 실행 가능한 봇"이다.

따라서 최우선 과제는 아래 순서로 고정한다.

1. **Trust Foundation**
   - verify phase
   - resolution semantics 정리
   - operational metrics / quality KPI 체계 확립
2. **Context**
   - file-local 한계를 넘는 retrieval 확장
3. **Learning + UX**
   - project-local tuning
   - summarize / ask / walkthrough
4. **Automation**
   - apply
   - multi-reviewer 병렬화 등 고비용 확장

이번 통합 과정에서 가장 중요한 최종 결론은 아래 한 줄이다.

> **Prometheus는 운영 이벤트를 본다.**
> **품질 KPI는 distinct fingerprint analytics로 계산한다.**

이 원칙을 지키지 않으면 rerun / reopen / publication event 누적 때문에
acceptance, conversion, signal/noise 지표가 왜곡된다.

## 1. 현재 시스템의 최종 진단

### 1.1 현재 구조 `[code-verified]`

현재 시스템은 **Note Hook mention 기반 수동 호출형 리뷰어**다.

- 자동 review run 생성 경로:
  - `POST /internal/review/runs`
  - GitLab `Note Hook` mention
- `Merge Request Hook`은 현재 자동 리뷰 게시에 쓰지 않는다.
- 파이프라인은 `detect -> publish -> sync`로 분리되어 있다.

### 1.2 유지할 것

- inline-first UX
- detect / publish / sync 분리
- fingerprint + anchor_signature dedupe
- `ThreadSyncState` 기반 backlog/current-state 모델
- feedback command 파서
- path policy 기반 score 조정

### 1.3 실제 핵심 부채

지금 가장 큰 기술 부채는 아래 둘이다.

1. **verify phase 부재**
   - detect 결과를 publish 전에 재검증하는 단계가 없다.

2. **quality KPI 부재**
   - 현재 counter는 event volume은 보지만,
     distinct finding 기준 품질 판단은 canonical source가 없다.

그 다음 부채는 아래 순서다.

- context / retrieval 한계
- global rule weight의 granularity 부족
- summarize / ask / walkthrough / apply 같은 actionability 부족
- `policy.json + env` 분산 설정

## 2. 최종 결정

### 2.1 트리거 모델

- 기본 모델은 note mention 유지.
- MR hook은 당장 auto inline publish 용도로 쓰지 않는다.
- 필요하면 metadata refresh / sync / optional walkthrough trigger 용도로만 부분 도입한다.
- baseline-v1 확보 전 auto inline publish는 금지한다.

### 2.2 KPI naming

모호한 `acceptance_rate`는 기본 문서 용어로 쓰지 않는다.
아래 두 개로 분리한다.

- `fix_confirmation_rate`
  - resolved distinct finding 중 실제 fix 근거가 확인된 비율
- `fix_conversion_rate`
  - surfaced cohort 중 SLA 내 fixed로 전환된 비율

### 2.3 측정 모델

측정은 2-plane으로 분리한다.

**Plane A — Operational Metrics**

- publish / suppress / resolve event volume
- verify attempt / drop
- feedback command event
- queue depth / duration / circuit breaker

**Plane B — Quality Analytics**

- distinct fingerprint
- first surfaced timestamp
- first fixed timestamp
- latest resolution reason
- feedback outcome
- cohort-based conversion

### 2.4 canonical source

- Plane A는 Prometheus 기반이다.
- Plane B는 `/internal/analytics/finding-outcomes`를 canonical source로 둔다.
- 필요하면 후속 단계에서 rollup/materialized aggregation을 추가한다.

### 2.5 설정 방향

- `.review-bot.yaml`은 기능 확장이 아니라 설정 수렴이다.
- 우선순위는 `.review-bot.yaml` > `policy.json` > env.
- 단일 파일 내 `allowed_rules ∩ suppressed_rules != ∅`는 bot error다.

### 2.6 defer 원칙

아래 항목은 폐기가 아니라 **조건부 defer**다.

- cross-repo analysis
- multi-language 대확장
- IDE 실시간 리뷰
- multi-reviewer 병렬화

특히 multi-reviewer 병렬화는 아래 두 조건을 모두 만족할 때만 재평가한다.

1. `fix_conversion_rate_28d`가 2 phase 이상 plateau
2. 단일 verify pipeline의 false-positive 저감 효과가 정체

## 3. 최종 구현 방향

### Phase A — Trust Foundation

반드시 먼저 구현한다.

1. `resolution_reason` 확장
   - `fixed_in_followup_commit`
   - `remote_resolved_manual_only`

2. verify phase v1
   - 초기 적용 범위는 inline comment publish 후보만

3. operational instrumentation 추가
   - `feedback_commands_total{command}`
   - `verify_attempts_total{mode}`
   - `verify_dropped_total{mode, reason}`
   - `finding_resolution_events_total{rule_family, resolution_reason}`

4. quality analytics 기반 마련
   - immutable lifecycle history 저장
   - `/internal/analytics/finding-outcomes` endpoint 추가

5. baseline 체계 확립
   - `baseline-v0`
   - instrumentation
   - `baseline-v1`

### Phase B — Context

- syntax-aware review unit split
- related file retrieval
- finding-level second retrieval

### Phase C — Learning + UX

- `(project_ref, rule_no)` 또는 유사 granularity의 learned weight
- similarity-aware suppression / memory
- `.review-bot.yaml`
- `@review-bot summarize`
- `@review-bot ask <question>`
- walkthrough note

### Phase D — Automation

- `@review-bot apply`
- low-priority collapsed output
- 조건부 multi-reviewer 병렬화

## 4. Baseline과 성공 기준

### 4.1 Baseline v0

현재 있는 것만 본다.

- `findings_published_total`
- `findings_resolved_total`
- `findings_suppressed_total`
- `/internal/analytics/rule-effectiveness`
- feedback event volume

이 단계는 canonical quality KPI가 아니라 운영 관찰과 noisy 정도 파악용이다.

### 4.2 Baseline v1

Instrumentation 이후 아래 둘을 함께 기록한다.

- Plane A operational baseline
- Plane B quality baseline

### 4.3 canonical KPI

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

## 5. 이번 라운드에서 정리된 중요한 사실

이번 문서 시리즈를 통해 아래가 정리되었다.

1. 원래 문서의 큰 방향은 맞았지만,
   naming, baseline 순서, metric semantics는 반복 보정이 필요했다.
2. Claude와 Codex가 서로의 핵심 주장을 무시한 것은 아니었다.
   문제는 주로 "좋은 원칙을 실제 구현 가능한 정의로 내리는 과정"에서 생겼다.
3. V5에서 Plane A/B 분리가 확정되며
   가장 큰 measurement 혼선이 정리되었다.
4. 이제 추가로 필요한 것은 새 버전 통합 문서의 반복 생산보다
   decision log와 detailed design에 기반한 개발 실행이다.

## 6. 개발자가 실제로 볼 문서

앞으로 이 주제를 다룰 때는 아래 세 문서만 primary set으로 본다.

1. `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
   - 왜 이 방향으로 가는지
   - 무엇을 우선 구현할지

2. `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_DECISION_LOG.md`
   - 이미 닫힌 결정
   - 다시 논쟁하지 않을 규칙

3. `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_DETAILED_DESIGN.md`
   - 실제 구현 설계
   - 코드 touchpoint / schema / endpoint / rollout

이전 평가/보강/메타 평가 문서는 모두 archive로 보관한다.

## 7. 최종 결론

최종 판단은 단순하다.

- 현재 리뷰 봇의 구조적 방향은 맞다.
- 가장 큰 기술 부채는 verify phase와 quality measurement다.
- context와 UX는 그 다음이다.
- KPI를 제대로 세우려면 **Prometheus와 quality analytics를 분리**해야 한다.
- quality analytics를 제대로 구현하려면 **immutable lifecycle history**가 필요하다.

즉, 이제 필요한 것은 새 철학이 아니라
이미 합의된 원칙을 기준으로 한 **개발 실행**이다.
