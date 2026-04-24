# 서비스 간 API 계약

## 목적

이 문서는 현재 구현 기준의 `review-engine`, `review-bot`, 그리고 외부 Git 리뷰 시스템 간 계약을 고정한다.

운영 기준의 canonical UI는 외부 Git 리뷰 시스템이다.
`review-platform` 관련 API는 로컬 데모와 통합 테스트용 harness 계약으로만 유지한다.

## 원칙

1. `review-engine`은 규칙 탐지와 근거 후보 반환만 담당한다.
2. `review-bot`은 `detect -> publish -> sync` lifecycle을 책임진다.
3. 외부 리뷰 시스템 연동은 `ReviewSystemAdapterV2`로 분리한다.
4. business identity는 `ReviewRequestKey(review_system, project_ref, review_request_id)`를 사용한다.
5. `review-platform` API는 운영 표준이 아니다.

## 1. 외부 리뷰 시스템 adapter 계약

`review-bot`은 아래 interface를 만족하는 adapter 하나를 선택해 사용한다.

### 필수 메서드

- `fetch_review_request_meta(key)`
- `fetch_diff(key, mode, base_sha=None)`
- `list_threads(key)`
- `upsert_comment(key, request)`
- `resolve_thread(key, thread_ref, reason=...)`
- `publish_check(key, request)`
- `collect_feedback(key, since=None)`

### Optional capability 메서드

- `fetch_file_content(key, path, ref)`
- `post_general_note(key, body)`
- `upsert_general_note(key, body=..., purpose=...)`

위 optional method는 protocol default가 `not_supported`를 반환한다.
지원하지 않는 adapter에서는 summarize/walkthrough/full-report/backlog/help note 게시가 response-level ignored 또는 501로 끝날 수 있다.

현재 구현 상태:

- `local_platform`
  - 로컬 harness adapter
- `gitlab`
  - GitLab MR inline discussion / thread sync adapter

### 핵심 타입

```json
{
  "key": {
    "review_system": "gitlab",
    "project_ref": "group/project",
    "review_request_id": "34"
  }
}
```

Adapter가 반환하는 remote ref scope:

- `ThreadSnapshot.thread_ref`, `ThreadSnapshot.comment_ref`, `ThreadNoteSnapshot.note_ref`,
  `CommentUpsertResult.thread_ref`, `CommentUpsertResult.comment_ref`,
  `FeedbackRecord.event_key`, `FeedbackRecord.adapter_thread_ref`,
  `FeedbackRecord.adapter_comment_ref`는 모두 해당 호출의 `ReviewRequestKey` 안에서만
  unique하면 된다.
- 서로 다른 `ReviewRequestKey`가 같은 remote thread/comment/event id를 재사용할 수 있다.
- `review-bot` storage dedupe도 같은 request scope를 사용한다. `thread_sync_states`는
  `(review_request_pk, adapter_thread_ref)`, `feedback_events`는
  `(review_request_pk, event_key)`로 중복을 판단한다.

```json
{
  "pull_request": {
    "id": "34",
    "base_sha": "abc123",
    "start_sha": "bcd234",
    "head_sha": "def456"
  },
  "files": [
    {
      "path": "src/a.cpp",
      "status": "modified",
      "patch": "@@ -10,6 +10,10 @@ ..."
    }
  ]
}
```

```json
{
  "thread_ref": "discussion-1",
  "comment_ref": "note-10",
  "resolved": false,
  "notes": [
    {
      "note_ref": "note-10",
      "author_type": "bot",
      "body": "[봇 리뷰][cpp] ..."
    }
  ]
}
```

### GitLab adapter 환경 변수

```bash
REVIEW_SYSTEM_ADAPTER=gitlab
REVIEW_SYSTEM_BASE_URL=https://gitlab.example.com
GITLAB_TOKEN=...
GITLAB_WEBHOOK_SECRET=...
BOT_AUTHOR_NAME=review-bot
BOT_GITLAB_API_TIMEOUT_SECONDS=30
BOT_GITLAB_API_MAX_RETRIES=2
BOT_GITLAB_API_RETRY_BACKOFF_SECONDS=0.5
```

주의:

- `GITLAB_PROJECT_ID`는 더 이상 사용하지 않는다.
- project identity는 webhook payload의 `project.path_with_namespace`가 canonical source다.

### GitLab adapter 현재 동작

- MR 메타 조회:
  - `GET /api/v4/projects/:project/merge_requests/:iid`
- diff 조회:
  - `GET /api/v4/projects/:project/merge_requests/:iid/changes`
- large diff 누락 시 patch 재구성:
  - `GET /api/v4/projects/:project/repository/files/:path/raw?ref=:head_sha`
- inline discussion 생성:
  - `POST /api/v4/projects/:project/merge_requests/:iid/discussions`
- 기존 discussion reply:
  - `POST /api/v4/projects/:project/merge_requests/:iid/discussions/:discussion_id/notes`
- resolved discussion reopen:
  - `PUT /api/v4/projects/:project/merge_requests/:iid/discussions/:discussion_id`
- discussion resolve:
  - `PUT /api/v4/projects/:project/merge_requests/:iid/discussions/:discussion_id`
- commit status 게시:
  - `POST /api/v4/projects/:project/statuses/:head_sha`
- thread / feedback 조회:
  - `GET /api/v4/projects/:project/merge_requests/:iid/discussions`
- general note 조회:
  - `GET /api/v4/projects/:project/merge_requests/:iid/notes`
- general note 생성:
  - `POST /api/v4/projects/:project/merge_requests/:iid/notes`
- same-purpose general note 갱신:
  - `PUT /api/v4/projects/:project/merge_requests/:iid/notes/:note_id`

현재 정책:

- GitLab API 호출은 retry/backoff를 사용한다.
- discussion 목록은 pagination을 따라 끝까지 수집한다.
- inline anchor 생성 실패는 `inline_anchor` category로 분류한다.
- resolved thread가 다시 eligible해지면 새 thread보다 기존 thread reopen/update를 우선한다.

## 2. `review-bot` 공개 API

Base URL:

- `http://review-bot:18081`

### `GET /health`

용도:

- bot 프로세스 상태 확인

### `POST /internal/review/runs`

용도:

- 특정 review request key에 대한 detect job을 queue에 넣는다.

Request:

```json
{
  "key": {
    "review_system": "gitlab",
    "project_ref": "group/project",
    "review_request_id": "34"
  },
  "trigger": "manual",
  "mode": "full",
  "title": "TDE review",
  "draft": false,
  "source_branch": "feature",
  "target_branch": "main",
  "base_sha": "abc123",
  "start_sha": "bcd234",
  "head_sha": "def456"
}
```

Response:

```json
{
  "accepted": true,
  "review_run_id": "uuid",
  "status": "queued",
  "queue_name": "review-detect"
}
```

응답 정책:

- `status`는 하드코딩된 `"queued"`가 아니라 실제 `review_run.status`를 반환한다.
- dedupe로 기존 pending run을 재사용한 경우 `status`는 `queued` 또는 `running`일 수 있다.

### `POST /internal/review/runs/{run_id}/publish`

용도:

- publish job을 queue에 넣는다.

### `POST /internal/review/runs/{run_id}/sync`

용도:

- sync job을 queue에 넣는다.

### `GET /internal/review/requests/{review_system}/{project_ref}/{review_request_id}`

용도:

- 특정 review request의 현재 상태를 조회한다.

Response:

```json
{
  "key": {
    "review_system": "gitlab",
    "project_ref": "group/project",
    "review_request_id": "34"
  },
  "last_review_run_id": "uuid",
  "last_head_sha": "def456",
  "last_status": "success",
  "provider_runtime": {
    "configured_provider": "openai",
    "effective_provider": "stub",
    "fallback_used": true,
    "fallback_reason": "build_draft_error:RuntimeError",
    "configured_model": "local-model",
    "endpoint_base_url": "http://127.0.0.1:11434/v1",
    "transport_class": "non_default_openai_compatible_base_url"
  },
  "published_batch_count": 1,
  "open_finding_count": 3,
  "resolved_finding_count": 1,
  "failed_publication_count": 0,
  "next_batch_size": 10,
  "open_thread_count": 2,
  "feedback_event_count": 4,
  "dead_letter_count": 0
}
```

표현 정책:

- `provider_runtime`는 마지막 review run의 configured/effective provider, fallback 사용 여부,
  configured model, sanitized endpoint base URL, transport class를 나타낸다.
- `endpoint_base_url`는 userinfo/query/fragment를 제거한 값이다.
- legacy row나 run 부재로 provenance를 복원할 수 없으면 `provider_runtime`은 `null`일 수 있다.

### `GET /internal/review/requests/{review_system}/{project_ref}/{review_request_id}/full-report`

용도:

- 특정 review request의 "최신 run 결과 + 현재 backlog" view를 조회한다.
- inline 게시, 다음 batch 대기, backlog 유지, feedback suppress 상태를 분리해서 반환한다.
- query parameter `view`를 지원한다.
  - `view=full` — 기본값
  - `view=backlog` — backlog section만 남기고 run-specific section은 0/빈 배열로 필터링

Section별 source of truth:

| 섹션 | source of truth |
| --- | --- |
| `published_inline` | 최신 run의 `PublicationState(created/updated)` |
| `pending_batch` | 최신 run의 `FindingDecision.state == eligible` |
| `failed_publication` | 최신 run의 `FindingDecision.state == failed_publication` |
| `suppressed_feedback_*` / `suppressed_other` | 최신 run의 `FindingDecision.suppression_reason` |
| `already_open` | 최신 run에서 open thread에 다시 반영되었으나 새 게시가 없는 항목 |
| `backlog_existing_open` | 현재 `ThreadSyncState.sync_status == open` 중 unchanged backlog |
| `backlog_resolved_unchanged` | 현재 `ThreadSyncState.sync_status == resolved` 중 unchanged backlog |
| `backlog_feedback_later` | 현재 feedback signal이 `later_requested`인 backlog |

- `backlog_*` 섹션은 최신 run에서 다시 관측되지 않았더라도 MR에 실제로 남아 있으면 포함된다.
- 같은 fingerprint가 최신 run과 backlog에서 동시에 보이면 중복 카운트하지 않고 run 섹션을 우선한다.

추가 메타데이터:

- `last_*` — review request 기준 최신 run 메타데이터
- `report_*` — report 본문을 구성하는 가장 최근 완료 run 메타데이터
- `in_flight_*` — `queued`/`running` 상태의 더 새로운 run이 있을 때만 채운다

표현 정책:

- 최신 run이 `queued`/`running`이라도, 더 이전의 완료 run이 있으면 report 본문은 `report_*` 기준으로 안정적으로 렌더링한다.
- 이때 최신 in-flight run은 숨기지 않고 `in_flight_*` 필드와 note wording으로 별도 노출한다.

### `GET /internal/analytics/rule-effectiveness`

용도:

- 규칙별 유효성(게시/해소/사람의 실제 resolve 비율)을 집계한다.

집계 단위:

- row 단위가 아니라 고유 `fingerprint` (unique surfaced finding) 단위다.
- 같은 finding이 여러 번 rerun으로 쌓여도 1건으로 본다.
- 각 fingerprint는 "latest meaningful state"(resolved > published > failed_publication > suppressed/eligible/candidate/stale) 기준으로 1개 상태에만 귀속된다.

Response 각 필드 의미:

- `total` — 해당 rule의 distinct surfaced fingerprint 수
- `published` — 최신 의미 상태가 `published`인 distinct fingerprint 수
- `resolved` — 최신 의미 상태가 `resolved`인 distinct fingerprint 수
- `suppressed` — 최신 의미 상태가 `suppressed`인 distinct fingerprint 수
- `human_resolved` — `ThreadSyncState.resolution_reason ∈ {remote_resolved, remote_resolved_manual_only}`로 끝난 distinct fingerprint 수
- `resolve_rate` — `resolved / (published + resolved)`
- `human_resolve_rate` — `human_resolved / (published + resolved)`

주의:

- 이 endpoint는 rule-level effectiveness용이다.
- Phase A 이후 canonical quality KPI는 `/internal/analytics/finding-outcomes`를 우선 사용한다.

Response 예시:

```json
{
  "rules": [
    {
      "rule_no": "R.10",
      "source_family": "cpp_core",
      "total": 12,
      "published": 7,
      "resolved": 3,
      "human_resolved": 2,
      "suppressed": 2,
      "resolve_rate": 0.3,
      "human_resolve_rate": 0.2
    }
  ],
  "total_rules": 1
}
```

### `GET /internal/analytics/finding-outcomes`

용도:

- distinct fingerprint 기준으로 quality KPI와 lifecycle outcome을 집계한다.
- `fix_confirmation_rate`, `fix_conversion_rate`, `human_resolve_rate`, `false_positive_feedback_rate`의 canonical source다.

Query parameter:

- `project_ref` optional
- `source_family` optional
- `window` optional: `14d | 28d`, 기본값 `28d`

집계 단위:

- row가 아니라 distinct `fingerprint`

시점 정의:

- `first_surfaced_at`
  - `PublicationState.publish_state ∈ {created, updated, skipped}` 중 가장 이른 `published_at`
- `first_fixed_at`
  - `FindingLifecycleEvent(event_type="resolved", event_reason="fixed_in_followup_commit")`의 가장 이른 `event_at`
- `reopened_distinct`
  - 해당 window cohort 안에서 `FindingLifecycleEvent(event_type="reopened")`가 한 번 이상 있었던 distinct fingerprint 수

Response 공통 필드:

- `surfaced_distinct`
- `resolved_distinct`
- `fixed_distinct`
- `manual_resolved_distinct`
- `ignored_distinct`
- `false_positive_distinct`
- `reopened_distinct`

`window=14d`일 때 canonical KPI:

- `fix_confirmation_rate`
  - latest resolved cohort 중 `fixed_in_followup_commit` 비율
- `human_resolve_rate`
  - surfaced cohort 중 `remote_resolved_manual_only` 기반 human resolve 비율
- `false_positive_feedback_rate`
  - surfaced cohort 중 latest human feedback command가 `false-positive`인 비율

`window=28d`일 때 cohort KPI:

- `surfaced_cohort_distinct`
  - 지난 28일 안에 first surfaced 된 distinct fingerprint 수
- `converted_cohort_distinct`
  - 위 cohort 중 first surfaced 후 28일 이내 `fixed_in_followup_commit`으로 전환된 수
- `fix_conversion_rate`
  - `converted_cohort_distinct / surfaced_cohort_distinct`

Response 예시:

```json
{
  "window": "28d",
  "project_ref": "group/project",
  "source_family": "cpp_core",
  "surfaced_distinct": 120,
  "resolved_distinct": 70,
  "fixed_distinct": 48,
  "manual_resolved_distinct": 22,
  "ignored_distinct": 15,
  "false_positive_distinct": 9,
  "reopened_distinct": 6,
  "surfaced_cohort_distinct": 120,
  "converted_cohort_distinct": 41,
  "fix_confirmation_rate": 0.0,
  "human_resolve_rate": 0.0,
  "false_positive_feedback_rate": 0.0,
  "fix_conversion_rate": 0.342
}
```

### `GET /internal/analytics/wrong-language-feedback`

용도:

- 사람이 `@review-bot wrong-language <expected-language>`로 남긴 피드백을 집계한다.
- detector blind spot, 자주 틀리는 언어 쌍, 경로 기반 오분류 패턴을 확인하는 canonical source다.

Query parameter:

- `project_ref` optional
- `window` optional: `14d | 28d`, 기본값 `28d`

집계 단위:

- 현재 구현은 window 안의 parsed `wrong-language` human reply event를 집계한다.
- `distinct_threads`와 `distinct_findings`는 unique count지만, 같은 thread/finding에 repeated wrong-language reply가 있으면 `total_events`와 pair/profile/path count는 증가할 수 있다.
- smoke fixture가 의도적으로 만든 wrong-language reply도 project filter 없이 보면 포함된다.
- response는 `provenance`, `triage_cause`, `actionability`를 함께 반환해 synthetic smoke, detector miss, wrong thread target, policy mismatch를 구분한다.
- detector blind spot backlog로 바로 전환하는 대상은 `actionability=fix_detector` 후보로 제한한다.

Response 공통 필드:

- `total_events`
- `distinct_threads`
- `distinct_findings`
- `smoke_events`
- `production_events`
- `unknown_provenance_events`
- `top_language_pairs`
- `top_profiles`
- `top_paths`
- `triage_candidates`

`top_language_pairs` 각 항목:

- `detected_language_id`
- `expected_language_id`
- `count`

`top_profiles` 각 항목:

- `detected_language_id`
- `expected_language_id`
- `profile_id`
- `context_id`
- `count`

`top_paths` 각 항목:

- `detected_language_id`
- `expected_language_id`
- `path_pattern`
- `count`

`triage_candidates` 각 항목:

- `detected_language_id`
- `expected_language_id`
- `profile_id`
- `context_id`
- `path_pattern`
- `count`
- `priority`
- `provenance`: `smoke | production | unknown`
- `triage_cause`: `synthetic_smoke | detector_miss | wrong_thread_target | policy_mismatch | needs_inspection`
- `actionability`: `ignore_for_detector_backlog | inspect_thread | update_policy_or_fixture | fix_detector`
- `suggested_action`

운영 해석 가이드:

- `top_language_pairs`는 어떤 언어 조합에서 detector가 흔들리는지 보여 준다.
- `top_profiles`는 framework/context 오분류가 profile/context 축에서 집중되는지 확인하는 데 쓴다.
- `top_paths`는 `.github/workflows`, `src`, `db`, `docs` 같은 경로 버킷별 blind spot을 찾는 데 쓴다.
- `triage_candidates` 중 `actionability=fix_detector`만 detector backlog 후보로 본다.
- `synthetic_smoke`는 telemetry loop 검증 이벤트이고, `wrong_thread_target`은 detector 수정 전에 reply 대상 thread를 먼저 확인해야 한다.

Response 예시:

```json
{
  "window": "28d",
  "project_ref": "group/project",
  "total_events": 3,
  "distinct_threads": 3,
  "distinct_findings": 3,
  "smoke_events": 1,
  "production_events": 2,
  "unknown_provenance_events": 0,
  "top_language_pairs": [
    {
      "detected_language_id": "cpp",
      "expected_language_id": "markdown",
      "count": 2
    }
  ],
  "top_profiles": [
    {
      "detected_language_id": "yaml",
      "expected_language_id": "markdown",
      "profile_id": "github_actions",
      "context_id": "github_actions",
      "count": 1
    }
  ],
  "top_paths": [
    {
      "detected_language_id": "cpp",
      "expected_language_id": "markdown",
      "path_pattern": "src",
      "count": 2
    }
  ],
  "triage_candidates": [
    {
      "detected_language_id": "yaml",
      "expected_language_id": "markdown",
      "profile_id": "gitlab_ci",
      "context_id": "gitlab_ci",
      "path_pattern": ".gitlab-ci.yml",
      "count": 1,
      "priority": "high",
      "provenance": "smoke",
      "triage_cause": "synthetic_smoke",
      "actionability": "ignore_for_detector_backlog",
      "suggested_action": "Smoke telemetry 검증 이벤트입니다. 운영 detector backlog에서는 제외하고 telemetry loop 회귀 여부만 확인하세요."
    }
  ]
}
```

### `POST /webhooks/gitlab/merge-request`

용도:

- GitLab `Note Hook` payload를 받아 detect job을 queue에 넣는다.
- endpoint 이름은 유지하지만, 현재 운영 트리거는 MR note mention이다.

- 지원 조건:

- `object_kind = note`
- `noteable_type = MergeRequest`
- note body 줄 시작에 `@review-bot` 또는 `/review-bot` 명령이 있음
- system note 아님
- bot 자신이 작성한 note 아님

지원 명령:

- `@review-bot review` 또는 `/review-bot review` — detect job enqueue
- `@review-bot summarize` 또는 `/review-bot summarize` — 최신 상태 aggregate를 보여 주는 summarize note 게시
- `@review-bot walkthrough` 또는 `/review-bot walkthrough` — summarize/backlog/full-report 읽는 순서를 안내하는 walkthrough note 게시
- `@review-bot full-report` 또는 `/review-bot full-report` — 최신 full-report note 게시
- `@review-bot backlog` 또는 `/review-bot backlog` — 현재 backlog만 보여 주는 note 게시
- `@review-bot help` 또는 `/review-bot help` — 지원 명령을 안내하는 help note 게시
- `@review-bot` 단독 mention — `review`로 해석
- mention 뒤에는 공백뿐 아니라 `:`, `,`, `.`도 허용한다. 예: `@review-bot, review`

파서 정책:

- 명령 매칭은 줄 시작 기준(`^\s*@name ...`)으로만 이루어진다. "please ping @review-bot when ready" 같은 문장 중 incidental mention은 무시한다.
- 알 수 없는 token(`@review-bot fullreport` 등)이 뒤에 오면 리뷰를 실행하지 않고, general note가 지원되는 adapter에서는 supported command 안내 note를 게시한다. webhook response는 `action=unknown_command`, `ignored_reason=unknown_command:...`를 포함한다.
- mention 자체가 아예 없으면 `ignored_reason=missing_review_request_mention:@review-bot`으로 응답한다.

추가 정책:

- MR open/update webhook은 더 이상 리뷰를 시작하지 않고 ignore한다.
- mention comment로 시작한 run은 현재 MR 전체 diff를 기준으로 `manual` mode로 실행된다.
- detect phase 시작 시 현재 thread snapshot과 feedback를 먼저 반영한다.
- batch가 작아도 기존 open thread의 실제 update는 새 finding 게시보다 우선한다.
- body/anchor 변화가 없는 기존 open thread는 `skipped`로 기록하지만 batch slot은 소모하지 않는다.
- resolved thread가 다시 eligible하면 full reconcile에서 기존 thread를 reopen/update 한다.
- human reply에 `bot:ignore`, `/bot ignore`, `review-bot:ignore`가 들어 있으면 이후 동일 fingerprint는 suppress 된다.
- human reply에 `bot:allow`, `/bot allow`, `review-bot:allow`가 들어 있으면 score penalty를 일부 상쇄한다.
- summarize note는 최신 run/head, provider provenance, aggregate backlog/suppress count만 빠르게 보여 준다.
- walkthrough note는 summarize -> backlog -> full-report 순서와 backlog reason 해석을 안내한다.
- full-report note는 "최신 run 결과 + 현재 MR에 남아 있는 backlog"를 함께 보여 준다.
- backlog note는 현재 MR에 실제로 남아 있는 backlog만 보여 준다.
- help note는 현재 지원 명령을 간단히 안내한다. adapter가 general note를 지원하지 않으면 webhook response만 `posted` 없이 ignored로 끝낼 수 있다.
- summarize / walkthrough / full-report / backlog / help / unknown-command note는 adapter가 `upsert_general_note`를 지원하면 same-purpose update를 우선한다.
- run-level summary note는 현재 append-only를 유지한다.
- `project.path_with_namespace` 또는 MR `iid`가 없으면 400을 반환한다.

Request body 예시:

```json
{
  "object_kind": "note",
  "user": {
    "username": "alice"
  },
  "project": {
    "path_with_namespace": "group/project"
  },
  "merge_request": {
    "iid": 7,
    "title": "TDE review",
    "source_branch": "tde_first",
    "target_branch": "tde_base",
    "last_commit": {
      "id": "def456"
    }
  },
  "object_attributes": {
    "id": 501,
    "note": "@review-bot review 부탁드립니다.",
    "noteable_type": "MergeRequest",
    "system": false
  }
}
```

Response 예시:

```json
{
  "accepted": true,
  "event": "gitlab_note",
  "action": "mention",
  "review_run_id": "uuid",
  "status": "queued",
  "queue_name": "review-detect",
  "ignored_reason": null
}
```

추가 응답 예시:

```json
{
  "accepted": true,
  "event": "gitlab_note",
  "action": "full_report",
  "review_run_id": null,
  "status": "posted",
  "queue_name": null,
  "ignored_reason": null
}
```

### Future `ask` note command boundary

상태:

- 이 섹션은 `ask` command를 구현하기 전의 boundary contract다.
- 현재 live `review-bot`은 아직 `ask`를 지원 명령으로 파싱하지 않는다. 구현 전까지
  `@review-bot ask ...`는 directed unknown command로 처리된다.
- `ask`는 구현되더라도 `review`처럼 detect/publish lifecycle을 만들지 않는 note-family read path다.

Context source 범위:

- `ReviewRequestKey(review_system, project_ref, review_request_id)`가 가리키는 현재 MR/request 안에서만
  context를 모은다.
- 사용할 수 있는 context는 최신 run state, 최신 full-report/backlog view, inline finding evidence,
  publication/thread/feedback state, provider runtime provenance, adapter가 이미 지원하는 same-file
  head/base snippet, 그리고 같은 `project_ref`의 review-engine index/search가 반환한 similar-code
  evidence로 제한한다.
- 기본 v1은 MR source branch 전체 checkout, 임의 repository crawl, 외부 ticket/wiki, 다른 project의
  review history, provider-side chat memory를 context source로 쓰지 않는다.
- `ask` 답변은 사용한 context category와 stale/missing context reason을 note 안에 짧게 남긴다.

Session / retention boundary:

- v1 `ask`는 provider chat session을 저장하거나 다음 `ask` 호출에 이어 붙이지 않는다.
- durable 저장은 기존 webhook/request metadata, same-purpose general note, structured log,
  provider runtime provenance, timeout/error diagnostic에 한정한다.
- 질문 원문을 별도 장기 conversation store에 저장하는 기능은 v1 범위가 아니다. 필요해지면 retention,
  redaction, access boundary를 별도 contract로 먼저 정의한다.

Unavailable / timeout / empty-evidence policy:

- provider unavailable 또는 provider timeout이면 detect/publish를 enqueue하지 않고, same-purpose `ask`
  general note에 `temporarily_unavailable` 또는 `provider_timeout` reason을 남긴다.
- review state가 아직 없거나 context source가 비어 있으면 answer를 생성하지 않고 `empty_evidence`
  reason을 남긴다. 이때 `@review-bot review`, `@review-bot summarize`, `@review-bot walkthrough`
  중 다음에 볼 command를 안내할 수 있다.
- adapter가 general note를 지원하지 않으면 webhook response는 posted 없이 ignored/unsupported로 끝날 수 있다.
- provider fallback이 설정되어 있더라도 `ask` note에는 effective provider, fallback 여부,
  configured model, sanitized endpoint base URL, transport class를 lifecycle provenance와 같은 형식으로 남긴다.

Note-family UX 목적:

- `summarize`는 aggregate state를 빠르게 보여 주고, `walkthrough`는 어떤 note를 어떤 순서로 읽을지 안내한다.
- `ask`는 그 다음 단계에서 사용자가 MR에 남은 finding/backlog/current run에 대해 좁은 질문을 할 때 쓰는
  scoped Q&A command다.
- `ask`는 inline finding을 새로 만들거나 backlog disposition을 바꾸지 않는다. 사용자가 disposition을
  바꾸려면 기존 feedback command(`bot:ignore`, `bot:false-positive`, `bot:later`, `bot:allow`,
  `bot:wrong-language <lang>`)를 사용한다.

### `.review-bot.yaml` repository config contract

상태:

- 이 섹션은 `.review-bot.yaml` runtime loader를 구현하기 전의 v1 계약이다.
- 현재 live `review-bot`은 아직 이 파일을 읽지 않는다. 구현 전까지는 env/default와 note command가
  실제 동작의 source of truth다.
- 파일 위치는 repository root의 `.review-bot.yaml`이다.
- config는 MR source head가 아니라 target/base revision에서 읽는다. config 변경 자체는 리뷰를 거쳐
  target branch에 들어간 뒤 다음 review request부터 적용된다.

v1 최소 surface:

```yaml
version: 1
review:
  enabled: true
  paths:
    include:
      - "**/*"
    exclude:
      - "docs/generated/**"
publish:
  batch_size: 5
  rule_family_cap: 2
  file_comment_cap: 2
  minimum_publish_score: 0.70
```

필드 의미:

- `version`: required. v1에서는 정수 `1`만 허용한다.
- `review.enabled`: optional bool. `false`이면 `review` command는 detect/publish를 만들지 않고,
  가능하면 visible config-disabled note를 남긴다.
- `review.paths.include`: optional string list. 비어 있거나 생략되면 모든 adapter 제공 diff path를
  후보로 둔다.
- `review.paths.exclude`: optional string list. include 이후 제거할 path glob이다.
- `publish.batch_size`: optional positive int. env `BOT_BATCH_SIZE`의 hard cap 안에서만 낮출 수 있다.
- `publish.rule_family_cap`: optional positive int. env `BOT_RULE_FAMILY_CAP`의 hard cap 안에서만
  낮출 수 있다.
- `publish.file_comment_cap`: optional positive int. env `BOT_FILE_COMMENT_CAP`의 hard cap 안에서만
  낮출 수 있다.
- `publish.minimum_publish_score`: optional number between `0` and `1`. env
  `BOT_MINIMUM_PUBLISH_SCORE`보다 낮게 설정할 수 없다.

v1에서 다루지 않는 값:

- `ReviewRequestKey`, `project_ref`, adapter 선택, GitLab URL/token/webhook secret, queue 이름,
  database/Redis URL, provider/model/base URL/API key, bot author identity는 env/orchestrator
  source of truth로만 유지한다.
- `ask`, provider session, codebase retrieval memory, prompt override, rule pack/profile authoring,
  private extension install/update는 `.review-bot.yaml` v1 surface가 아니다. `ask` command 자체의
  future boundary는 위 섹션에서 별도 관리한다.

Precedence:

| 결정 영역 | 우선순위 | 정책 |
| --- | --- | --- |
| Security / identity / adapter | env/orchestrator only | repo config에 해당 key가 있으면 fail-fast |
| Per-invocation action | MR note command | `review`만 detect enqueue, report-style commands는 enqueue하지 않음 |
| Review enablement | env service availability -> repo `review.enabled` | repo config는 review를 끌 수 있지만 service/env disabled 상태를 켤 수 없음 |
| File eligibility | adapter diff -> built-in reviewability -> repo include/exclude | repo config는 후보를 좁힐 수 있지만 unreviewable type을 강제로 reviewable로 만들 수 없음 |
| Publish volume | env hard cap -> repo value -> runtime suppress/rerank | repo config는 cap을 낮추거나 score threshold를 올리는 방향만 허용 |
| Provider behavior | env/provider runtime only | repo config가 provider/model/endpoint/fallback을 바꾸지 않음 |

Validation / error policy:

| 상태 | 정책 |
| --- | --- |
| 파일 없음 | ignore, env/default 사용 |
| adapter가 target/base file fetch를 지원하지 않음 | warn metadata를 남기고 env/default 사용 |
| malformed YAML, unsupported `version`, unknown key, invalid type | fail-fast config error |
| forbidden key(provider, token, adapter, queue, identity 등) | fail-fast config error |
| repo value가 env hard cap보다 완화적임 | fail-fast config error |
| include/exclude 이후 reviewable file이 없음 | no-op success, provider 호출과 inline publish 없음 |

Note-first UX 관계:

- `@review-bot review`와 `/review-bot review`만 config를 적용한 detect/publish lifecycle을 시작한다.
- `summarize`, `walkthrough`, `backlog`, `full-report`는 current state를 읽는 note-family
  command다. 이 명령들은 새 review run을 만들지 않고, invalid config가 source branch에 추가되어도
  그 자체만으로 실패하지 않는다.
- `help`는 supported command 안내 note이며 새 review run을 만들지 않는다.
- `summarize`는 최신 run/head, provider provenance, aggregate backlog/suppress count를 보여 준다.
- `walkthrough`는 summarize -> backlog -> full-report 읽기 순서를 안내한다.
- `backlog`는 현재 MR thread state 기준 backlog만 보여 준다.
- `full-report`는 최신 완료 run 결과와 현재 backlog를 함께 보여 준다.
- unknown directed command는 config와 무관하게 no-enqueue visible feedback 경로를 유지한다.

## 3. `review-engine` API

Base URL:

- `http://review-engine:18082`

### `POST /review/diff`

용도:

- diff 전체를 입력받아 규칙 후보를 반환한다.

Request:

```json
{
  "diff": "@@ -10,6 +10,10 @@ ...",
  "top_k": 10,
  "file_path": "src/a.cpp",
  "file_context": "optional full or partial file content",
  "language_id": "cpp",
  "profile_id": "default",
  "context_id": null,
  "dialect_id": null
}
```

Response:

```json
{
  "query_text": "Review this C++ diff for ...",
  "detected_patterns": [
    "malloc_free",
    "free_without_null_reset"
  ],
  "results": [
    {
      "rule_no": "R.10",
      "pack_id": "cpp_core",
      "source_family": "cpp_core",
      "authority": "external",
      "conflict_policy": "compatible",
      "title": "Avoid malloc() and free()",
      "section": "R",
      "priority": 0.98,
      "score": 0.94,
      "summary": "free() 직후 NULL을 대입한다.",
      "text": "...",
      "category": "memory",
      "reviewability": "auto_review",
      "fix_guidance": "free() 이후 포인터를 NULL로 재설정한다.",
      "language_id": "cpp",
      "context_id": null,
      "dialect_id": null,
      "source_kind": "public_standard",
      "priority_tier": "override",
      "pack_weight": 0.72,
      "conflict_action": "compatible"
    }
  ]
}
```

호환성 메모:

- `pack_id`가 canonical pack identity다.
- `source_family`는 legacy read-only alias이며 현재는 `pack_id`와 같은 값으로만 반환한다.

### `POST /review/code`

용도:

- 코드 조각을 입력받아 규칙 후보를 반환한다.

### `GET /rule/{rule_no}`

용도:

- 특정 규칙 전문 조회

### `POST /ingest`

용도:

- 규칙셋 재적재
- active/reference/excluded 컬렉션 summary 반환

현재 컬렉션 이름은 language suffix를 가진다.
예: `guideline_rules_active_cpp`, `guideline_rules_reference_yaml`, `guideline_rules_excluded_cuda`

### `POST /codebase/index`

용도:

- 허용된 local root 아래의 reviewable file을 chunk로 나누어 `codebase_chunks` 컬렉션에 적재한다.
- `project_ref`를 주면 그 프로젝트 전용 codebase scope에 적재한다.
- `REVIEW_ENGINE_CODEBASE_ALLOWED_ROOTS`가 있으면 그 경로 아래만 허용한다.
- 설정이 없으면 기본적으로 `review-engine` parent workspace 아래를 허용한다.

Request:

```json
{
  "root_path": "/home/et16/work/review_system",
  "clear_first": true,
  "project_ref": "root/review-system-smoke"
}
```

### `POST /codebase/search`

용도:

- `codebase_chunks`에서 similar code snippet을 검색한다.
- `project_ref`를 주면 같은 project scope 안에서만 similar code를 검색한다.
- `project_ref`를 생략하면 legacy shared scope를 사용한다.

Request:

```json
{
  "query": "changed code snippet",
  "top_k": 3,
  "project_ref": "root/review-system-smoke"
}
```

## 4. `review-platform` local harness API

이 섹션은 운영 표준이 아니라 local harness 계약이다.

Base URL:

- `http://review-platform:18080`

### `POST /api/repos`

용도:

- bare repo 등록

### `POST /api/pull-requests`

용도:

- 로컬 PR 생성

### `GET /api/pull-requests/{pr_id}/diff`

용도:

- 로컬 PR diff 조회

### `POST /api/pull-requests/{pr_id}/comments`

용도:

- 로컬 PR 댓글 게시

### `POST /api/pull-requests/{pr_id}/statuses`

용도:

- 로컬 PR 상태 게시

## 5. 데이터 스코프 주의사항

현재 `review-bot`의 business identity는 아래 composite key다.

```text
review_system + project_ref + review_request_id
```

즉 같은 `iid`라도 project가 다르면 다른 review request로 저장한다.

legacy `pr_id` endpoint는 current-state에서 제거되었다. local harness와 테스트는 runner helper 또는 `ReviewRequestKey` 기반 API를 사용한다.
