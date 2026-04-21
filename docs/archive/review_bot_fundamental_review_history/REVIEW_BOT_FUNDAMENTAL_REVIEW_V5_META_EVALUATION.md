# Review Bot Fundamental Review — V5 Meta Evaluation

- 문서 상태: Assessment
- 작성일: 2026-04-21
- 작성자: Claude
- 대상 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V4_EVALUATION.md` (Codex의 V4 평가)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V5.md` (Codex의 V4 보정본)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_DOCUMENT_FLOW_ASSESSMENT.md` (Codex의 흐름 평가)

## 0. 이 문서를 왜 만드는가

Codex가 V4에 대해 세 개의 문서로 응답했다.

- `V4_EVALUATION`은 V4의 **KPI 데이터 소스 오류**를 제기한다.
- `V5`는 그 지적을 수용해 **Prometheus(운영) vs DB analytics(품질)** 2-plane 모델을 도입한다.
- `DOCUMENT_FLOW_ASSESSMENT`는 이 문서 시리즈 전체가 수렴하고 있는지를 독립적으로 평가한다.

이번 평가의 목적은 세 가지다.

1. V4_EVALUATION의 핵심 기술 주장을 코드로 검증한다.
2. V5가 그 지적을 완전히 해소했는지, 과정에서 **V4의 유용한 세부 detail을 잃지는 않았는지** 본다.
3. FLOW_ASSESSMENT가 제안한 "decision log" 아이디어가 얼마나 실효성이 있는지 판단한다.

결론부터 쓰면:

- V4_EVALUATION의 핵심 critique는 **코드로 완전히 검증된다. 재반박 불가.**
- V5의 Plane A/B 분리는 **진짜 advance다.** 이 방향이 맞다.
- 단, V5는 V4의 일부 **구현 디테일을 상실했다**. 새 문서 V6을 쓰기보다는
  **decision log로 고정하고 V5를 archival로 내리지 않는 편**이 더 나은 판단이다.
- FLOW_ASSESSMENT의 decision log 제안이 **이번 라운드의 가장 큰 기여**다.
  단 스스로는 decision log를 쓰지 않았다. 이 공백은 별도 문서
  `REVIEW_BOT_FUNDAMENTAL_REVIEW_DECISION_LOG.md`로 채운다.

## 1. V4_EVALUATION 핵심 주장 검증

### 1.1 `findings_resolved_total`이 event counter인가, distinct-finding counter인가 — **코드로 검증됨**

`review_bot/bot/review_runner.py:1486-1503` `_mark_fingerprint_resolved`:

```python
def _mark_fingerprint_resolved(self, session, review_request_pk, fingerprint):
    decisions = (
        session.query(FindingDecision)
        .filter(
            FindingDecision.review_request_pk == review_request_pk,
            FindingDecision.fingerprint == fingerprint,
            FindingDecision.state.in_(["eligible", "published", "failed_publication"]),
        )
        .all()
    )
    for decision in decisions:
        decision.state = "resolved"
        findings_resolved_total.labels(rule_no=decision.rule_no or "unknown").inc()
```

즉, **하나의 fingerprint가 resolve되어도 해당 fingerprint의 `FindingDecision` row 수만큼 counter가 증가**한다.
rerun이 많아 한 fingerprint에 3개 row가 쌓였다면 `findings_resolved_total`은 +3이 된다.

`findings_published_total`도 `review_runner.py:599` 부근에서 **publish event마다 증가**한다.
같은 fingerprint의 body 업데이트도 별도 publication으로 집계된다.

반면 현재 analytics / learning은 이미 distinct fingerprint 기반으로 설계돼 있다
(`/internal/analytics/rule-effectiveness`는 최신 meaningful state per fingerprint로 집계,
`_load_rule_effectiveness_weights`도 fingerprint set 기준).

→ Codex의 진단 **완전 일치**. V4가 canonical KPI를 이 counter 비율로 정의한 것은 실제 오류.
이 상태로 구현되면 rerun 빈도에 KPI가 직접 오염된다.

### 1.2 `fix_conversion_rate`의 분모 `published + resolved` 문제 — **개념적 오류 확인**

V4 §8.2의 정의:

```
fix_conversion_rate =
  fixed_in_followup_commit / (published + resolved)
```

- `resolved` event는 거의 언제나 먼저 `published`였던 finding의 후속 lifecycle event.
- 따라서 `published + resolved`는 같은 finding을 **두 번 세는** 구조에 수렴한다.

Codex가 제안한 cohort-based 정의("지난 N일에 first-surfaced된 distinct fingerprint 중 N일 내 fixed로 전환된 비율")가
개념적으로 맞다. → **유효한 보정**.

### 1.3 window 없는 PromQL counter ratio — **Prometheus 원리상 오류**

V4의 대부분 PromQL은 `sum(counter_a) / sum(counter_b)` 형태.
Prometheus counter는 누적값이므로 프로세스 재시작 / scrape 이력 / 오래된 노이즈가 지속적으로 분자·분모에 섞인다.
운영 KPI는 반드시 `increase(...[window])` 또는 recording rule 기반으로 계산해야 한다. → **유효**.

### 1.4 regex escape 지적 (§3.4) — **과한 편집 수준**

V4의 `severity=~"warning\|critical"`의 `\|` escape는 markdown/yaml 표기 관습상 발생한 것이지,
실제 PromQL 쿼리 시 해당 escape가 남아도 대부분 정상 작동한다.
이 지적은 옳긴 하지만 실행 오류를 만들 사안은 아니다. → **minor, 수용 가능**.

### 1.5 fallback proxy 취급 (§3.5) — **수용 가능**

V4의 baseline-v0 fallback PromQL이 여전히 raw counter ratio라는 지적은 맞다.
하지만 "proxy라 못 박고 쓰면 된다"는 V4의 태도 자체도 허용 가능한 선. 표현만 다듬으면 됨.

### 1.6 종합

**V4_EVALUATION의 5개 지적 중 §3.1–§3.3은 material, §3.4–§3.5는 minor.**
material 지적 셋은 모두 코드/Prometheus 원리로 검증된다. 재반박 근거 없음.

## 2. V5 자체 평가

### 2.1 강점 — 중대한 진전

- **Plane A / Plane B 분리**(§5)가 이번 라운드의 핵심 진전. Prometheus = 운영 이벤트, DB analytics = 품질 KPI.
  코드베이스의 실제 철학(`findings_*` counter는 event, `/internal/analytics/rule-effectiveness`는 fingerprint)과
  정확히 일치한다.
- **windowed PromQL** (`increase(...[7d])`, `clamp_min`): Prometheus 원리에 맞는 쿼리.
- **cohort-based `fix_conversion_rate_28d`**: "first surfaced cohort → SLA 내 fixed 전환 비율"로 재정의.
  `published + resolved` double-counting 문제 해소.
- **`/internal/analytics/finding-outcomes` 신 endpoint 제안**(§6.4): canonical source를 코드 수준에서 지정.
- **운영 지표와 품질 KPI를 이름 수준에서 분리**(§6.1): `publish_volume_7d` vs `fix_confirmation_rate_14d`.
- V4의 다른 좋은 판단들(trigger model, P0.4 config conflict, condition-based defer)은 **유지**.

### 2.2 약점 — V4에서 잃어버린 디테일

V5는 **구조적으로는 V4보다 낫지만**, V4가 가지고 있던 구체적 디테일 일부가 **기술 없이 사라졌다**.
이 손실은 "V5가 short하고 focused하다"는 장점과 같은 동전의 뒷면이다.

#### 2.2.1 V4의 fallback PromQL (§8.5) 섹션이 V5에서 사라짐

V4는 severity migration / label 확장 완료 **전** 시점(baseline-v0)에서 쓸 수 있는 fallback PromQL을
§8.5에 명시했다:

- `findings_published_total{severity="high"}` 기반 proxy
- `findings_suppressed_total` 기반 proxy

V5는 이 fallback을 §6.2에서 "regex와 windowed PromQL로 써라"로 대체했는데,
**severity label이 아직 `low/medium/high`인 상태에서는 `severity=~"warning|critical"` 쿼리가 매치 안 한다**.
즉 V5의 PromQL은 여전히 Phase A2 완료 후에야 유효한 상태. 이 전환기 PromQL 처방이 V4에 있었는데 V5에서 사라졌다.

→ decision log에 "baseline-v0 기간에는 기존 severity label 기반 fallback PromQL 허용" 명시 필요.

#### 2.2.2 label value set의 열거가 사라짐

V4는 label value set을 닫힌 집합으로 고정했다:

- `command ∈ {ignore, false-positive, later, allow}`
- `mode ∈ {llm_self_check, pattern_execution}`
- `resolution_reason`: 현재값 5 + 추가 후보 2

V5는 이 열거를 생략했다. cardinality 안전성 원칙이 약화됨.

→ decision log에 그대로 복원 필요.

#### 2.2.3 `.review-bot.yaml` 충돌 규칙 설명이 줄어듦

V4의 "단일 파일 내 `allowed_rules ∩ suppressed_rules != ∅`면 bot error" 규칙은 V5 §8 P0.4에 한 줄로 축약됨.
**규칙 자체는 있음.** 설명이 짧아진 것은 손실이 아니고, 오히려 decision log가 필요한 이유.

#### 2.2.4 Phase naming 이력 각주 소실

V4는 "V2 A1 = acceptance tracking" vs "V3 A1 = resolution_reason 확장"의 renaming 이력을 각주로 남겼다.
V5에서는 이 각주가 사라짐. 다음 세대 독자가 이전 문서를 읽다가 혼란 가능.

→ decision log에 naming history 박스로 유지.

#### 2.2.5 `finding-outcomes` endpoint 설계 해상도 부족

V5 §6.4의 sample response는 유용하지만 아래는 미정:

- `first_surfaced_at`은 어떤 timestamp인가? (`FindingDecision.created_at`의 min? `ThreadSyncState.created_at`?)
- fingerprint가 reopened → re-fixed된 경우 `first_fixed_at`을 첫 fix로 보는가, 최신 fix로 보는가?
- cohort 경계의 timezone 처리는?
- resolved_distinct / fixed_distinct의 교집합/포함관계는?

이 미정 상태로 Phase A6를 들어가면 구현자가 임의 판단하게 되고,
baseline-v1 숫자가 판단에 따라 달라진다.

→ decision log에 "시점 의미는 first 기준(earliest timestamp), reopened 재fixed는 별도 카운트"처럼 **한 번 결정**이 필요.

#### 2.2.6 V5 §7.3 Baseline-v1 정의가 추상적

"Plane A operational metrics baseline + Plane B quality KPI baseline을 동시에 잡는다"고 쓰였지만
**어떤 테이블에 기록하고 어떻게 비교하는지**는 없다.

→ 구체화는 Phase A 초입에서 해도 되지만, decision log에 "baseline 기록 location = X"는 고정해야 함.

### 2.3 V5 종합 판정

- **방향**: 완전히 맞음. V4 → V5는 진짜 advance.
- **구조**: 매우 좋음.
- **구현 해상도**: V4 대비 일부 후퇴. 다만 decision log로 보정 가능한 수준.
- **current 문서 자격**: 유지 권장. V6을 새로 쓸 필요는 크지 않음.

## 3. DOCUMENT_FLOW_ASSESSMENT 평가

### 3.1 강점

- **자기 성찰적**. 문서 시리즈가 제자리걸음인지를 독립적으로 검증했다.
- **§3 진단이 정확**: 핑퐁은 "철학 불일치"가 아니라 "측정 정의를 구현 가능한 형태로 내리는 과정"에서 발생.
- **§4의 구분** ("ignoring" vs "absorbing principle but not implementing completely")은
  이 시리즈의 행동 패턴을 정확히 포착한다.
- **§8 decision log 제안**이 이번 라운드에서 **가장 장기 가치 높은 기여**다.
  10+ 문서가 쌓인 지금, "합의된 결정은 더 이상 논의하지 말자"는 규율이 없으면 계속 반복될 것.

### 3.2 약점

#### 3.2.1 Decision log를 제안만 하고 쓰지 않았다

§8이 decision log의 존재 필요성을 주장하지만 **실제 decision log 자체는 첨부하지 않았다**.
이 공백은 이 문서의 가장 큰 실무적 빈칸.

→ 본 evaluation에 이어 `REVIEW_BOT_FUNDAMENTAL_REVIEW_DECISION_LOG.md`로 채움.

#### 3.2.2 V5 자체의 약점은 언급되지 않음

§6은 "현재 기준으로는 V5가 가장 적절한 통합 문서"라고 결론 내지만
V5 자체의 미정 사항(finding-outcomes 시점 의미, baseline 기록 위치, fallback PromQL 소실 등)은 다루지 않는다.
같은 턴에 쓰였으니 보기 어려웠던 점은 이해되지만,
"flow 수렴 평가"와 "V5 자체 평가"는 scope를 더 명확히 분리하는 편이 좋았다.

#### 3.2.3 "iterative uncovering of the same underlying confusion" 패턴을 명명하지 않음

이 시리즈에서 반복된 특정 실수는 이름 붙일 만하다:
*"existence-assumption drift"* — 아직 존재하지 않는 코드/metric/label을 이미 있는 것처럼 문서에 쓰고,
다음 라운드에서 그 함정이 발견되고, 더 정교하게 되돌아오지만 미묘한 형태로 재발한다.

V2→V3→V4→V5 모두 같은 부류 실수(존재하지 않는 label / 존재하지 않는 endpoint / 존재하지 않는 state)를 조금씩 더 미묘한 형태로 반복했다.
이 패턴을 이름 붙이면 decision log 체크리스트에 *"PromQL을 쓰기 전에 해당 label이 현재 코드에 실제로 있는지 확인했는가?"* 같은 항목으로 예방할 수 있다.

### 3.3 FLOW_ASSESSMENT 종합

- **전반 진단**: 정확.
- **실무적 기여**: decision log 제안이 이번 라운드의 best-takeaway.
- **실행**: 제안만 했고 작성은 하지 않음. 이 공백을 이번에 채운다.

## 4. "지금 버전 흐름에 대한 내 생각"

### 4.1 이 프로세스가 제자리걸음인가?

**아니다. 단, 비용이 점점 커지고 있다.**

FLOW_ASSESSMENT가 맞다 — 구조적으로는 수렴했다. 다만:

- 문서 수가 11개까지 늘었다.
- 각 라운드가 이전 라운드의 "놓친 디테일"을 복구하는 데 reader cost가 점점 커진다.
- V1→V5로 오면서 phase 번호 재할당, KPI 이름 변경, endpoint naming 변경이 누적돼
  새 독자가 진입하려면 이력을 순차로 다 읽어야 한다.

이 비용은 decision log 없이는 계속 커진다.

### 4.2 V6가 지금 필요한가?

**지금은 필요 없다고 본다.**

근거:

1. V5의 방향은 맞다 (Plane A/B).
2. V5가 잃은 디테일은 **V6로 새로 쓰기보다 decision log로 복원**하는 편이 누적 cost가 작다.
3. V6를 쓰면 또 V6_EVALUATION → V7이 이어질 가능성이 높다. "existence-assumption drift" 유형 실수가 더 미묘한 형태로 재발할 수 있다.
4. 현재 팀이 필요한 건 "더 좋은 문서"가 아니라 **"결정된 것을 더 이상 논의하지 않게 고정하는 장치"**.

### 4.3 대신 필요한 것

1. **`REVIEW_BOT_FUNDAMENTAL_REVIEW_DECISION_LOG.md`** — 단일 파일에 합의된 것만.
2. **V5에 small addendum** (§2.2에서 지적한 5–6개 구멍을 짧은 섹션으로 메우는 것).
   또는 그 내용을 decision log에 넣어도 된다 — 어차피 둘 다 "확정" 문서니까.
3. **다음 라운드 규칙**:
   - Open issue만 다룬다.
   - 이미 decision log에 박힌 것은 재논의하지 않는다.
   - 새 PromQL은 `grep`으로 현재 코드에 해당 label이 있음을 확인한 뒤 문서에 넣는다.

### 4.4 long-term: 이 문서 프로세스의 학습

이 11-문서 시리즈에서 얻을 수 있는 메타 학습은 아래다.

- **평가와 통합을 분리하면 반복이 쉽다. 다만 decision log 없이는 같은 결정을 계속 재확인한다.**
- **"존재하지 않는 것을 있는 것처럼 쓰는" 실수는 이 시리즈에서 최소 3회 발생했다** (V2 review_comments_* counter, V3 findings_resolved_total{resolution_reason}, V4 counter-based KPI). 매번 문법이 달랐지만 원인은 같았다: 설계자의 목표 상태와 코드의 현재 상태를 같은 문서 안에서 무구분 혼재.
- **LLM 기반 문서 병합은 "방향은 강하게, 디테일은 약하게" 수렴하는 편향이 있다.** V4→V5에서 Plane 분리는 강해졌지만 label value set 열거는 약해졌다.
- **Ping-pong은 나쁘지만 완전히 피할 수도 없다.** 다만 decision log로 "이미 끝난 주제"를 빼면 ping-pong의 표면적이 작아진다.

## 5. 산출물 구성 권장

| 문서 | 상태 | 역할 |
| --- | --- | --- |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW.md` | archival | 1차 방향성 메모 |
| `*_EVALUATION.md` | archival | Codex 1차 평가 |
| `*_ENHANCED.md` | archival | Codex 1차 보강본 |
| `*_META_EVALUATION.md` | archival | Claude 2차 메타 평가 |
| `*_V2.md` | archival | Claude 1차 통합본 |
| `*_V2_EVALUATION.md` | archival | Codex V2 평가 |
| `*_V3.md` | archival | Codex V2 보정본 |
| `*_V3_META_EVALUATION.md` | archival | Claude V3 메타 평가 |
| `*_V4.md` | archival | Claude V3 보정본 |
| `*_V4_EVALUATION.md` | archival | Codex V4 평가 |
| `*_V5.md` | **current (primary)** | Codex V5, Plane A/B 모델 확립 |
| `*_DOCUMENT_FLOW_ASSESSMENT.md` | archival | Codex 흐름 평가 |
| `*_V5_META_EVALUATION.md` | archival (본 문서) | Claude V5 평가 |
| `*_DECISION_LOG.md` | **current (companion)** | 결정 고정, 재논의 차단 |

즉 **V5를 current로 유지**하고 **decision log를 companion으로 추가**한다.
V6를 쓰지 않는다. 이것이 이번 라운드의 가장 실효성 있는 선택.

## 6. 결론

- V4_EVALUATION의 material critique는 코드로 전부 검증된다. V4의 KPI 데이터 소스 오류는 실제 설계 결함이었다.
- V5의 Plane A/B 분리는 그 오류에 대한 올바른 correction이며, 이후 버전의 기준으로 유지 가능하다.
- V5는 V4의 일부 디테일을 잃었지만, V6로 다시 쓰기보다 decision log로 복원하는 편이 누적 cost가 작다.
- DOCUMENT_FLOW_ASSESSMENT의 decision log 제안이 이번 라운드의 가장 장기 가치 높은 기여다. 이 제안을 실제 파일로 구현한다.
- 이 시리즈의 반복 비용은 더 좋은 통합 문서가 아니라 **결정 고정 장치**로 줄여야 한다.

따라서 본 평가와 짝을 이루는 산출물은 V6이 아니라
`REVIEW_BOT_FUNDAMENTAL_REVIEW_DECISION_LOG.md`다.
