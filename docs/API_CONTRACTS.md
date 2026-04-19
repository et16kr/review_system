# 서비스 간 API 계약

## 목적

이 문서는 `review-engine`, `review-bot`, 그리고 외부 Git 리뷰 시스템 사이의 최소 계약을 고정한다.

운영 기준의 canonical UI는 외부 Git 리뷰 시스템이다.
`review-platform` 관련 API는 로컬 데모와 통합 테스트용 harness 계약으로만 유지한다.

## 원칙

1. `review-engine`은 규칙 검색과 diff/code 분석만 담당한다.
2. `review-bot`만 `review-engine`을 호출한다.
3. 외부 리뷰 시스템 연동은 adapter로 분리한다.
4. 외부 리뷰 시스템의 DB를 직접 읽지 않는다.
5. `review-platform` API는 운영 표준이 아니다.

## 1. 외부 리뷰 시스템 adapter 계약

`review-bot`은 아래 interface를 만족하는 adapter 하나를 선택해 사용한다.

### 필수 메서드

- `get_pull_request_diff(review_request_id)`
- `post_comment(review_request_id, body, file_path, line_no, ...)`
- `post_status(review_request_id, state, description)`

현재 구현 상태:

- `local_platform`
  - 로컬 harness adapter
- `gitlab`
  - GitLab MR 연동용 MVP adapter

### 공통 반환 형태

```json
{
  "pull_request": {
    "id": 34,
    "base_sha": "abc123",
    "head_sha": "def456"
  },
  "files": [
    {
      "path": "src/a.cpp",
      "status": "modified",
      "additions": 10,
      "deletions": 2,
      "patch": "@@ -10,6 +10,10 @@ ..."
    }
  ]
}
```

### GitLab adapter 환경 변수

```bash
REVIEW_SYSTEM_ADAPTER=gitlab
REVIEW_SYSTEM_BASE_URL=https://gitlab.example.com
GITLAB_TOKEN=...
GITLAB_PROJECT_ID=group%2Frepo
GITLAB_WEBHOOK_SECRET=...
```

### GitLab adapter MVP 동작

- diff 조회:
  - `GET /api/v4/projects/:id/merge_requests/:iid/changes`
- 댓글 게시:
  - `POST /api/v4/projects/:id/merge_requests/:iid/notes`
- 상태 게시:
  - MVP에서는 내부 상태 저장 우선
  - GitLab commit status / discussion 확장은 후속 과제

## 2. `review-bot` 공개 API

Base URL:

- `http://review-bot:18081`

### `GET /health`

용도:
- bot 프로세스 상태 확인

### `POST /internal/review/pr-opened`

용도:
- local harness 또는 내부 테스트에서 리뷰 작업을 직접 queue에 넣는다.

Request:

```json
{
  "pr_id": 34,
  "trigger": "manual"
}
```

Response:

```json
{
  "accepted": true,
  "review_run_id": 101,
  "status": "queued",
  "queue_name": "review-bot"
}
```

### `POST /internal/review/pr-updated`

용도:
- local harness 또는 내부 테스트에서 업데이트 리뷰 작업을 queue에 넣는다.

### `POST /internal/review/next-batch`

용도:
- 미게시 finding 중 다음 5개를 queue에 넣는다.

Request:

```json
{
  "pr_id": 34,
  "reason": "manual_next_batch"
}
```

### `GET /internal/review/state/{pr_id}`

용도:
- bot 내부 상태를 조회한다.

Response:

```json
{
  "pr_id": 34,
  "last_review_run_id": 101,
  "last_head_sha": "def456",
  "last_status": "success",
  "published_batch_count": 2,
  "open_finding_count": 17,
  "resolved_finding_count": 3,
  "failed_publication_count": 0,
  "next_batch_size": 5
}
```

### `POST /webhooks/gitlab/merge-request`

용도:
- GitLab `Merge Request Hook` payload를 받아 리뷰 작업을 queue에 넣는다.

지원 action:

- `open`
- `update`
- `reopen`

요청 헤더:

- `X-Gitlab-Event: Merge Request Hook`
- `X-Gitlab-Token: <secret>` 선택

Request body 예시:

```json
{
  "object_kind": "merge_request",
  "object_attributes": {
    "iid": 7,
    "action": "update"
  }
}
```

Response 예시:

```json
{
  "accepted": true,
  "event": "gitlab_merge_request",
  "action": "update",
  "review_run_id": 203,
  "status": "queued",
  "queue_name": "review-bot",
  "ignored_reason": null
}
```

무시되는 경우 예시:

```json
{
  "accepted": false,
  "event": "gitlab_merge_request",
  "action": "merge",
  "review_run_id": null,
  "status": "ignored",
  "queue_name": null,
  "ignored_reason": "unsupported_merge_request_action"
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
      "reviewability": "active_review",
      "fix_guidance": "free() 이후 포인터를 NULL로 재설정한다."
    }
  ]
}
```

### `POST /review/code`

용도:
- 코드 조각을 입력받아 규칙 후보를 반환한다.

### `POST /review/hunks`

용도:
- 여러 파일/헝크를 한 번에 분석한다.

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

현재 GitLab adapter MVP는 `GITLAB_PROJECT_ID`가 고정된 **프로젝트 단위 bot 인스턴스**를 전제로 한다.

즉 현재 `review-bot` DB의 `pr_id`는 다음 의미를 가진다.

- `local_platform` 모드:
  - local harness PR ID
- `gitlab` 모드:
  - GitLab MR `iid`

여러 프로젝트를 하나의 bot DB에서 동시에 처리하는 멀티테넌트 모델은 후속 과제다.
