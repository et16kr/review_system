# 리뷰 봇 근원 점검 및 개선 방향 보고서 (V4, 통합판)

- 문서 상태: Current — 실행 기준 문서
- 작성일: 2026-04-21
- 작성자: Claude (병합 작업)
- 이전 버전:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md` (원본, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md` (Codex 1차 평가, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md` (Codex 1차 보강본, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md` (Claude 2차 메타 평가, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md` (Claude 1차 통합본, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2_EVALUATION.md` (Codex V2 평가, archival)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V3.md` (Codex V2 보정본, superseded)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V3_META_EVALUATION.md` (Claude V3 메타 평가, archival)

## 0. 이 문서를 왜 만드는가

V3는 V2의 KPI/metric/phase 충돌을 구조적으로 해결했지만,
**PromQL이 아직 존재하지 않는 metric label을 전제로 쓰인다**는 V2의 함정을
더 미묘한 형태로 재발했다 (`V3_META_EVALUATION` §3.2.1 참조).

V4는 방향을 뒤집지 않고, V3의 잔존 gap 7개를 보정한다.

- PromQL 유효성의 **선행 label/taxonomy migration 의존**을 명시한다.
- `.review-bot.yaml` vs `policy.json` **값 단위 충돌 해결 규칙**을 고정한다.
- `verify_dropped_total{mode}` 등 신설 counter의 **label value set**을 고정한다.
- Ellipsis 병렬 reviewer의 **조건부 defer 재평가 조건**을 복원한다.
- Phase naming 변경의 **이력 주석**을 남긴다.

한 파일만 읽고도 설계/구현/측정 기준을 잡을 수 있는 실행 기준 문서로 유지한다.

> 이후 변경은 V4에서 이어간다. 앞선 문서들은 이력으로 남기고 변경하지 않는다.

## 1. Executive Summary

현재 `review-bot`은 **"inline-first, lifecycle-aware, feedback-aware" 구조로서 방향이 맞다.**

유지할 핵심:

1. inline discussion을 canonical UI로.
2. `detect -> publish -> sync` 파이프라인.
3. `ThreadSyncState`를 current backlog의 source of truth.
4. feedback command를 thread reply에서 해석.
5. 다음 투자는 "탐지량"이 아니라 "신뢰도, context, actionability".

V4의 한 줄 요약:

> `review-bot`의 다음 단계는 "더 많이 지적하는 봇"이 아니라
> "더 믿을 수 있고, 더 맥락을 알고, 더 실행 가능한 제안을 하는 봇"이어야 한다.

## 2. 증거 층위 규칙

- `[code-verified]` — 현재 저장소 코드와 직접 대조 가능한 사실.
- `[design-inference]` — 코드/구조 기반 설계 해석.
- `[market-informed]` — 외부 제품 문서 / 블로그 / vendor self-report 기반 참고치.

명시적 태그가 없는 문장은 기본 `[design-inference]`로 본다.

## 3. 현재 시스템 지형

### 3.1 트리거 모델 `[code-verified]`

`review-bot`은 **Note Hook mention 기반 수동 호출형 리뷰어**다.

- `review_bot/api/main.py:191-197`: `Merge Request Hook`은
  `manual_review_requires_bot_mention_comment`로 명시적 무시.
- 실 review run 생성 경로는 (a) `POST /internal/review/runs` 내부 API,
  (b) Note Hook mention 두 가지뿐.

이 전제는 walkthrough 자동 게시 / acceptance freshness / sync 주기 설계에 직접 영향.
V4도 이 전제를 **유지**하고, Phase C에서 optional auto-trigger 도입 여부만 재평가한다.

### 3.2 파이프라인 개요 `[code-verified]`

```
GitLab Note Hook
     │
     ▼
[ Webhook API (rate limit, explicit command parser) ]
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
[ backlog / full-report / help general note ]
```

### 3.3 현재 `resolution_reason` 상태값 `[code-verified]`

`review_bot/bot/review_runner.py`에서 실제 대입되는 값 5개:

| 값 | 위치 |
| --- | --- |
| `anchor_changed` | line 608 |
| `no_longer_eligible` | line 851 |
| `resolve_failed` | line 858 |
| `remote_resolved` | line 1565 |
| `remote_reopened` | line 1574 |

V4에서 추가 검토하는 값:

- `fixed_in_followup_commit`
- `remote_resolved_manual_only`

즉 문서와 코드에서 **현재값 vs 추가 후보**를 구분해 서술한다.

### 3.4 현재 강점 `[code-verified]`

- inline-first UX.
- queue 기반 detect / publish / sync 분리.
- `ThreadSyncState` 기반 backlog.
- reply 기반 feedback command 해석.
- fingerprint + anchor_signature dedupe.
- path policy 기반 score 조정.
- current-state backlog view.
- explicit command parser.
- worker-scoped SQLite test DB (`tests/conftest.py:8-16`).
- process-local rate-limit 한계를 코드 주석이 이미 경고.

### 3.5 현재 한계

- `[code-verified]` context = 현재 파일 `file_context` 4000자.
- `[design-inference]` review unit split이 lexical / hunk 기반.
- `[design-inference]` verify phase 부재.
- `[code-verified]` severity = `_severity_from_score`의 파생값 (`low/medium/high`).
- `[code-verified]` rule weight = `rule_no` global.
- `[design-inference]` 실제 코드 수정 유발 여부 미측정.
- `[code-verified]` `ask` / `summarize` / `apply` 커맨드 없음.
- `[code-verified]` 설정 표면이 `policy.json + env` 분산.
- `[code-verified]` run summary note는 있지만 walkthrough 역할은 못 함 (`_post_pr_summary`, `review_runner.py:2303`).

## 4. 업계 비교 사용 규칙

> 이 절의 수치와 제품 특징은 `[market-informed]`이며 vendor self-report를 포함한다.
> 방향성 참고치로만 사용. KPI 목표의 직접 근거로 사용하지 않는다.

업계 수렴 패턴:

1. `flag → verify → post` 3단 구조.
2. learned rules / knowledge base.
3. severity 정책 분리(critical / warning / suggestion / nitpick).
4. walkthrough의 별도 산출물화.
5. acceptance 계열 KPI.
6. 검증된 auto-fix만 허용.
7. repo-local config 수렴.

## 5. Gap 분석

### 5.1 신뢰도 (Must-fix)

- acceptance 직접 측정 없음 (`fix_confirmation_rate` / `fix_conversion_rate` 부재).
- verify phase 부재.
- severity가 score의 종속.

### 5.2 Context (High)

- 단일 파일 중심 context.
- syntax-aware가 아닌 review unit split.
- finding-level second retrieval 부재.

### 5.3 Learning (High)

- `(project_ref, rule_no)` 단위 학습 부재.
- similarity-based suppression 부재.

### 5.4 UX / Actionability (High)

- walkthrough 부재 (run summary와는 다름).
- `ask` 부재.
- `apply` 부재.

### 5.5 운영 / Observability (Medium)

- process-local rate limit.
- metric 체계가 다음 KPI를 직접 뒷받침하지 못함 (label 확장 선행 필요).
- config 표면 분산.

### 5.6 장기 / 조건부 Defer

- cross-repo analysis, multi-lang 대확장, IDE 실시간 리뷰: acceptance baseline 확보 전까지 후순위.
- **multi-reviewer 병렬화 (Ellipsis 방식, `[market-informed]`):**
  단순 "과투자" 치부가 아니라 **verify phase 확장 경로로서 조건부 defer**.
  **재평가 조건:** Phase A/B 완료 후 (a) `fix_conversion_rate` plateau가 관측되고
  (b) 단일 verify pipeline이 false-positive를 더 못 줄이는 상태가 실측될 때.
  Phase D3에서 재평가한다.

## 6. 유지 / 재검토 판정

### 6.1 유지할 결정

- inline-first review UX.
- detect / publish / sync 분리.
- feedback command를 thread reply에서 해석.
- `ThreadSyncState` 중심 backlog / analytics.
- path policy 기반 score 조정.
- run summary + full-report / backlog / help의 보조 인터페이스 구조.

### 6.2 재검토할 결정

- `severity = f(score)` → provider/engine이 severity를 자기주장.
- `rule_no` global weight → `(project_ref, rule_no)` 단위.
- note-only trigger 유지 기간.
- run summary note append-only 여부.
- `policy.json + env` 분산 설정.

## 7. Phase 0 — Pre-check

> Phase 0는 **결정 작업**이다. 구현 phase가 아니다.
> 회의 1–2회 수준에서 끝나는 것이 정상.

### P0.1 트리거 모델 결정

- (a) 현행 유지: MR hook 무시, note mention만. **권장 default**.
- (b) 부분 확장: MR hook은 metadata refresh / sync / optional walkthrough trigger만.
- (c) 자동 리뷰 확장: acceptance baseline 확보 전까지 **금지**.

### P0.2 `resolution_reason` 의미 확정

- 현재값 5개 유지 (§3.3).
- 추가 후보 2개(`fixed_in_followup_commit`, `remote_resolved_manual_only`)의 semantics 합의.
- naming은 현 코드의 `resolution_reason`으로 통일.

### P0.3 KPI 용어 확정

V4는 모호한 `acceptance_rate` 대신 아래 두 개를 구분한다.

- **`fix_confirmation_rate`** — resolved된 것 중 실제 fix 근거가 확인된 비율.
- **`fix_conversion_rate`** — surfaced(published + resolved)된 것 중 실제 fix로 이어진 비율.

외부 커뮤니케이션에서 `acceptance_rate`라는 말을 쓴다면
기본값은 `fix_conversion_rate`로 간주하되,
**대시보드에는 별도 이름**을 쓰는 것을 권장.

### P0.4 `.review-bot.yaml` 충돌 해결 정책 합의

(V4 신규) 설정 파일 간 우선순위와 **값 단위 충돌 해결 규칙**을 확정한다.

- 파일 우선순위: `.review-bot.yaml` > `policy.json` > env.
- 값 단위 충돌은 **strict override** — 상위 파일의 명시값이 항상 이긴다.
- 같은 rule이 상위 파일 `allowed_rules`에 있고 하위 파일 `suppressed_rules`에 있으면
  상위 파일이 이긴다. 그 반대도 동일.
- 단일 파일 내에서 `suppressed_rules`와 `allowed_rules` 교집합은 **bot error**로 처리해
  silent ambiguity 방지.

## 8. Baseline과 Instrumentation 순서

V4는 V3의 3단 분리를 그대로 유지한다 (`baseline-v0` → `instrumentation` → `baseline-v1`).
**V3가 빠뜨린 label 의존성**을 §8.2–§8.4에서 명시한다.

### 8.1 Baseline v0 — 현재 지표 기준

아직 구현되지 않은 분류나 metric을 쓰지 않는다.
현재 코드에서 바로 측정 가능한 것만 본다.

수집 항목:

- `findings_published_total{severity, rule_family}` (현재 label 기준)
- `findings_resolved_total{rule_no}` (현재 label 기준)
- `findings_suppressed_total{reason}`
- `/internal/analytics/rule-effectiveness` 응답
- feedback command 빈도 (현재는 DB `FeedbackEvent`에서 집계; counter는 아직 없음)
- inline publish 실패 분포
- open thread / backlog 규모

**목적:** "현재 상태의 noisy 정도"와 rule별 resolve 경향을 잡는다.

### 8.2 Instrumentation Phase — 새 metric / label 도입 (Phase A)

> **이 phase가 완료되어야 §8.3 PromQL이 유효해진다.**

구현 항목:

- `findings_resolved_total`에 `resolution_reason` label **추가**
  (현재는 `rule_no`만 있음. 코드: `review_bot/metrics.py:23-27`).
- `findings_published_total`의 `severity` label value를
  새 taxonomy(`nitpick | suggestion | warning | critical`)로 **확장** — 기존 `low/medium/high`는 alias.
- 새 counter:
  - `feedback_commands_total{command}` — `command ∈ {ignore, false-positive, later, allow}`.
  - `verify_attempts_total{mode}` — `mode ∈ {llm_self_check, pattern_execution}`.
  - `verify_dropped_total{mode, reason}` — `reason`은 `low_confidence | llm_self_check | ...` 네임스페이스.
- `resolution_reason` 확장:
  - `fixed_in_followup_commit`
  - `remote_resolved_manual_only`

### 8.3 KPI 정의와 PromQL — **§8.2 완료 후 유효**

> 아래 PromQL은 **Phase A1(label 확장) + A2(severity migration) 완료 후 유효**하다.
> Phase 진행 중에는 §8.5의 fallback PromQL 사용.

| KPI | 정의 | PromQL (Phase A 완료 후) |
| --- | --- | --- |
| `fix_confirmation_rate` | resolved finding 중 실제 fix 확인 비율 | `sum(findings_resolved_total{resolution_reason="fixed_in_followup_commit"}) / sum(findings_resolved_total)` |
| `fix_conversion_rate` | surfaced finding 중 실제 fix 비율 | `sum(findings_resolved_total{resolution_reason="fixed_in_followup_commit"}) / (sum(findings_published_total) + sum(findings_resolved_total))` |
| `signal_ratio` | warning 이상 비중 | `sum(findings_published_total{severity=~"warning\|critical"}) / sum(findings_published_total)` |
| `ignore_rate` | ignore/false-positive 비중 | `sum(feedback_commands_total{command=~"ignore\|false-positive"}) / sum(findings_published_total)` |
| `verify_drop_rate` | verify 대상 중 drop 비율 | `sum(verify_dropped_total) / sum(verify_attempts_total)` |

### 8.4 label 설계 원칙

- Prometheus에는 `rule_no` 대신 `rule_family`를 기본으로.
  `rule_no` 단위 drill-down은 `/internal/analytics/*` 또는 warehouse.
- label value set은 **닫힌 집합**으로 고정 (cardinality 관리).
  - `command`: 4개.
  - `mode`: 2개 시작.
  - `resolution_reason`: 5 + 2개 (현재 + 추가 후보).
- Prometheus에서 top-N / `__other__` 동적 grouping은 피한다.

### 8.5 Baseline v0 단계의 Fallback PromQL

Instrumentation 완료 전 운영 모니터링용.

| 지표 | Fallback (현재 label로 계산 가능) |
| --- | --- |
| "resolve 비율" (proxy) | `sum(findings_resolved_total) / (sum(findings_published_total) + sum(findings_resolved_total))` |
| "high-priority 비중" (proxy) | `sum(findings_published_total{severity="high"}) / sum(findings_published_total)` |
| "suppress 비율" | `sum(findings_suppressed_total) / (sum(findings_published_total) + sum(findings_suppressed_total))` |

이 fallback들은 Phase A1/A2 완료 후 §8.3의 canonical PromQL로 **교체**하고,
baseline-v1 집계를 다시 잡는다.

### 8.6 Baseline v1 — 새 지표 기준 soak

Instrumentation 배포 후 짧은 운영 구간(2주 권장)을 둔다.
이때부터 §8.3 PromQL로 canonical baseline을 기록한다.

### 8.7 해석 규칙

- `resolved`는 곧 fix가 아니다 (`remote_resolved` vs `fixed_in_followup_commit` 구분).
- `suppressed` 감소만으로 성공 판단 금지.
- published count 증가를 성공 지표로 쓰지 않는다.
- vendor benchmark를 직접 목표 수치로 고정하지 않는다.

### 8.8 1차 목표 설정 방식

절대 목표치를 문서에 박지 않는다. baseline-v1 대비 **개선폭**으로 관리.

- verify 도입 후 `ignore_rate` baseline-v1 대비 20% 이상 감소.
- context 강화 후 `fix_conversion_rate` baseline-v1 대비 10pt 이상 개선.
- walkthrough 도입 후 reviewer onboarding 시간 정성 피드백 개선.

### 8.9 시장 참고치 (KPI 목표 아님) `[market-informed]`

- Diamond: false positive < 3% (vendor self-report).
- Bugbot: resolution rate ~80% (vendor blog).
- Greptile: addressed comments 19% → 55% 개선 사례.

**내부 목표는 위 수치를 직접 차용하지 않는다.**
baseline-v1 대비 20–30% 개선이 현실적 1차 목표.

## 9. 강화된 로드맵

> Phase 기간은 예시. team velocity에 맞춰 조정.
> Phase 0는 결정 작업이지 implementation phase가 아니다.
>
> **Phase naming 이력** (V2 → V3 → V4):
> - V2/V1 원본에서 A1 = "acceptance tracking 추가"
> - V3에서 A1 = "resolution_reason 확장"으로 rename
> - V4는 V3의 naming을 계승.

### Phase A (2–4주) — Trust Foundation

- **A1. `resolution_reason` 확장 + `findings_resolved_total` label 확장 (선행 의존)**
  - `resolution_reason`에 `fixed_in_followup_commit`, `remote_resolved_manual_only` 추가.
  - sync phase에서 resolved transition 시 후속 commit diff로
    `file_path:line_no ± 3 lines` 변화 유무를 판정.
  - **동시에** `findings_resolved_total` counter에 `resolution_reason` label 추가.
    (현재는 `rule_no` 하나뿐. 이 작업이 없으면 §8.3 PromQL이 전부 무효.)
- **A2. Severity / Score 분리**
  - `FindingDecision.severity`를 provider/engine의 자기주장값으로 보존.
  - 새 taxonomy `nitpick / suggestion / warning / critical`.
  - 기존 `low/medium/high`는 alias로 유지하며 점진 migration.
  - **주의:** 이 migration이 완료되기 전에는 §8.3의 `signal_ratio` PromQL이 match 안 함.
    Baseline v0 단계에서는 §8.5 fallback 사용.
- **A3. Verify phase v1**
  - `BOT_VERIFY_WITH_LLM_CONFIDENCE` env. 저확신도 finding에 LLM self-check.
  - drop 이유 네임스페이스: `verify:llm_self_check`, `verify:low_confidence`.
- **A4. Distributed rate limit**
  - `api/main.py`의 per-IP deque → Redis sliding window.
- **A5. Instrumentation 추가**
  - `feedback_commands_total{command}` — label value 4개 고정.
  - `verify_attempts_total{mode}` — `mode ∈ {llm_self_check, pattern_execution}`.
  - `verify_dropped_total{mode, reason}`.

### Phase B (4–8주) — Context

- **B1. Syntax-aware review unit split** — tree-sitter 기반 함수 경계. C/C++ 먼저.
- **B2. Related file retrieval** — touched symbol 기준 정의/참조 1-hop excerpt.
  payload 구조화: `primary_file_context + related_contexts`.
- **B3. Finding-level second retrieval (optional)** — finding title+summary mini-query.

### Phase C (8–12주) — Learning + UX

- **C1. `(project_ref, rule_no)` weight** — `_load_rule_effectiveness_weights(scope=...)`.
  5건 임계 대신 Bayesian smoothing.
- **C2. Similarity-based learned suppression**
  - 초기: (title + summary + file_path) 문자열 유사도(`difflib`) ≥ 0.9면
    `suppressed(reason=learned:similar_ignore)`.
  - 후속: in-process FAISS embedding. 규모 확인 후.
- **C3. `.review-bot.yaml` 도입** (설정 수렴, 기능 확장 아님)
  - 스키마는 §11.3.
  - 충돌 해결 규칙은 P0.4에서 합의한 strict override.
- **C4. Walkthrough note**
  - 1차: on-demand `@review-bot summarize`.
  - 2차: optional MR 오픈 auto-post (P0.1이 (b)로 확장된 경우만).
  - run summary와 **다른 purpose**로 `upsert_general_note(purpose="walkthrough")`.
- **C5. `@review-bot ask <질문>`**
  - thread + diff + 관련 파일 excerpt 기반 답변. thread reply로 게시.
  - history 3턴.

### Phase D (12주+) — Automation

- **D1. `@review-bot apply`**
  - 확신도 ≥ 0.9 + suggestion 라인 ≤ 5 + build/lint pass 조합에서만.
  - branch 생성 → patch → push. merge는 사람이.
- **D2. Collapsed low-priority output**
  - `nitpick` / `suggestion`은 GitLab `<details>` 접힘.
- **D3. (조건부) Multi-reviewer 병렬화**
  - **defer 해제 조건:**
    1. `fix_conversion_rate` plateau (baseline-v1 대비 유의미한 추가 개선이 2 phase 이상 관찰되지 않음).
    2. 단일 verify pipeline이 false-positive를 더 못 줄이는 것이 실측됨.
  - 초기 구성 예시: (a) rule-based (현 엔진), (b) security-focused LLM, (c) performance-focused LLM.
    결과는 filter pipeline에서 dedupe.
  - `[market-informed]` Ellipsis 패턴 참고.
  - **폐기가 아닌 조건부 defer.**

## 10. 상세 설계 스케치

### 10.1 Verify Phase 흐름

```
Detect → FindingDecision(state=eligible, confidence=c, source_signals={...})
         │
         ▼
   verify_attempts_total{mode}.inc()
   if c < VERIFY_THRESHOLD:
         │
         ▼
   LLM_self_check(prompt=[finding, evidence, change_snippet])
         │
         ▼
   {is_real_bug: bool, reasons: [str], new_confidence: float}
         │
   is_real_bug == False
     → state=suppressed, reason="verify:llm_self_check"
     → verify_dropped_total{mode="llm_self_check", reason="not_a_real_bug"}.inc()
   new_confidence < minimum
     → state=suppressed, reason="verify:low_confidence"
     → verify_dropped_total{mode="llm_self_check", reason="low_confidence"}.inc()
```

- hook 위치: `review_runner.py`의 `_build_decision` 이후, `FindingDecision` 생성 전 혹은 직후.
- `mode`는 향후 `pattern_execution` 같은 다른 검증 전략을 수용하기 위한 확장 슬롯.

### 10.2 Acceptance / Fix Tracking

핵심은 `resolved`를 둘로 쪼개 보는 것이다.

- `fixed_in_followup_commit`
  - resolved 시점 이후 commit diff가 `file_path:line_no ± 3 lines`를 실제 touch.
- `remote_resolved_manual_only`
  - 사용자가 resolve만 눌렀고 코드 변경 근거 없음.

이 구분이 있어야 `fix_confirmation_rate`와 `fix_conversion_rate` 둘 다 계산 가능.

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

- 파일 우선순위: `.review-bot.yaml` > `policy.json` > env.
- **값 단위 충돌 규칙 (strict override)**:
  - 상위 파일의 명시값이 항상 이김.
  - `.review-bot.yaml`의 `suppressed_rules: [X]`가 `policy.json`의 `allowed_rules: [X]`를 이김.
- **단일 파일 내 교차 금지**: 같은 파일에서 `suppressed_rules ∩ allowed_rules ≠ ∅`이면 **bot error**.

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

- run summary와 walkthrough는 **purpose 분리**.
  - run summary: 이번 배치 게시 항목 운영 요약.
  - walkthrough: MR onboarding용 설명.
- 구현: `upsert_general_note(purpose="walkthrough")` — same-purpose upsert.

## 11. 결론

- 현재 구조는 유지 가치가 높다.
- 가장 큰 기술 부채는 여전히 **verify phase 부재** + **acceptance 측정 부재**.
- context 강화는 중요하지만 **trust foundation 뒤**.
- UX 고도화는 신뢰도 기반 위에.
- KPI는 vendor claim이 아니라 **baseline-v1 대비 개선폭**으로 관리.
- PromQL은 **label/taxonomy migration 선행 의존**을 명시한다.
- `.review-bot.yaml` vs `policy.json` 충돌은 **strict override**로 단순화.
- multi-reviewer 병렬화는 **폐기가 아닌 조건부 defer** (§9 D3).

V4는 방향 반전이 아니라 **V3의 label/taxonomy/conflict/조건 defer/이력 gap을 채운 보정본**이다.

## 부록 A. 현재 코드 참조점

- 파이프라인 엔트리: `review-bot/review_bot/worker.py`
- Detect/publish/sync 로직: `review-bot/review_bot/bot/review_runner.py`
- Command parser: `review-bot/review_bot/api/main.py`
- GitLab adapter: `review-bot/review_bot/review_systems/gitlab.py`
- Policy: `review-bot/review_bot/policy.py`
- Analytics endpoint: `review-bot/review_bot/api/main.py` (`/internal/analytics/rule-effectiveness`)
- Metrics 정의: `review-bot/review_bot/metrics.py`
- Test DB isolation: `review-bot/tests/conftest.py`
- 트리거 무시 지점: `review-bot/review_bot/api/main.py:191-197`
- Run summary: `review-bot/review_bot/bot/review_runner.py:2303` (`_post_pr_summary`)
- Backlog helper: `review-bot/review_bot/bot/review_runner.py::_current_backlog_entries`
- `resolution_reason` 대입 위치: `review_runner.py:608/851/858/1565/1574`
- `findings_resolved_total` label 현재값: `metrics.py:23-27` (현재 `rule_no` 하나)
- `findings_published_total` 사용 위치: `review_runner.py:599-602`

## 부록 B. 참고 자료 — `[market-informed]`

> vendor self-report 또는 2차 정리글. 내부 KPI 목표의 직접 근거가 아니다.

- CodeRabbit: <https://www.coderabbit.ai/>, <https://docs.coderabbit.ai>
- CodeRabbit – massive codebase: <https://www.coderabbit.ai/blog/how-coderabbit-delivers-accurate-ai-code-reviews-on-massive-codebases>
- Greptile: <https://www.greptile.com>, <https://www.greptile.com/docs/introduction>
- Greptile – embedding 기반 품질 개선 사례: <https://www.zenml.io/llmops-database/improving-ai-code-review-bot-comment-quality-through-vector-embeddings>
- Graphite Diamond: <https://diamond.graphite.dev/>
- Graphite – false positive 기대치: <https://graphite.com/guides/ai-code-review-false-positives>
- Graphite – Diamond eval: <https://www.braintrust.dev/blog/graphite>
- Cursor Bugbot: <https://cursor.com/bugbot>
- Bugbot learned rules: <https://cursor.com/blog/bugbot-learning>
- Bugbot autofix: <https://cursor.com/blog/bugbot-autofix>
- Ellipsis: <https://www.zenml.io/llmops-database/building-and-deploying-production-llm-code-review-agents-architecture-and-best-practices>, <https://www.ellipsis.dev/blog/how-we-built-ellipsis>
- Qodo Merge / PR-Agent: <https://github.com/qodo-ai/pr-agent>, <https://qodo-merge-docs.qodo.ai/>
- Sourcery: <https://www.sourcery.ai/>, <https://docs.sourcery.ai/Code-Review/Overview/>
- GitHub Copilot code review: <https://docs.github.com/en/copilot/concepts/agents/code-review>
- 노이즈/신호 프레임워크: <https://dev.to/jet_xu/drowning-in-ai-code-review-noise-a-framework-to-measure-signal-vs-noise-304e>
- Cloudflare – AI 코드 리뷰 오케스트레이션: <https://blog.cloudflare.com/ai-code-review/>
- CodeRabbit – 평가 프레임워크: <https://www.coderabbit.ai/blog/framework-for-evaluating-ai-code-review-tools>
- RAG/코드 그래프 조사: <https://arxiv.org/html/2510.04905v1>
