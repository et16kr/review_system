# Review Bot Repeat / Feedback Policy Design

- 문서 상태: Implemented Reference
- 작성일: 2026-04-21
- 최종 갱신일: 2026-04-21
- 대상 독자: AI agent, 구현 담당자
- 관련 문서:
  - `docs/REVIEW_BOT_ADDITIONAL_IDEAS.md`
  - `docs/REVIEW_BOT_REDESIGN_DESIGN.md`
  - `docs/API_CONTRACTS.md`

## 0. 현재 반영 상태

이 문서는 반복 지적 / feedback 정책의 상세 설계 기준으로 작성되었고,
현재 트리에는 핵심 정책이 이미 반영되어 있다.

- unchanged open thread reminder reply는 기본값으로 꺼져 있다.
- `bot:ignore`, `bot:false-positive`, `bot:later`, `bot:allow`가 모두 지원된다.
- `later`와 `resolved + unchanged`는 inline 재게시보다 backlog 쪽으로 표현된다.
- summary는 실제 게시 수와 backlog / feedback suppress 상태를 구분해 보여 준다.
- full-report / backlog 노출 정책은 `docs/REVIEW_BOT_BACKLOG_ANALYTICS_AND_COMMAND_UX_DESIGN.md`와 `docs/API_CONTRACTS.md`에 현재 기준이 정리되어 있다.

즉 이 문서는 구현 전 할 일 목록이라기보다,
현재 정책이 왜 그렇게 되어 있는지 설명하는 reference 문서로 읽는 편이 맞다.

## 1. 목적

이 문서는 `review-bot`의 반복 지적, thread 재노출, human feedback 해석 정책을
AI agent가 바로 구현 작업으로 옮길 수 있도록 상세화한다.

핵심 목표는 아래 3가지다.

- 반복 검출은 허용하되 반복 게시를 줄인다.
- 기존 open thread를 canonical review state로 유지한다.
- `ignore`/`false-positive`/`later` 같은 human intent를 기계적으로 해석할 수 있게 한다.

이 문서는 제품 아이디어 문서가 아니라, 실제 코드 변경 작업을 위한 실행 설계다.

## 2. 현재 상태 요약

현재 구현의 중요한 동작은 아래와 같다.

### 2.1 이미 잘 되어 있는 부분

- 같은 finding fingerprint에 대해 existing thread를 찾고 재사용하려는 흐름이 있다.
  - 파일: `review-bot/review_bot/bot/review_runner.py`
  - 주요 지점: `_find_existing_thread()`, `_prepare_publication_candidates()`
- incremental run에서는 unchanged open thread를 별도 reminder로 다시 끌어올리지 않는다.
- human reply 안의 `bot:ignore`, `bot:allow`는 이미 파싱된다.
- `ignore_requested`가 켜지면 candidate는 `suppressed` 처리된다.

### 2.2 현재 UX가 거친 부분

- 기본 설정에서는 full/manual rerun에서도 unchanged open thread에 reminder reply를 추가로 달지 않는다.
  - `_should_resurface_open_thread()`는 feature flag 기반 opt-in 동작이다.
- 일반 `resolve`는 suppress가 아니라 score penalty에 가깝다.
  - `_was_previously_resolved()`
  - `_score_candidate()`
- summary는 현재 "실제 게시된 항목"과
  "이미 열린 backlog / later / feedback suppress" 상태를 구분해 설명한다.

### 2.3 현재 상태의 의미

즉, 현재 정책은 다음에 가깝다.

- "문제가 남아 있으면 다시 잡아낸다"는 점은 맞다.
- 다만 `resolve`/`later`/`ignore`의 의미를 사용자가 얼마나 직관적으로 느끼는지는
  앞으로도 계속 다듬을 여지가 있다.

## 3. 목표 정책

이번 설계의 기본 원칙은 한 줄로 요약된다.

**반복 검출은 허용, 반복 게시는 제한**

### 3.1 목표 동작

1. open thread가 그대로 남아 있으면 기본값으로는 새 reminder reply를 달지 않는다.
2. existing open thread는 canonical state로 유지한다.
3. full/manual rerun에서도 unchanged open thread는 inline 재게시 대신 backlog 취급한다.
4. resolved thread는 코드/anchor/body가 의미 있게 바뀌었을 때만 inline 재등장시킨다.
5. human feedback는 최소 아래 의미를 구분한다.
   - `ignore`: 더 이상 보고 싶지 않음
   - `false-positive`: 이 finding은 오탐임
   - `later`: 지금 inline으로 다시 올리지 말고 backlog로 미뤄도 됨
   - `allow`: suppression보다 게시를 우선해도 됨

### 3.2 이번 설계의 구현 범위

이 문서는 원래 아래 2단계 구현을 전제로 썼고,
현재는 대부분 완료된 상태다.

#### Phase 1

- 완료: full/manual rerun의 open-thread reminder reply 기본값 비활성화
- 완료: `bot:false-positive`, `bot:later` feedback command 파싱 추가
- 완료: summary에 "재게시하지 않고 backlog로 유지한 기존 이슈 수"를 노출할 수 있는 집계 기반 추가

#### Phase 2

- 완료: `@review-bot full-report` / `@review-bot backlog` view 추가
- 완료: `later` 항목을 backlog 전용 출력으로 노출
- 부분 반영: richer feedback UX의 command/note 경로 확장

현재는 **Phase 1 + 주요 Phase 2**가 반영된 상태다.

## 4. 비범위

아래는 이번 작업에 포함하지 않는다.

- GitLab UI에 전용 버튼 추가
- DB 스키마 대규모 개편
- Gerrit/GitHub adapter 구현
- reviewer/team profile 기능

## 5. 현재 코드 기준 변경 포인트

### 5.1 `review-bot/review_bot/bot/review_runner.py`

가장 큰 변경이 들어갈 파일이다.

#### 현재 관련 책임

- `FeedbackSignal` 정의
- feedback command 해석
- repeat reminder candidate 판정
- publication candidate 우선순위 결정
- summary 게시

#### 변경해야 할 항목

1. `FeedbackSignal` 확장
   - `false_positive_requested: bool = False`
   - `later_requested: bool = False`

2. feedback command 파서 확장
   - `bot:false-positive`
   - `bot:later`
   - 기존 `bot:ignore`, `bot:allow` 유지

3. suppression / demotion 정책 추가
   - `false_positive_requested`면 현재 run candidate를 suppress
   - suppression_reason은 `feedback:false_positive`
   - `later_requested`면 inline publish 후보에서는 제외하되 backlog 카운트 대상으로 유지

4. open-thread reminder 기본값 제거
   - `_should_resurface_open_thread()`의 기본 반환 정책을 변경
   - 기본 모드에서는 `False`
   - 추후 opt-in 모드 추가를 고려해 feature flag를 남긴다

5. publication candidate 분류 확장
   - 현재 `priority_group`만으로는 "backlog-only"를 드러내기 어렵다
   - 최소한 summary 집계를 위해 아래 정보가 필요하다.
     - `backlog_reason: str | None`
     - 예: `existing_open_thread`, `feedback:later`, `resolved_unchanged`

6. summary 집계 확장
   - 실제 `created/updated` 성공 건수는 그대로 유지
   - 추가로 아래 카운트를 보여 줄 수 있어야 한다.
     - `backlog_existing_open`
     - `backlog_feedback_later`
     - `suppressed_feedback_ignore`
     - `suppressed_feedback_false_positive`

### 5.2 `review-bot/review_bot/config.py`

기본 정책을 코드 상수로 박지 말고 설정으로 노출한다.

추가 제안 필드:

- `repeat_open_thread_reminder_enabled: bool`
  - env: `BOT_REPEAT_OPEN_THREAD_REMINDER_ENABLED`
  - default: `false`

- `resolved_unchanged_resurface_enabled: bool`
  - env: `BOT_RESOLVED_UNCHANGED_RESURFACE_ENABLED`
  - default: `false`

이 두 값은 초기에는 모두 `false`로 둔다.

### 5.3 `review-bot/tests/test_review_runner.py`

핵심 regression test 파일이다.

현재 이미 있는 테스트 중 직접 영향받는 항목:

- `test_review_runner_resurfaces_unfixed_open_finding_on_full_rerun`
- `test_review_runner_suppresses_finding_when_human_feedback_requests_ignore`

이 중 첫 번째는 새 정책 기준으로 수정 또는 대체되어야 한다.

## 6. 목표 동작 상세

### 6.1 상태별 정책 표

| Thread 상태 | 이번 run | 코드/anchor/body 변화 | 기본 동작 |
| --- | --- | --- | --- |
| 없음 | full/manual/incremental | 해당 없음 | 새 inline 게시 가능 |
| open | incremental | unchanged | 새 inline 없음, backlog only |
| open | full/manual | unchanged | 새 reminder reply 없음, backlog only |
| open | full/manual/incremental | body 또는 anchor 변화 | existing thread update 가능 |
| resolved | any | unchanged | inline 재게시 없음, backlog only |
| resolved | any | 의미 있는 변화 있음 | reopen/update 가능 |
| any | any | `bot:ignore` | suppress |
| any | any | `bot:false-positive` | suppress |
| any | any | `bot:later` | backlog only |

### 6.2 `resolve`의 의미

이번 설계에서는 `resolve`를 완전 suppress 신호로 해석하지 않는다.

정책:

- `resolve`는 여전히 penalty 신호로 남긴다.
- 다만 `resolved + unchanged`는 inline 재게시보다 backlog로 우선 보낸다.
- 즉 사용자가 resolve했다고 해서 탐지를 완전히 끄지는 않지만,
  반복적으로 같은 inline reply를 받게 하지는 않는다.

### 6.3 `false-positive`와 `ignore`의 차이

초기 구현에서는 두 명령 모두 현재 fingerprint suppress로 처리해도 된다.

단, payload와 suppression_reason은 구분한다.

- `feedback:ignore`
- `feedback:false_positive`

이유:

- 이후 분석 대시보드에서 오탐과 단순 무시를 구분할 수 있어야 한다.

### 6.4 `later`의 의미

`later`는 suppress가 아니라 **게시 지연** 신호로 해석한다.

초기 구현 정책:

- detect/scoring은 유지
- inline publish 후보에서는 제외
- summary/backlog count에 포함

중요:

- Phase 1에서는 별도 DB migration 없이 구현해야 하므로,
  `later`는 새로운 DB 상태를 만들기보다 summary/backlog 집계용 분기 처리로 다룬다.

## 7. 구현 설계

### 7.1 `FeedbackSignal` 확장

현재:

```python
@dataclass(frozen=True)
class FeedbackSignal:
    resolved_count: int = 0
    unresolved_count: int = 0
    human_reply_count: int = 0
    ignore_requested: bool = False
    allow_requested: bool = False
```

변경 후:

```python
@dataclass(frozen=True)
class FeedbackSignal:
    resolved_count: int = 0
    unresolved_count: int = 0
    human_reply_count: int = 0
    ignore_requested: bool = False
    false_positive_requested: bool = False
    later_requested: bool = False
    allow_requested: bool = False
```

### 7.2 feedback command 파싱

수정 함수:

- `_feedback_signal()`
- `_contains_feedback_command()`

추가 명령:

- `ignore`
- `false-positive`
- `later`
- `allow`

파싱 규칙:

- `bot:false-positive`
- `/review-bot false-positive`
- `bot later`
- `review-bot:allow`

현재 regex 패턴 구조는 재사용 가능하다.

### 7.3 open-thread reminder 비활성화

수정 함수:

- `_should_resurface_open_thread()`

목표:

- 기본 모드에서는 `False`
- 단, 향후 opt-in 모드가 가능하도록 settings flag를 참조

권장 구현:

```python
if not self.settings.repeat_open_thread_reminder_enabled:
    return False
```

그 뒤 기존 조건을 적용한다.

### 7.4 backlog-only 후보 처리

새 상태를 DB에 추가하지 않고, publication candidate 준비 단계에서만 처리한다.

권장 전략:

1. `PublicationCandidate`에 아래 필드 추가
   - `backlog_only: bool = False`
   - `backlog_reason: str | None = None`

2. 아래 조건이면 `backlog_only=True`
   - `feedback_signal.later_requested`
   - `existing_thread.sync_status == "open"` and unchanged rerun
   - `existing_thread.sync_status == "resolved"` and unchanged rerun and not settings.resolved_unchanged_resurface_enabled

3. `_select_batch_candidates()`에서는 `backlog_only` 후보를 제외한다.

4. `execute_publish_phase()` summary 작성 시 backlog counters를 별도로 집계한다.

### 7.5 summary 확장

수정 함수:

- `_post_pr_summary()`
- 또는 `execute_publish_phase()`에서 집계 후 전달

추가로 보여 줄 항목:

- 이번 배치 실제 게시 수
- 재게시하지 않고 backlog로 유지한 기존 open thread 수
- `later`로 보류한 항목 수
- `ignore`/`false-positive`로 suppress된 항목 수

예시 문구:

```text
---
총 4개 항목이 게시되었습니다.
기존 열린 이슈 3개는 재게시하지 않고 backlog로 유지했습니다.
사용자 피드백으로 보류된 항목 1개, 무시된 항목 2개가 있습니다.
```

중요:

- summary는 여전히 "성공 게시"와 "backlog 유지"를 분리해서 써야 한다.
- 게시되지 않은 항목을 "게시되었다"고 표현하면 안 된다.

## 8. 구현 순서

### Step 1

- `config.py`에 새 setting 2개 추가
- default는 모두 `false`

### Step 2

- `FeedbackSignal` 확장
- `_feedback_signal()`에서 `false-positive`, `later` 파싱 추가

### Step 3

- `_should_resurface_open_thread()`에서 reminder 기본 비활성화
- 기존 full/manual rerun reminder 테스트를 새 정책에 맞게 수정

### Step 4

- `PublicationCandidate`에 `backlog_only`, `backlog_reason` 추가
- candidate 준비 로직에서 backlog-only 분기 추가
- `_select_batch_candidates()`에서 backlog-only 제외

### Step 5

- publish phase summary에 backlog / feedback counters 추가

### Step 6

- 테스트 보강

## 9. 테스트 계획

### 9.1 기존 테스트 수정

- `test_review_runner_resurfaces_unfixed_open_finding_on_full_rerun`
  - 새 정책 기준으로 실패해야 한다.
  - 기대 결과를 "기존 thread에 redundant reply를 달지 않음"으로 바꾼다.

### 9.2 신규 테스트 추가

1. `test_full_rerun_does_not_reply_again_to_unchanged_open_thread_by_default`
   - 첫 run에서 comment 생성
   - 두 번째 full/manual run에서 unchanged
   - 두 번째 upsert request가 없어야 함
   - summary backlog counter가 증가해야 함

2. `test_open_thread_with_changed_body_updates_existing_thread`
   - body가 바뀐 경우에는 여전히 existing thread update 허용

3. `test_resolved_unchanged_finding_stays_backlog_only_by_default`
   - resolved 후 unchanged rerun
   - reopen/update가 발생하지 않아야 함

4. `test_feedback_false_positive_suppresses_future_candidate`
   - `bot:false-positive`
   - suppression_reason == `feedback:false_positive`

5. `test_feedback_later_keeps_candidate_out_of_inline_publish`
   - `bot:later`
   - inline publish 없음
   - backlog count 증가

6. `test_opt_in_reminder_mode_can_restore_old_behavior`
   - setting override로 reminder enabled
   - 기존 full rerun reminder reply 동작 유지 확인

### 9.3 테스트 범위

- `review-bot/tests/test_review_runner.py`
- 필요 시 `review-bot/tests/test_integration_phase1_4.py`

## 10. 수용 기준

아래 조건을 모두 만족하면 구현 완료로 본다.

1. 기본 설정에서 full/manual rerun이 unchanged open thread에 새 reminder reply를 남기지 않는다.
2. `bot:false-positive`가 suppress로 동작한다.
3. `bot:later`가 inline publish를 막고 backlog count로 남는다.
4. summary가 "실제 게시 수"와 "backlog 유지 수"를 구분해 보여 준다.
5. 기존 `bot:ignore`, `bot:allow` 동작은 유지된다.
6. opt-in setting으로 reminder behavior를 다시 켤 수 있다.

## 11. 구현 시 주의사항

- 새 DB 상태를 추가하려고 하지 말 것.
  - 이번 단계는 migration 없는 변경을 우선한다.
- `ignore`와 `false-positive`는 suppression_reason을 반드시 구분할 것.
- summary wording에서 backlog 항목을 "게시됨"으로 잘못 표현하지 말 것.
- incremental untouched thread 정책을 깨지 말 것.
- existing open thread update 경로와 reminder 경로를 혼동하지 말 것.

## 12. 권장 커밋 단위

커밋 1:

- settings
- feedback parsing
- reminder default off
- unit tests

커밋 2:

- backlog-only candidate handling
- summary counter 확장
- integration tests

## 13. 후속 작업 메모

이 문서의 Phase 1이 끝나면 다음 작업으로 이어진다.

- full-report / backlog note 또는 artifact 설계
- `false-positive`를 rule/path suppression 정책과 연결
- feedback command를 slash command UX로 정리
- summary와 analytics에서 feedback command별 카운트 분리
