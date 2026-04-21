# 리뷰 봇 근원 점검 상세 설계

- 문서 상태: Current — Implementation Design
- 작성일: 2026-04-21
- 작성 목적: `REVIEW_BOT_FUNDAMENTAL_REVIEW.md`의 최종 방향을 실제 구현 단계로 내린다.
- 함께 볼 문서:
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW.md`
  - `docs/REVIEW_BOT_FUNDAMENTAL_REVIEW_DECISION_LOG.md`

## 0. 설계 목표

이 설계의 1차 목표는 Phase A, 즉 **Trust Foundation**을 구현 가능한 단위로 구체화하는 것이다.

이번 설계가 해결해야 하는 문제는 아래 네 가지다.

1. verify phase 부재
2. `resolution_reason` 의미 부족
3. operational metrics와 quality KPI의 분리 부재
4. distinct fingerprint quality KPI를 계산하기 위한 immutable history 부재

## 1. 범위

### 1.1 이번 설계에 포함

- `resolution_reason` 확장
- verify phase v1
- 운영 계측용 metric 추가
- quality analytics용 immutable event 저장
- `/internal/analytics/finding-outcomes` endpoint
- baseline-v0 / baseline-v1 문서 운영 방식

### 1.2 이번 설계에서 제외

- `.review-bot.yaml` 구현 자체
- summarize / ask / walkthrough UI 설계
- apply/autofix
- multi-reviewer 병렬화
- cross-repo / multi-lang 대확장

## 2. 현재 코드 기준 touchpoint

이번 설계가 직접 영향을 주는 파일은 아래다.

- `review-bot/review_bot/db/models.py`
- `review-bot/review_bot/metrics.py`
- `review-bot/review_bot/bot/review_runner.py`
- `review-bot/review_bot/api/main.py`
- `review-bot/review_bot/config.py`
- `review-bot/review_bot/review_systems/base.py`
- `review-bot/review_bot/review_systems/gitlab.py`

현재 구조상 중요한 사실:

- review run 생성은 `api/main.py`의 internal API와 GitLab `Note Hook` mention 경로에 있다.
- detect/publish/sync의 실질 로직은 `review_runner.py`에 있다.
- `findings_*` counter는 event volume을 센다.
- `/internal/analytics/rule-effectiveness`는 distinct fingerprint 기반 latest meaningful state를 쓴다.
- `ThreadSyncState`는 최신 상태 snapshot이지 immutable history 저장소가 아니다.

## 3. 핵심 설계 원칙

### 3.1 운영 계측과 품질 KPI를 분리한다

- Prometheus는 운영 이벤트를 본다.
- quality KPI는 distinct fingerprint analytics로 계산한다.
- Prometheus counter 비율을 canonical quality KPI로 쓰지 않는다.

### 3.2 mutable snapshot과 immutable event를 분리한다

- `ThreadSyncState`는 최신 상태를 유지한다.
- quality analytics는 별도 immutable event를 기준으로 계산한다.

### 3.3 migration은 additive하게 간다

- 기존 `findings_*` metric 이름은 유지한다.
- 기존 모델을 wholesale replace하지 않는다.
- 새 요구는 sibling counter / 새 테이블 / 새 endpoint로 추가한다.

## 4. 데이터 모델 설계

### 4.1 `resolution_reason` 확장

`ThreadSyncState.resolution_reason`의 현재값은 유지하고 아래 두 값을 추가한다.

- `fixed_in_followup_commit`
- `remote_resolved_manual_only`

의미는 아래와 같이 고정한다.

- `fixed_in_followup_commit`
  - thread가 resolved되었고,
    마지막 관측 head 이후의 code change가 해당 finding anchor/file에 실제로 닿았다고 판단된 경우
- `remote_resolved_manual_only`
  - thread는 resolved되었지만,
    code change 근거를 확보하지 못한 경우

기존 값:

- `anchor_changed`
- `no_longer_eligible`
- `resolve_failed`
- `remote_resolved`
- `remote_reopened`

운영 정책:

- 기존 `remote_resolved`는 migration 이후 신규 기록에 직접 쓰지 않는다.
- migration 후 새 sync path는 `fixed_in_followup_commit` 또는 `remote_resolved_manual_only` 중 하나를 기록한다.
- 과거 row는 migration/backfill 전까지 기존 값을 유지한다.

### 4.2 새 immutable event 테이블

`ThreadSyncState`와 `FindingDecision`은 최신 상태만 남기므로
quality KPI를 안정적으로 계산하려면 immutable event가 필요하다.

새 테이블 이름:

- `finding_lifecycle_events`

권장 스키마:

```python
class FindingLifecycleEvent(Base):
    __tablename__ = "finding_lifecycle_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_request_pk: Mapped[str] = mapped_column(ForeignKey("review_requests.id"), index=True)
    review_system: Mapped[str] = mapped_column(String(32), index=True)
    project_ref: Mapped[str] = mapped_column(String(255), index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), index=True)
    finding_fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    finding_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("finding_decisions.id"), nullable=True, index=True
    )
    adapter_thread_ref: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    rule_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rule_family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    event_reason: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    observed_head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compared_from_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
```

초기 `event_type` 집합:

- `resolved`
- `reopened`

향후 확장 가능:

- `published`
- `suppressed`
- `verify_dropped`

초기에는 **resolution lifecycle 보존**이 가장 중요하므로
`resolved` / `reopened`만 저장해도 충분하다.
publish 시점은 기존 `PublicationState.published_at`,
feedback command는 기존 `FeedbackEvent`를 사용한다.

### 4.3 왜 `finding_lifecycle_events`가 필요한가

현재 구조만으로는 아래를 안정적으로 복원하기 어렵다.

- `first_fixed_at`
- reopen 이후 재해결 history
- `latest_resolution_reason`의 과거 이력

특히 `_mark_fingerprint_reopened()`는 이전 resolved row의 state를 다시 `published`로 되돌릴 수 있어
최초 resolve/fix 시점이 mutable state 안에서 사라진다.

따라서 quality KPI는 다음 조합으로 계산한다.

- surfaced 시점: `PublicationState`
- resolution / reopen 시점: `FindingLifecycleEvent`
- feedback command: `FeedbackEvent`
- latest surfaced state: 기존 `latest_rule_effectiveness_states()`

## 5. Metric 설계

### 5.1 유지하는 기존 metric

- `findings_published_total{severity, rule_family}`
- `findings_suppressed_total{reason}`
- `findings_resolved_total{rule_no}`

이 metric은 계속 **event volume**용으로만 본다.

### 5.2 새 operational metric

```python
feedback_commands_total = Counter(
    "feedback_commands_total",
    "Total feedback commands by command type",
    ["command"],
)

verify_attempts_total = Counter(
    "verify_attempts_total",
    "Total verify attempts by mode",
    ["mode"],
)

verify_dropped_total = Counter(
    "verify_dropped_total",
    "Total findings dropped by verify",
    ["mode", "reason"],
)

finding_resolution_events_total = Counter(
    "finding_resolution_events_total",
    "Total resolution events by rule family and reason",
    ["rule_family", "resolution_reason"],
)
```

고정 label value set:

- `feedback_commands_total{command}`
  - `ignore`
  - `false-positive`
  - `later`
  - `allow`
- `verify_attempts_total{mode}`
  - `llm_self_check`
  - `pattern_execution`
- `verify_dropped_total{reason}`
  - `not_a_real_bug`
  - `low_confidence`
  - `pattern_mismatch`
  - `execution_error`

### 5.3 왜 sibling counter를 쓰는가

`findings_resolved_total`의 label set을 직접 바꾸지 않고
`finding_resolution_events_total`을 추가하는 이유는 아래와 같다.

- 기존 metric 의미를 깨지 않는다.
- 기존 대시보드나 운영 습관과 충돌이 작다.
- 새 counter는 `rule_family` 수준으로 cardinality를 낮출 수 있다.

## 6. Verify Phase v1 설계

### 6.1 삽입 위치

verify phase는 `review_runner.py`의 `_build_decision()` 안에서
최종 `FindingDecision`을 반환하기 직전에 들어간다.

현재 `_build_decision()`은 아래를 수행한다.

- fingerprint 계산
- feedback signal 반영
- score 계산
- suppression reason 계산
- `FindingDecision` 생성

verify는 이 흐름 사이에서 아래 위치가 적절하다.

1. score / policy / feedback 기반 1차 판단 계산
2. verify 필요 여부 판정
3. verify 실행
4. verify 결과를 반영해 state / suppression_reason / confidence 조정
5. `FindingDecision` 반환

### 6.2 verify 대상

초기에는 아래 조건일 때만 verify를 건다.

- `reviewability == "auto_review"`
- 아직 policy / feedback / weak_anchor 등으로 suppress되지 않음
- `final_score`가 publish threshold 근처
- 또는 confidence가 낮음

권장 초기 기준:

- `minimum_publish_score <= final_score < minimum_publish_score + 0.1`
- 또는 `confidence < 0.85`

### 6.3 verify 방식

초기 구현은 `llm_self_check` 하나만 실제로 활성화한다.

흐름:

1. candidate finding의 evidence / change_snippet / title / summary / rule_no를 묶는다.
2. provider에 "이 finding이 false positive일 가능성"을 재질문한다.
3. 응답을 아래로 정규화한다.

```json
{
  "is_real_bug": true,
  "confidence": 0.72,
  "reason": "low_confidence"
}
```

4. 결과에 따라:
   - `is_real_bug == false` → suppress, `verify_dropped_total{mode="llm_self_check", reason="not_a_real_bug"}`
   - `confidence < threshold` → suppress, `reason="low_confidence"`
   - 호출/파싱 실패 → publish 판단은 유지하되 `reason="execution_error"`만 운영 로그에 남김

### 6.4 verify 적용 범위

초기 verify는 **inline comment publish 후보**에만 적용한다.

적용하지 않는 것:

- walkthrough
- summarize
- ask

## 7. Sync / Resolution Classification 설계

### 7.1 목표

remote thread가 resolved될 때,
그 이유를 아래 둘 중 하나로 분류한다.

- `fixed_in_followup_commit`
- `remote_resolved_manual_only`

### 7.2 분류 위치

분류는 `_reconcile_thread_snapshots()` 안에서
`snapshot.resolved`가 true가 되고 `thread_state.sync_status != "resolved"`일 때 수행한다.

현재는 이 지점에서 단순히 `remote_resolved`를 기록한다.
새 설계에서는 아래 helper를 도입한다.

- `_classify_resolution_reason(...)`

### 7.3 분류 알고리즘

입력:

- `thread_state`
- `review_request`
- 현재 `head_sha`
- 해당 fingerprint의 최신 decision / anchor payload
- adapter

판정 순서:

1. `head_sha`가 없거나 `thread_state.last_seen_head_sha`가 없으면
   `remote_resolved_manual_only`
2. `head_sha == thread_state.last_seen_head_sha`면
   코드 변화 없이 resolve된 것으로 간주하고 `remote_resolved_manual_only`
3. 아니면 `adapter.fetch_diff(key, mode="incremental", base_sha=thread_state.last_seen_head_sha)` 호출
4. diff에서 해당 finding의 `file_path`를 찾는다.
5. 아래 중 하나라도 만족하면 `fixed_in_followup_commit`
   - anchor line 인근이 실제로 수정됨
   - `candidate_line_nos` 중 하나가 수정됨
   - changed line digest / hunk header가 유사한 위치에서 다시 나타남
6. 근거가 없으면 `remote_resolved_manual_only`

### 7.4 기록 방식

resolved 전환 시 아래를 함께 수행한다.

1. `ThreadSyncState.sync_status = "resolved"`
2. `ThreadSyncState.resolution_reason = <classified_reason>`
3. `_mark_fingerprint_resolved(...)`
4. `finding_resolution_events_total{rule_family, resolution_reason}.inc()`
5. `FindingLifecycleEvent(event_type="resolved", event_reason=<classified_reason>, ...)` insert

reopen 전환 시:

1. `ThreadSyncState.sync_status = "open"`
2. `ThreadSyncState.resolution_reason = "remote_reopened"`
3. `_mark_fingerprint_reopened(...)`
4. `FindingLifecycleEvent(event_type="reopened", event_reason="remote_reopened", ...)` insert

## 8. Feedback Command 계측 설계

### 8.1 metric emission 위치

`_ingest_feedback()`에서 새 `FeedbackEvent`를 저장할 때 같이 처리한다.

처리 규칙:

- `event_type == "reply"`
- `actor_type == "human"`
- body 안에 최신 feedback command가 있으면
  `feedback_commands_total{command=<parsed_command>}.inc()`

중요:

- `FeedbackEvent.event_key`가 dedupe key이므로
  같은 이벤트를 다시 ingest해도 metric 중복 증가를 피할 수 있다.

### 8.2 analytics에서의 사용

quality KPI는 counter 합계가 아니라
`FeedbackEvent`에서 fingerprint별 latest command를 따로 계산한다.

`feedback_commands_total`은 Plane A 운영 지표 전용이다.

## 9. `finding-outcomes` Endpoint 설계

### 9.1 endpoint

- 경로: `GET /internal/analytics/finding-outcomes`

초기 query parameter:

- `project_ref` optional
- `window` optional, 기본 `28d`
- `source_family` optional

### 9.2 내부 집계 의미

집계 단위는 **distinct fingerprint**다.

필요한 파생값:

- `first_surfaced_at`
  - `min(PublicationState.published_at)` for successful publish
- `latest_meaningful_state`
  - 기존 `latest_rule_effectiveness_states()`
- `first_fixed_at`
  - earliest `FindingLifecycleEvent(event_type="resolved", event_reason="fixed_in_followup_commit")`
- `latest_resolution_reason`
  - latest lifecycle event 기준
- `latest_feedback_command`
  - `FeedbackEvent`의 최신 human command 기준

### 9.3 응답 예시

```json
{
  "window": "28d",
  "project_ref": "group/repo",
  "surfaced_distinct": 120,
  "resolved_distinct": 70,
  "fixed_distinct": 48,
  "manual_resolved_distinct": 22,
  "ignored_distinct": 15,
  "false_positive_distinct": 9,
  "reopened_distinct": 6
}
```

### 9.4 canonical KPI 계산

```text
fix_confirmation_rate_14d =
  fixed_distinct_14d / resolved_distinct_14d
```

```text
fix_conversion_rate_28d =
  converted_cohort_28d / surfaced_cohort_28d
```

```text
false_positive_feedback_rate_14d =
  false_positive_distinct_14d / surfaced_distinct_14d
```

## 10. Baseline 운영 방식

### 10.1 baseline-v0

Instrumentation 이전에는 아래만 snapshot으로 남긴다.

- publish / suppress / resolve event volume
- rule-effectiveness top rules
- feedback command volume

기록 위치:

- `docs/baselines/review_bot/`

권장 파일명:

- `baseline_v0_YYYY-MM-DD.md`

### 10.2 baseline-v1

Phase A 완료 후 아래를 같은 위치에 snapshot으로 남긴다.

- operational metrics baseline
- quality KPI baseline
- query / endpoint output
- 측정 시점의 build / branch / deploy context

권장 파일명:

- `baseline_v1_YYYY-MM-DD.md`

## 11. 구현 순서

### Step 1. Schema + metric 준비

- `FindingLifecycleEvent` 모델 추가
- migration 작성
- `metrics.py`에 새 counter 추가

### Step 2. feedback / sync instrumentation

- `_ingest_feedback()`에 `feedback_commands_total`
- `_reconcile_thread_snapshots()`에 resolution classifier / lifecycle event / sibling counter

### Step 3. verify phase v1

- `_build_decision()`에 verify hook 추가
- provider contract에 self-check 호출 경로 추가

### Step 4. analytics endpoint

- `api/main.py`에 `/internal/analytics/finding-outcomes`
- distinct fingerprint 집계 구현

### Step 5. baseline 문서화

- `docs/baselines/review_bot/` 생성
- baseline-v0 기록
- instrumentation 배포
- baseline-v1 기록

## 12. 테스트 전략

### 12.1 unit / integration

- feedback command ingest dedupe
- resolved → fixed/manual classification
- reopen 이후 lifecycle event 기록
- verify drop metric emission
- endpoint cohort aggregation

### 12.2 회귀 방지

반드시 커버할 시나리오:

1. 같은 fingerprint가 여러 run에 걸쳐 repeated publish된 경우
2. resolved 후 reopened, 다시 resolved되는 경우
3. code change 없이 human이 resolve한 경우
4. `bot:false-positive` 후 rerun되는 경우
5. `baseline-v0` proxy와 `baseline-v1` canonical KPI를 혼동하지 않는지

## 13. 잔여 리스크

### 13.1 resolution 분류의 heuristic 한계

`fixed_in_followup_commit` 판정은 완전한 semantic proof가 아니라
incremental diff 기반 heuristic이다.
초기엔 precision을 우선하고, 애매하면 `remote_resolved_manual_only`로 둔다.

### 13.2 analytics query 비용

초기 endpoint는 live query로 시작한다.
프로젝트 규모가 커지면 rollup/materialized aggregation으로 승격한다.

### 13.3 migration 중 혼합 데이터

과거 `remote_resolved` row와 새 `fixed_in_followup_commit` / `remote_resolved_manual_only` row가 한동안 공존한다.
대시보드와 baseline 문서에 migration cut line을 명시해야 한다.

## 14. 최종 구현 판단

이 설계의 핵심은 두 가지다.

1. verify phase를 detect/publish 사이에 삽입해 trust를 높인다.
2. mutable snapshot만으로는 품질 KPI를 계산할 수 없으므로
   immutable lifecycle history + distinct fingerprint analytics를 도입한다.

이 두 가지가 구현되면,
이후 context / learning / UX 투자는 더 단단한 measurement 위에서 진행할 수 있다.
