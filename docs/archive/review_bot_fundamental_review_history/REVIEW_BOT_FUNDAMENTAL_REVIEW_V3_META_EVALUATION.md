# Review Bot Fundamental Review — V3 Meta Evaluation

- 문서 상태: Assessment
- 작성일: 2026-04-21
- 작성자: Claude (본 문서의 1인칭은 평가자 Claude를 가리킨다)
- 대상 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2_EVALUATION.md` (Codex의 V2 평가)
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V3.md` (Codex의 V2 보정본)
- 관련 이력:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md`

## 0. 이 문서를 왜 만드는가

V2에 대해 Codex가 다시 두 문서로 응답했다.

- `V2_EVALUATION`은 V2의 KPI/metric 정의 문제를 5개로 정리했다.
- `V3`는 그 지적을 반영해 baseline-v0 / instrumentation / baseline-v1 3단 구조와
  `fix_confirmation_rate` / `fix_conversion_rate` 분리를 도입했다.

이번 평가의 목적은 두 가지다.

1. V2_EVALUATION의 5개 critique가 **코드로 검증되는가** 확인한다.
2. V3가 그 지적을 **완전히** 해소했는지, 새로운 함정을 만들지 않았는지 확인한다.

결론부터 쓰면:
V2_EVALUATION의 5개 critique는 **모두 코드 또는 출처 분석으로 검증된다**.
V3는 구조적으로 V2보다 확실히 나아졌지만,
**V2가 빠졌던 "존재하지 않는 metric을 PromQL에 쓰는" 함정에 더 미묘한 형태로 다시 빠졌다**.
이 추가 gap을 정리한 V4가 필요하다.

## 1. V2_EVALUATION의 5개 Critique 검증

### 1.1 baseline과 instrumentation 순서 충돌 — **✅ 코드로 검증됨**

V2가 baseline-first를 선언하면서 동시에 `fixed_in_followup_commit` 같은
**아직 존재하지 않는 `resolution_reason` 값**을 KPI 정의의 분자로 사용했다.

현재 코드(`review_bot/bot/review_runner.py`)의 `resolution_reason` 대입값은 아래 5개뿐이다.

- line 608: `anchor_changed`
- line 851: `no_longer_eligible`
- line 858: `resolve_failed`
- line 1565: `remote_resolved`
- line 1574: `remote_reopened`

`fixed_in_followup_commit`는 없다. V2가 이 값을 전제로 baseline을 측정하겠다고 한 것은
스스로의 baseline-first 원칙과 모순이다. Codex 지적은 **유효**.

### 1.2 `acceptance_rate` 정의 불일치 — **✅ V2 본문 대조로 검증됨**

V2 §8.2 KPI 표: `review_comments_resolved_total` / … (분모 = resolved만)
V2 §11.2 본문: `fixed_in_followup_commit / (published + resolved)` (분모 = published + resolved)

같은 이름에 다른 식이 공존한다. Codex의 `fix_confirmation_rate` /
`fix_conversion_rate` 분해 제안은 **유효**.

### 1.3 metric 계열과 PromQL 예시 부정확 — **✅ 코드로 검증됨**

`review_bot/metrics.py`에서 현재 정의된 counter:

- `findings_published_total{severity, rule_family}`
- `findings_suppressed_total{reason}`
- `findings_resolved_total{rule_no}`

V2가 PromQL에서 사용한 `review_comments_*` 계열은 **코드에 존재하지 않는다**.
또 rename/병행 추가 여부에 대한 migration 지침도 없다. Codex 지적 **유효**.

PromQL 예시의 `severity="warning|critical"` 표기가 regex matcher(`=~`) 대신
equality에 or로 쓰인 점도 실제 쿼리로는 잘못된 문법이다. **유효**.

### 1.4 META_EVALUATION의 "코드 검증" 표현 과함 — **⚠️ 부분 유효**

내 META_EVALUATION은 "5개 critique가 코드로 모두 검증된다"고 썼는데,
다섯 번째 항목(벤더 수치가 self-report인가)은 엄밀히는 **출처 성격 분석**이다.
다만 이는 표현의 문제이지 판단의 오류는 아니다.

Codex의 tone-down 권고(`"코드 또는 문서 출처 성격으로 검증된다"`)는 **수용 가능**.

### 1.5 `resolution_reason` 현재값 설명 불완전 — **✅ 코드로 검증됨**

V2 §3.2 파이프라인 그림에서 언급한 `resolution_reason` 값:

- `remote_resolved`
- `no_longer_eligible`
- `anchor_changed`

코드에 실제 존재하지만 V2가 누락한 값:

- `resolve_failed` (line 858)
- `remote_reopened` (line 1574)

상태 머신 문서로서 5개 중 2개를 빠뜨린 것은 후속 migration에서 버그를 만든다.
Codex 지적 **유효**.

### 1.6 종합

V2_EVALUATION의 5개 critique는 **모두 실질적이며 코드 / 문서로 검증된다**.
표현 강도 차이만 있을 뿐 판단의 정확도는 매우 높다.

## 2. V2_EVALUATION 자체 평가

### 2.1 강점

- 5개 critique 모두 material (문장 다듬기 수준이 아니라 실행 시 버그를 만드는 급).
- `fix_confirmation_rate` / `fix_conversion_rate` 분해 제안은 단순 지적이 아니라
  **설계 언어의 개선 제안**이며 V3/V4에서 채택할 가치가 있다.
- V2의 실무 결함(metric naming, label 누락, 정의 충돌)을 구현자 관점에서 짚었다.
- 권장 산출물 구성표가 명시적이어서 버전 관리 혼선이 적다.

### 2.2 약점

- **자기 주장의 근거 인용이 약하다.** "현재 코드의 counter는 `findings_*` 계열이다"라고만 쓰고
  파일 경로/라인 인용이 없다. 본인 제시한 evidence tier 원칙을 본인이 덜 따른다.
- **누락된 V2 이슈 지적 없음.** 예:
  - `.review-bot.yaml` 우선순위 규칙(`policy.json`과의 충돌 해결)이 V2에서 비어 있음.
  - V2의 "Ellipsis 병렬 reviewer 조건부 defer" 해석이 D3 한 줄로 축소됨.
  - V2의 `verify_phase_drop_total{reason}` label value 목록이 열거되지 않음.
- **V2의 핵심 우선순위(verify > context > UX)는 언급하지 않음.** 수용하는 것으로 보이지만
  명시적 endorsement가 없으면 V3 저자에게 방향성 유지 책임을 넘기게 된다.
  다행히 V3가 그 방향을 유지해서 문제가 되지 않았다.

## 3. V3 자체 평가

### 3.1 강점

- **baseline-v0 / instrumentation / baseline-v1 3단 분리** (§7)는 V2의 충돌을 깔끔하게 해소.
  새 metric이 도입되기 전에는 기존 `findings_*` + `/internal/analytics/rule-effectiveness` 기반으로
  먼저 baseline-v0를 잡도록 명시.
- **`fix_confirmation_rate` / `fix_conversion_rate` 분리 수용** (§6.3, §8.2).
  두 개념의 분모가 다름을 명확히 함.
- **`findings_*` 계열 유지 정책** (§8.1): "기존 counter rename은 피한다, label 확장 또는 sibling 추가만".
  wholesale rename을 명시적으로 금지한 것이 실무적으로 큰 도움.
- **`rule_no` 대신 `rule_family`를 Prometheus label 기본으로** (§8.3):
  cardinality 폭발 방지의 현실적 판단. `rule_no` 단위 drill-down은 warehouse로 분리.
- **PromQL regex matcher(`=~`) 사용** (§8.2):
  V2의 문법 오류 수정.
- **`resolution_reason` 현재값 5개 전부 나열** (§2.5):
  누락 이슈 해소.
- **절대 목표치 포기, 개선폭 관리**(§8.5): baseline 없는 절대 수치 금지 원칙 정착.

### 3.2 약점 — V3_EVALUATION이 놓친 것들

V3는 V2 평가 지적을 잘 반영했지만 **새로운 미묘한 gap을 가지고 있다**.

#### 3.2.1 PromQL이 "아직 없는 label"을 사용한다 — **V2 함정의 재발, 더 미묘한 형태**

V3 §8.2 KPI 표:

```
fix_confirmation_rate =
  sum(findings_resolved_total{resolution_reason="fixed_in_followup_commit"})
  / sum(findings_resolved_total)
```

그러나 현재 `findings_resolved_total`의 label은 `rule_no` 하나뿐이다
(`review_bot/metrics.py:23-27` 확인).

V3 §8.3은 "기존 계열 확장 기준"으로 `findings_resolved_total{rule_family, resolution_reason}`를
**"권장"**하지만, §8.2 PromQL은 이미 그 확장이 끝난 것처럼 쿼리를 쓴다.

이는 **V2가 빠졌던 함정과 같은 문제 유형**이다.
다만 (a) migration이 원위치 rename이 아니라 label 확장이고,
(b) 바로 구현 가능한 작업이라 V2만큼 심각하지는 않다.

해결: V3가 V4로 넘어갈 때 Phase A1에
"`findings_resolved_total`에 `resolution_reason` label 추가"를
**PromQL 유효성의 선행 의존**으로 박아야 한다.

#### 3.2.2 `signal_ratio` PromQL이 새 severity taxonomy를 전제한다

V3 §8.2:

```
signal_ratio =
  sum(findings_published_total{severity=~"warning|critical"})
  / sum(findings_published_total)
```

그러나 현재 `findings_published_total`의 `severity` label value는
`low / medium / high` (코드상 `_severity_from_score`).

V3 Phase A2에서 severity를 `warning / critical / suggestion / nitpick`으로 migration한다고 적지만,
그 migration이 끝나기 전에는 위 PromQL이 **아무것도 매치하지 않는다**.

해결: V4에서 이 PromQL에 "Phase A2 완료 후 유효" 주석 명시,
또는 기존 taxonomy 기준 PromQL을 먼저 제시하고 새 taxonomy용 PromQL을 단계적으로 추가.

#### 3.2.3 `.review-bot.yaml` vs `policy.json` 충돌 해결 규칙 누락

V3 §10.3에서 우선순위를 "`.review-bot.yaml` > `policy.json` > env"로 적었지만,
**값 단위 충돌 해결 규칙이 없다**.

예: `.review-bot.yaml`의 `suppressed_rules: [X]`와
`policy.json`의 `allowed_rules: [X]`가 동시에 존재할 때
X는 suppress되는가, allow되는가?

V4에서는 아래 중 하나를 명시해야 한다.

- strict override: 상위 파일의 명시값이 항상 이김.
- merge with precedence: allowed 우선 vs suppressed 우선 중 정책 고정.
- conflict → bot error: 정의 자체를 금지.

#### 3.2.4 `verify_dropped_total{mode}` 의미 미정의

V3 §8.3은 `verify_dropped_total{mode, reason}`을 신설 counter로 열거하지만,
`mode`가 무엇을 가리키는지 §10.1 verify flow와 연결 짓지 않는다.

의도를 추론하면 `mode = llm_self_check | pattern_execution | ...`일 것이나,
설계 문서에는 명시해야 한다.

#### 3.2.5 Ellipsis 병렬 reviewer 맥락이 축소됨

V2 §5.7에서 "단순 과투자 치부가 아니라 verify phase의 확장 경로로서 조건부 defer"라는
재해석을 담았는데, V3 §9 Phase D의 한 줄("조건부 multi-reviewer 병렬화")로 줄어들었다.

defer 자체는 맞지만 **defer의 조건**을 잃으면 미래 재평가 기준이 사라진다.
V4에서는 재평가 조건(acceptance plateau + verify phase 한계 실측)을 복원해야 한다.

#### 3.2.6 `feedback_commands_total{command}` label value 목록 미열거

V3 §8.3에서 이 counter를 새로 만든다고 적지만 `command` label의 value set을 안 적는다.
현재 `_latest_feedback_command` 정규식이 `ignore | false-positive | later | allow` 4개를 잡으므로
label 값은 이 4개로 한정해야 cardinality 안전.

#### 3.2.7 Phase A1 이름이 이전과 달라짐

- V2: A1 = "Acceptance tracking 추가"
- V3: A1 = "resolution_reason 확장"

내용은 같지만 naming이 바뀌었다. 산출물 이력 추적 시 혼선 가능성.
V4에서 alias 주석이나 comment로 연결 관계를 남겨 두는 편이 좋다.

### 3.3 종합

V3는 V2_EVALUATION의 5개 critique에 대해 구조적으로 올바른 해법을 제시했다.
다만 위 7가지 잔존 gap이 있다. 이 중 3.2.1 / 3.2.2가 material이고 나머지는 보완 수준이다.

## 4. V4에서 반드시 반영할 사항

1. **PromQL label 의존성 명시**
   - `findings_resolved_total`에 `resolution_reason` label 추가를 Phase A1의 **선행 작업**으로.
   - 모든 새 label 기반 PromQL에는 "label 확장 후 유효" 주석.
2. **severity taxonomy migration의 영향 범위 기록**
   - 새 taxonomy 기준 PromQL은 Phase A2 완료 후 유효임을 본문 각주에.
   - 전환 기간 동안 기존 label value 기반 fallback PromQL 제공.
3. **`.review-bot.yaml` 충돌 해결 규칙**
   - strict override 원칙 권장.
   - 같은 key에서 상충하면 상위 파일이 이김.
4. **`verify_dropped_total{mode}` 정의**
   - `mode ∈ {llm_self_check, pattern_execution}`로 값 집합 고정.
5. **Ellipsis 병렬 reviewer 재평가 조건 복원**
   - Phase D3에 "acceptance plateau + verify phase 한계 실측 이후"를 defer 해제 조건으로 명시.
6. **`feedback_commands_total{command}` label value 열거**
   - `ignore | false-positive | later | allow` 4개만.
7. **Phase 이름 alias / 이력 주석**
   - V2 ↔ V3 Phase A1 naming 변화를 문서 안에 각주.
8. **META_EVALUATION 방법론 계승**
   - `[code-verified]` / `[design-inference]` / `[market-informed]` 태그는 V3가 이미 채택.
   - V4도 이어간다.

## 5. 문서 수준 최종 판정

### 5.1 V2_EVALUATION

- 방향성: 정확
- 사실 근거: 강 (5/5 검증됨)
- 표현 보수성: 일부 개선 여지 있음
- 산출물: current가 아니라 **ARCHIVAL** — V3 판단 근거로서 이력 가치

### 5.2 V3

- 방향성: 매우 좋음
- 구조: 매우 좋음 (baseline 3단, KPI 2분화, findings_* 유지)
- 구현 가능성: **"label migration 선행 의존"만 명시하면 바로 실행 가능 수준**
- 계측 정의 완성도: V2 대비 큰 향상, 단 일부 의존관계 미명시

### 5.3 결론

- V2_EVALUATION은 archival로 유지.
- V3는 current에서 **superseded** 처리하고 V4를 current로 승격.
- V4는 방향을 뒤집지 않고 **V3의 label migration / taxonomy migration / 충돌 규칙 / 조건 defer 근거**를 채우는 보정본.

## 6. 산출물 구성

| 문서 | 상태 | 역할 |
| --- | --- | --- |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW.md` | archival | 1차 방향성 메모 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_EVALUATION.md` | archival | 1차 평가 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_ENHANCED.md` | archival | 1차 보강본 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_META_EVALUATION.md` | archival | 2차 메타 평가 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_V2.md` | archival | 1차 통합본 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_V2_EVALUATION.md` | archival | V2 평가 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_V3.md` | **superseded** | V2 + KPI 정리 통합본 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_V3_META_EVALUATION.md` | archival (본 문서) | V3 독립 판정 |
| `REVIEW_BOT_FUNDAMENTAL_REVIEW_V4.md` | **current** | V3 + label migration 선행 의존 반영본 |

이후 변경은 V4에서 이어간다. 이전 문서들은 변경하지 않는다.
