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
      "body": "[봇 리뷰] ..."
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

### `POST /webhooks/gitlab/merge-request`

용도:

- GitLab `Note Hook` payload를 받아 detect job을 queue에 넣는다.
- endpoint 이름은 유지하지만, 현재 운영 트리거는 MR note mention이다.

- 지원 조건:

- `object_kind = note`
- `noteable_type = MergeRequest`
- note body에 `@review-bot` mention 포함
- system note 아님
- bot 자신이 작성한 note 아님

추가 정책:

- MR open/update webhook은 더 이상 리뷰를 시작하지 않고 ignore한다.
- mention comment로 시작한 run은 현재 MR 전체 diff를 기준으로 `manual` mode로 실행된다.
- detect phase 시작 시 현재 thread snapshot과 feedback를 먼저 반영한다.
- batch가 작아도 기존 open thread의 실제 update는 새 finding 게시보다 우선한다.
- body/anchor 변화가 없는 기존 open thread는 `skipped`로 기록하지만 batch slot은 소모하지 않는다.
- resolved thread가 다시 eligible하면 full reconcile에서 기존 thread를 reopen/update 한다.
- human reply에 `bot:ignore`, `/bot ignore`, `review-bot:ignore`가 들어 있으면 이후 동일 fingerprint는 suppress 된다.
- human reply에 `bot:allow`, `/bot allow`, `review-bot:allow`가 들어 있으면 score penalty를 일부 상쇄한다.
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
  "event": "gitlab_merge_request",
  "action": "update",
  "review_run_id": "uuid",
  "status": "queued",
  "queue_name": "review-detect",
  "ignored_reason": null
}
```

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
  "top_k": 10
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
      "rule_no": "ALTI-MEM-007",
      "source_family": "altibase",
      "authority": "internal",
      "conflict_policy": "authoritative",
      "title": "Assign NULL immediately after free()",
      "section": "ALTI-MEM",
      "priority": 0.98,
      "score": 0.94,
      "summary": "free() 직후 NULL을 대입한다.",
      "text": "...",
      "category": "memory",
      "reviewability": "auto_review",
      "fix_guidance": "free() 이후 포인터를 NULL로 재설정한다."
    }
  ]
}
```

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
