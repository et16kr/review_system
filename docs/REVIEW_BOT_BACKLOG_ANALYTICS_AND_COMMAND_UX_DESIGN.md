# Review Bot Backlog / Analytics / Command UX Design

- 문서 상태: Implemented Reference
- 작성일: 2026-04-21
- 최종 갱신일: 2026-04-21
- 대상 독자: AI agent, 구현 담당자
- 관련 문서:
  - `docs/API_CONTRACTS.md`
  - `docs/REVIEW_BOT_REDESIGN_DESIGN.md`
  - `docs/REVIEW_BOT_REPEAT_FEEDBACK_POLICY_DESIGN.md`
  - `docs/REVIEW_BOT_ADDITIONAL_IDEAS.md`

## 0. 현재 반영 상태

이 문서는 원래 구현 지시용 상세 설계였고,
현재 트리에서는 아래 항목이 이미 반영되었다.

- `full-report` / `backlog`가 current backlog 기준으로 집계된다.
- `full-report`는 최신 in-flight run이 있어도 가장 최근 완료 run 기준으로 본문을 구성하고, in-flight run은 별도 메타데이터로 노출한다.
- `/internal/analytics/rule-effectiveness`와 rule weight 계산이 distinct fingerprint 기준으로 교정되었다.
- GitLab note parser는 explicit command 기반으로 동작하며 `help` / `backlog` / `full-report`를 지원한다.
- full-report / backlog / help general note는 same-purpose update를 우선한다.
- `/full-report?view=backlog` filtered API가 추가되었다.
- 테스트는 worker-scoped SQLite DB 경로를 사용하도록 정리되었다.

남아 있는 후속 개선은 구현 누락이라기보다 선택적 고도화에 가깝다.

- run-level summary note까지 same-purpose update로 바꿀지
- note purpose를 hidden marker 외 별도 persistent ref로 관리할지
- per-test transaction isolation까지 더 밀어붙일지

## 1. 목적

이 문서는 최근 코드 리뷰에서 확인된 제품성/정확도/UX 이슈를 바탕으로
`review-bot`의 다음 개선 작업을 구현 가능한 수준으로 정리한다.

이번 설계의 핵심 목표는 아래 3가지다.

- `full-report` / `backlog`가 실제 현재 backlog를 정확히 보여 주게 한다.
- analytics와 rule learning이 rerun 횟수에 의해 왜곡되지 않게 한다.
- GitLab note command UX를 안전하고 예측 가능하게 만든다.

부가 목표는 아래와 같다.

- MR 일반 note가 과도하게 누적되는 문제를 완화한다.
- 테스트/운영 편의성을 개선해 구현과 검증 비용을 낮춘다.

이 문서는 아이디어 문서가 아니라, 실제 코드 변경의 기준이 되는 실행 설계다.

## 2. 리뷰 결과 요약

아래 문제 목록은 이 문서가 작성될 당시의 분석 기준이다.
현재 코드베이스에서는 대부분 해결되었고, 구현 의도와 검증 기준을 남기기 위해 보존한다.

### 2.1 현재 시스템의 강점

- GitLab-first inline discussion lifecycle이 이미 잘 잡혀 있다.
- `detect -> publish -> sync` 파이프라인과 thread sync 모델이 비교적 안정적이다.
- `ignore` / `false-positive` / `later` / `allow` 같은 human feedback 해석이 이미 도입되어 있다.
- batch 제한과 summary / full-report 보조 note 구조는 운영형 리뷰 봇 방향과 잘 맞는다.

### 2.2 이번 리뷰에서 확인된 핵심 문제

#### 문제 A. `full-report` / `backlog`가 최신 run만 보고 전체 backlog를 놓친다

현재 `build_full_report()`는 최신 run의 `FindingDecision`만 대상으로 삼는다.

그 결과:

- 최신 run이 incremental일 때 이전 run에서 이미 열려 있던 unresolved thread가 report에서 빠질 수 있다.
- 실제 MR에는 open thread가 남아 있는데 `backlog_existing_open`이 0으로 보일 수 있다.
- 사용자 입장에서는 `@review-bot backlog`가 "현재 남아 있는 전체 현황"이 아니라
  "최신 run에서 다시 관측된 일부 항목"처럼 보이게 된다.

이 문제는 제품 신뢰도를 직접 깎는다.

#### 문제 B. analytics와 rule learning이 `decision row` 기준이라 rerun에 취약하다

현재:

- `/internal/analytics/rule-effectiveness`
- `_load_rule_effectiveness_weights()`

두 경로 모두 `FindingDecision.id` row 수를 기준으로 집계하는 부분이 있다.

그 결과:

- 같은 finding이 rerun마다 새 row로 쌓이면 실제보다 많이 surfaced된 것처럼 보인다.
- 한 번의 human resolve가 여러 번 resolve된 것처럼 계산될 수 있다.
- 특정 rule이 rerun이 많은 프로젝트에서 과대평가되거나 과소평가될 수 있다.

즉, 현재 집계 단위는 "고유 finding"이 아니라 "탐지 실행 row"에 가깝다.

#### 문제 C. GitLab note command parser가 너무 공격적이다

현재 구현은 명령을 인식하지 못해도 `@review-bot` 멘션만 있으면 기본값으로 `review`를 실행한다.

실제 부작용:

- `@review-bot help`
- `@review-bot fullreport`
- `please ping @review-bot when ready`

같은 note도 모두 리뷰 실행으로 해석될 수 있다.

이 동작은 아래 측면에서 좋지 않다.

- 오타가 곧바로 리뷰 실행으로 이어진다.
- 일반 대화나 메모가 bot trigger가 된다.
- 사용자가 command set을 배우기 어렵다.

### 2.3 부가 개선 포인트

#### 부가 문제 D. 일반 note가 append-only라 MR이 길어진다

현재 summary / full-report / 향후 help note는 모두 새 general note를 추가하는 방식이다.

이는 short-term에는 단순하지만, long-running MR에서는 다음 문제가 생긴다.

- 같은 종류의 bot note가 여러 번 누적된다.
- 최신 상태를 찾기 어렵다.
- 사용자 경험이 noisy해진다.

#### 부가 문제 E. 테스트가 shared SQLite에 의존해 병렬 실행에 약하다

현재 테스트는 순차 실행에서는 안정적이지만,
병렬 실행 시 같은 SQLite DB 파일을 공유해 간섭이 발생할 수 있다.

이는 제품 버그는 아니지만, 구현 생산성과 CI 확장성에는 불리하다.

## 3. 목표 상태

이번 설계가 완료된 뒤의 기대 동작은 아래와 같다.

1. `@review-bot backlog`는 현재 MR에 남아 있는 backlog를 신뢰할 수 있게 보여 준다.
2. `@review-bot full-report`는 "최신 run 결과"와 "현재 backlog"를 혼동 없이 보여 준다.
3. analytics와 rule learning은 rerun row가 아니라 고유 finding 단위로 계산된다.
4. `@review-bot help` 같은 명령은 의도대로 동작하고, 오타나 일반 멘션은 안전하게 무시된다.
5. 문서와 API 계약이 실제 런타임과 일치한다.

## 4. 비범위

이번 작업에는 아래를 포함하지 않는다.

- GitHub / Gerrit adapter 구현
- vector DB retrieval 전략의 전면 개편
- LLM provider 교체
- 대규모 DB 스키마 재설계
- GitLab UI 확장 기능 개발

필요하면 부가 개선은 Phase 2로 넘긴다.

## 5. 설계 원칙

1. canonical current state는 "최신 run row"가 아니라 "SCM thread 상태 + 현재 추적 상태"다.
2. analytics의 집계 단위는 실행 row가 아니라 고유 finding이어야 한다.
3. 명령 파서는 보수적으로 해석한다.
4. inline review artifact가 primary이고, summary / full-report note는 보조 인터페이스다.
5. 가능한 한 API shape는 크게 깨지지 않도록 유지한다.

## 6. 설계 상세

### 6.1 `full-report` / `backlog` 의미 재정의

이번 설계에서는 `latest run view`와 `current backlog view`를 명확히 분리한다.

#### 현재 문제 요약

현재 `build_full_report()`는 최신 run의 decision만 훑는다.
따라서 최신 incremental run에서 touched file이 아닌 기존 open thread는 report에서 사라질 수 있다.

#### 목표 의미

- `latest run`
  - 최신 detect/publish 결과
  - 이번 run에서 새로 게시된 항목
  - 이번 run 기준 pending / suppress / failed 상태

- `current backlog`
  - 지금 이 MR에 실제로 남아 있는 open/resolved backlog
  - 기존 open thread
  - resolved but unchanged backlog
  - `bot:later`로 backlog only가 된 항목

#### 선택한 설계

기존 `/full-report` endpoint shape는 가능하면 유지하되,
section별 source of truth를 아래처럼 재정의한다.

| 섹션 | source of truth |
| --- | --- |
| `published_inline` | latest run의 `PublicationState(created/updated)` |
| `pending_batch` | latest run의 `FindingDecision.state == eligible` |
| `failed_publication` | latest run의 `FindingDecision.state == failed_publication` |
| `suppressed_*` | latest run의 `FindingDecision.suppression_reason` |
| `backlog_existing_open` | 현재 `ThreadSyncState.sync_status == open` 중 unchanged backlog |
| `backlog_resolved_unchanged` | 현재 `ThreadSyncState.sync_status == resolved` 중 unchanged backlog |
| `backlog_feedback_later` | 현재 feedback signal이 `later_requested`인 backlog |
| `already_open` | latest run에서 open thread update 대상이었으나 새 게시 없이 유지된 항목 |

즉:

- run-specific 섹션은 latest run 기반
- backlog 섹션은 current thread state 기반

#### 출력 정책

- `@review-bot full-report`
  - latest run 결과 + current backlog를 함께 보여 준다.

- `@review-bot backlog`
  - current backlog 섹션만 필터링해서 보여 준다.

현재 구현은 note renderer 분기뿐 아니라
`/full-report?view=backlog` filtered API까지 함께 제공한다.

#### 구현 기준

`review-bot/review_bot/bot/review_runner.py`

추가 또는 변경할 핵심 helper는 아래와 같다.

1. `_current_backlog_entries(...)`
   - `ThreadSyncState`와 최신 usable decision metadata를 조합해 backlog row를 만든다.

2. `_latest_decision_for_fingerprint(...)`
   - report item title / summary / severity를 채울 때 사용할 최신 decision을 가져온다.

3. `build_full_report(...)`
   - latest run 기반 섹션과 current backlog 기반 섹션을 병합한다.
   - 동일 fingerprint가 두 source에서 동시에 나타나면 중복 카운트하지 않는다.

#### dedupe 규칙

- backlog section에서는 `fingerprint`를 canonical identity로 사용한다.
- 같은 fingerprint가 latest run과 current backlog 양쪽에서 보이더라도
  "이미 게시된 최신 run finding"과 "기존 open backlog"를 중복 표기하지 않는다.
- current backlog는 section별 distinct fingerprint 기준으로 집계한다.

### 6.2 analytics / rule learning 집계 단위 교정

#### 현재 문제

현재는 rerun마다 새로 쌓이는 `FindingDecision` row 수가 집계에 직접 반영된다.

이것은 아래 두 곳에 모두 영향을 준다.

- `/internal/analytics/rule-effectiveness`
- `_load_rule_effectiveness_weights()`

#### 목표 집계 단위

집계 단위는 `unique surfaced finding`이어야 한다.

현재 코드 기준에서는 `fingerprint`가 충분히 안정적인 canonical identity다.
`fingerprint` 안에는 review request key, file, issue signature가 모두 들어 있다.

따라서 이번 설계에서는 아래 원칙을 사용한다.

- count는 가능한 한 `distinct fingerprint` 기준
- 필요하면 "최신 상태"는 `fingerprint`별 latest decision 기준
- human resolve도 `distinct fingerprint` 기준

#### `/internal/analytics/rule-effectiveness` 목표 의미

응답에서 각 rule의 수치는 아래 의미를 가져야 한다.

- `published`
  - 현재 surfaced/open 상태인 distinct fingerprint 수
- `resolved`
  - resolved 상태인 distinct fingerprint 수
- `suppressed`
  - latest meaningful state가 suppressed인 distinct fingerprint 수
- `human_resolved`
  - `remote_resolved`로 끝난 distinct fingerprint 수
- `resolve_rate`
  - `resolved / (published + resolved)`
- `human_resolve_rate`
  - `human_resolved / (published + resolved)`

중요:

- denominator는 row 수가 아니라 distinct fingerprint 수여야 한다.
- rerun이 많아도 같은 finding은 1건으로 본다.

#### `_load_rule_effectiveness_weights()` 목표 의미

rule weight는 "이 rule이 실제로 도움 되었는가"를 근사해야 한다.

이번 설계에서는 아래를 사용한다.

- `total`
  - distinct surfaced fingerprint 수
- `human_resolved`
  - distinct fingerprint 중 `remote_resolved` 된 수

weight 계산식 자체는 현재 공식을 유지해도 되지만,
입력 count는 distinct fingerprint 기준으로 바꾼다.

#### 구현 기준

핵심 구현 방식은 아래 2안 중 하나다.

##### 권장안

- `fingerprint -> latest meaningful state` subquery를 만든다.
- analytics와 learning이 같은 subquery를 재사용한다.

##### 단순안

- Python 단에서 `rule_no -> set[fingerprint]`를 만든다.
- small data 기준으로 먼저 안정성을 확보한다.

초기 구현은 단순안으로도 충분하지만,
향후 데이터가 커질 수 있으므로 공통 helper를 두는 편이 좋다.

### 6.3 GitLab note command parser 재설계

#### 현재 문제

현재 parser는 명령을 인식하지 못해도 멘션만 있으면 `review`로 fallback한다.

이 fallback은 오작동을 만든다.

#### 목표 정책

명령은 explicit하게 파싱한다.

지원 명령:

- `@review-bot review`
- `@review-bot full-report`
- `@review-bot backlog`
- `@review-bot help`
- `/review-bot review`
- `/review-bot full-report`
- `/review-bot backlog`
- `/review-bot help`

#### 기본 해석 규칙

1. recognized command면 해당 동작 수행
2. bare mention only면 `review`로 허용 가능
3. unknown token이 뒤에 오면 리뷰 실행하지 않음
4. 문장 중 incidental mention은 무시

예시:

- `@review-bot`
  - 허용: review trigger
- `@review-bot review 부탁드립니다`
  - 허용: review trigger
- `@review-bot help`
  - help note
- `@review-bot fullreport`
  - unknown command, no enqueue
- `please ping @review-bot when ready`
  - incidental mention, no enqueue

#### `help` 명령

초기 구현은 general note 하나로 충분하다.

예시 내용:

- 지원 명령 목록
- `review`, `full-report`, `backlog`, `help`
- 현재 정책 간단 설명

adapter가 general note를 지원하지 않으면 webhook response만 `ignored`로 끝내도 된다.

#### 구현 기준

`review-bot/review_bot/api/main.py`

- `_extract_gitlab_note_command()`는 단순 `str | None` 대신
  richer result를 돌려줄 수 있게 바꾼다.
- 예:
  - `command`
  - `is_bare_mention`
  - `is_unknown_command`
  - `matched_text`

초기 구현에서는 dataclass나 tuple 중 단순한 형태를 선택해도 된다.

### 6.4 일반 note lifecycle 개선

이 항목은 원래 Phase 2 성격으로 분류했지만,
현재 구현에서는 `full-report` / `backlog` / `help`에 대해 same-purpose update가 반영되었다.

#### 현재 문제

- summary
- full-report
- 향후 help

모두 append-only면 MR note가 누적된다.

현재 상태:

- `full-report`
- `backlog`
- `help`

는 adapter의 `upsert_general_note()`가 있으면 update를 우선한다.

- run-level summary는 여전히 append-only다.
- 즉 note clutter 문제는 "일반 명령 note" 기준으로는 완화되었고,
  "배치 이력 note" 기준으로는 현재 정책을 유지한다.

#### 목표 정책

같은 `note purpose`에 대해서는 가능하면 update를 우선한다.

권장 note purpose:

- `summary`
- `full-report`
- `backlog`
- `help`

#### 구현 옵션

현재 구현은 hidden purpose marker + adapter note lookup/update 방식을 사용한다.

향후 더 밀어붙일 수 있는 권장안:

- 별도 state 저장소에 `note_purpose -> adapter_note_ref`를 보존
- 다음 게시에서는 note lookup 없이 direct update
- summary note까지 same-purpose lifecycle로 확장할지 별도 결정

### 6.5 테스트 / 개발 편의 개선

이 항목도 제품 동작보다 개발 편의에 가깝지만,
다음 구현 작업을 안정적으로 만들기 위해 기록한다.

#### 현재 상태

- `review-bot/tests/conftest.py`에서 worker-scoped `BOT_DATABASE_URL`을 주입한다.
- 기본 테스트 실행은 shared repo DB 대신 임시 sqlite 파일을 사용한다.
- xdist worker 간 직접 충돌 가능성은 크게 줄었다.

#### 남은 개선 가능성

- per-test transaction rollback 기반 isolation
- SQLite 대신 PostgreSQL test profile 추가
- schema drop/create를 덜 쓰는 fixture 구조로 점진 전환

## 7. 구현 결과 요약

### 7.1 Phase 1 Must-Fix

1. 완료: `full-report` / `backlog`를 current backlog 기반으로 보강
2. 완료: analytics / learning을 distinct fingerprint 기준으로 교정
3. 완료: GitLab note parser를 explicit command 기반으로 교체
4. 완료: `help` command 추가
5. 완료: `docs/API_CONTRACTS.md`와 테스트 보강

### 7.2 Phase 2 Should-Fix

1. 완료: general note upsert / same-purpose update
2. 완료: backlog-only filtered API(`view=backlog`) 추가
3. 완료: 테스트 DB isolation 정리

## 8. 파일별 변경 포인트

### 8.1 `review-bot/review_bot/bot/review_runner.py`

주요 변경 포인트:

- `build_full_report()`
- `_load_rule_effectiveness_weights()`
- report item / backlog helper 추가
- backlog-only renderer / in-flight report 표시 추가

추가 후보 helper:

- `_current_backlog_entries()`
- `_latest_decision_for_fingerprint()`
- `_fingerprint_state_snapshot()`

### 8.2 `review-bot/review_bot/api/main.py`

주요 변경 포인트:

- `_extract_gitlab_note_command()`
- `_handle_gitlab_note_hook()`
- `/internal/analytics/rule-effectiveness`
- `/internal/review/requests/.../full-report?view=backlog`

### 8.3 `review-bot/review_bot/schemas.py`

현재 구현에서는 existing response shape를 크게 깨지 않으면서도
아래 메타데이터가 추가되었다.

- `report_*`
- `in_flight_*`

즉 report 본문 기준 run과 최신 in-flight run을 구분해서 표현한다.

### 8.4 `review-bot/review_bot/review_systems/base.py`, `gitlab.py`

현재 구현에서 추가 반영된 포인트:

- `upsert_general_note()`
- hidden purpose marker 기반 same-purpose note update
- GitLab MR note list / update API 활용

### 8.5 `docs/API_CONTRACTS.md`

반드시 반영해야 한다.

특히 아래를 명시한다.

- `full-report`의 backlog section은 current backlog 기준임
- `backlog` command 의미
- rule effectiveness 응답 필드와 의미
- `help` command 지원 여부

### 8.6 테스트

필수 보강 테스트:

- incremental latest run 이후에도 `backlog_existing_open`가 이전 open thread를 포함한다.
- `@review-bot help`는 review run을 만들지 않는다.
- `@review-bot fullreport` 같은 unknown command는 review run을 만들지 않는다.
- incidental mention은 무시된다.
- same fingerprint rerun이 많아도 analytics / weights가 distinct fingerprint 기준으로 유지된다.

## 9. 테스트 계획

### 9.1 Backlog correctness

시나리오:

1. first run에서 A, B 두 finding이 게시된다.
2. second incremental run에서는 C만 touched되어 새 finding이 생성된다.
3. A, B thread는 여전히 open 상태다.
4. `build_full_report()` 또는 `@review-bot backlog` 결과에서 A, B가 backlog에 보여야 한다.

검증:

- `published_inline == ["src/c.cpp"]`
- `backlog_existing_open` 또는 대응 backlog section에 `src/a.cpp`, `src/b.cpp` 포함

### 9.2 Command parser safety

시나리오:

- `@review-bot help`
- `@review-bot fullreport`
- `please ping @review-bot when ready`
- `@review-bot review`

검증:

- `help`만 help 동작
- unknown / incidental mention은 no enqueue
- explicit `review`만 enqueue

### 9.3 Analytics / learning stability

시나리오:

1. 같은 fingerprint를 여러 번 rerun으로 쌓는다.
2. 실제 human resolve는 한 번만 준다.

검증:

- `/internal/analytics/rule-effectiveness`의 수치가 row 수가 아니라 fingerprint 수를 따른다.
- `_load_rule_effectiveness_weights()`가 resolve_rate를 과도하게 올리지 않는다.

### 9.4 Contract regression

검증:

- `docs/API_CONTRACTS.md` 내용과 API 테스트가 일치한다.
- `full-report` note wording이 실제 의미와 어긋나지 않는다.

## 10. 롤아웃 방안

이 문서의 설계는 현재 로컬 코드와 테스트 기준으로 반영되었다.
아래는 historical rollout ordering을 참고용으로 남긴다.

### 10.1 적용 순서

1. analytics / learning aggregation 수정
2. command parser 수정
3. backlog/full-report source 교정
4. 문서 갱신
5. GitLab staging 또는 local compose 검증

### 10.2 운영 리스크

- backlog source를 current state 기준으로 바꾸면 기존 `full-report` 숫자가 달라질 수 있다.
- command parser를 보수적으로 바꾸면 기존 "멘션만 하면 리뷰 시작" 습관이 있는 사용자에게 변화가 생길 수 있다.

대응:

- `help` note에서 새 command 사용법을 안내한다.
- 릴리즈 노트 또는 운영 문서에 변경 사실을 짧게 기록한다.

## 11. 최종 판단

현재 시스템은 운영형 리뷰 봇의 기본 구조를 이미 갖추고 있다.

- inline-first
- lifecycle-aware thread sync
- feedback-aware suppression
- batch + summary + full-report 보조 인터페이스

문제는 "엔진이 부족하다"가 아니라,
"현재 state를 얼마나 정확하고 친절하게 보여 주는가" 쪽에 더 가깝다.

따라서 다음 우선순위는 아래와 같다.

1. backlog truthfulness
2. analytics / learning correctness
3. command UX safety
4. note clutter reduction

즉, 지금 가장 가치가 큰 일은 탐지 모델을 더 복잡하게 만드는 것이 아니라,
현재 lifecycle 위에 정확한 상태 표현과 예측 가능한 UX를 얹는 것이다.
