# 서비스 간 API 계약

## 1. 목적

이 문서는 `review-engine`, `review-platform`, `review-bot` 사이의 HTTP 계약을 고정한다.
초기 구현은 이 문서를 우선 기준으로 삼는다.

## 2. 원칙

1. 서비스 간 통신은 JSON HTTP만 사용한다.
2. 다른 서비스의 DB를 직접 읽지 않는다.
3. `review-platform`은 자동 리뷰 요청을 `review-bot`에만 보낸다.
4. `review-bot`만 `review-engine`을 호출한다.

## 3. `review-engine` API

Base URL:

- `http://review-engine:18082`

### `POST /review/diff`

목적:
- diff 전체를 입력받아 규칙 후보를 반환

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
      "text": "..."
    }
  ]
}
```

### `POST /review/code`

목적:
- 코드 조각을 입력받아 규칙 후보를 반환

Request:

```json
{
  "code": "void f(){ char* p=(char*)malloc(10); free(p); }",
  "top_k": 10
}
```

### `POST /review/hunks`

목적:
- PR의 여러 파일/헝크를 한 번에 분석하기 위한 확장 API

Request:

```json
{
  "items": [
    {
      "path": "src/a.cpp",
      "input_kind": "diff",
      "content": "@@ -10,3 +10,6 @@ ..."
    },
    {
      "path": "src/b.h",
      "input_kind": "code",
      "content": "..."
    }
  ],
  "top_k_per_item": 8
}
```

Response:

```json
{
  "items": [
    {
      "path": "src/a.cpp",
      "detected_patterns": [
        "malloc_free"
      ],
      "results": [
        {
          "rule_no": "ALTI-MEM-007",
          "score": 0.94
        }
      ]
    }
  ]
}
```

### `GET /rule/{rule_no}`

목적:
- 특정 규칙 전문 조회

### `POST /ingest`

목적:
- 규칙셋 재적재

## 4. `review-platform` API

Base URL:

- `http://review-platform:18080`

### `POST /api/repos`

목적:
- bare repo 등록

Request:

```json
{
  "name": "altibase-sample",
  "description": "internal sample repo",
  "default_branch": "main"
}
```

### `POST /api/pull-requests`

목적:
- PR 생성

Request:

```json
{
  "repository_id": 1,
  "title": "Fix memory handling",
  "description": "free() 이후 NULL 재설정",
  "base_branch": "main",
  "head_branch": "feature/fix-memory"
}
```

Response:

```json
{
  "id": 34,
  "repository_id": 1,
  "title": "Fix memory handling",
  "base_branch": "main",
  "head_branch": "feature/fix-memory",
  "base_sha": "abc123",
  "head_sha": "def456",
  "status": "open"
}
```

### `GET /api/pull-requests/{pr_id}`

목적:
- PR 메타데이터 조회

### `GET /api/pull-requests/{pr_id}/diff`

목적:
- PR diff와 changed files 조회

Response:

```json
{
  "pull_request": {
    "id": 34,
    "repository_id": 1,
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

### `POST /api/pull-requests/{pr_id}/comments`

목적:
- 사람 또는 봇 댓글 게시

Request:

```json
{
  "file_path": "src/a.cpp",
  "line_no": 120,
  "comment_type": "inline",
  "author_type": "bot",
  "body": "[봇 리뷰] free() 이후 NULL 재설정이 필요합니다."
}
```

### `POST /api/pull-requests/{pr_id}/statuses`

목적:
- 봇 상태 표시

Request:

```json
{
  "context": "review-bot",
  "state": "running",
  "description": "자동 리뷰 실행 중"
}
```

## 5. `review-bot` API

Base URL:

- `http://review-bot:18081`

### `POST /internal/review/pr-opened`

목적:
- PR 생성 이벤트 수신

Request:

```json
{
  "pr_id": 34,
  "trigger": "pr_opened"
}
```

Response:

```json
{
  "accepted": true,
  "review_run_id": 1001,
  "status": "queued"
}
```

### `POST /internal/review/pr-updated`

목적:
- 새 commit push 후 재리뷰 큐 등록

### `POST /internal/review/next-batch`

목적:
- 수동으로 다음 5개 게시

Request:

```json
{
  "pr_id": 34,
  "reason": "manual_next_batch"
}
```

### `GET /internal/review/state/{pr_id}`

목적:
- 현재 리뷰 상태 조회

Response:

```json
{
  "pr_id": 34,
  "last_review_run_id": 1001,
  "last_head_sha": "def456",
  "published_batch_count": 1,
  "open_finding_count": 17,
  "resolved_finding_count": 3,
  "next_batch_size": 5
}
```

## 6. `review-bot` 내부 동작 계약

`review-bot`은 다음 순서로 동작한다.

1. `review-platform`에서 PR diff 조회
2. C/C++ 파일만 필터링
3. 각 파일/헝크를 `review-engine`에 전달
4. 규칙 후보와 코드 조각을 LLM provider에 전달
5. finding 생성
6. fingerprint dedupe
7. 아직 게시되지 않은 상위 5개를 `review-platform` 댓글 API로 게시

## 7. finding 스키마

```json
{
  "fingerprint": "pr34:src/a.cpp:120:ALTI-MEM-007:free-null-reset",
  "file_path": "src/a.cpp",
  "line_no": 120,
  "rule_no": "ALTI-MEM-007",
  "source_family": "altibase",
  "severity": "high",
  "confidence": 0.92,
  "score": 0.94,
  "title": "free() 이후 포인터를 NULL로 재설정하지 않음",
  "summary": "해제 후 재사용 위험을 줄이기 위해 즉시 NULL 대입이 필요합니다.",
  "guideline_excerpt": "Assign NULL immediately after free()",
  "suggested_fix": "free(ptr); ptr = NULL;"
}
```

## 8. 에러 응답 규칙

세 서비스는 공통으로 아래 형식을 따른다.

```json
{
  "error": {
    "code": "invalid_request",
    "message": "top_k must be between 1 and 30"
  }
}
```

## 9. 구현 우선순위

1. `review-platform`의 PR diff API
2. `review-bot`의 PR 이벤트 API
3. `review-engine`의 `/review/hunks`
4. `review-platform`의 댓글/상태 API

이 네 계약이 먼저 고정되어야 실제 코드 구현이 흔들리지 않는다.
