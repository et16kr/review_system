# Workspace 분리 구조 제안

## 1. 목적

이 문서는 `~/work/review_system` 아래에 사내 PR 리뷰 시스템을 구축할 때,
어떤 폴더 구조와 서비스 경계를 기준으로 작업할지 고정하기 위한 문서이다.

이 문서의 기준은 다음과 같다.

- `review-engine`: 규칙/벡터DB/검색 엔진
- `review-platform`: Git PR 리뷰 시스템 본체
- `review-bot`: 자동 리뷰 실행기
- `ops`: 실행 및 배포 자산
- `docs`: 상위 설계 문서

## 2. 추천 디렉터리 구조

```text
~/work/review_system/
  docs/
    WORKSPACE_SPLIT_ARCHITECTURE.md
    SERVICE_PYPROJECT_TEMPLATES.md
    API_CONTRACTS.md
  ops/
    docker-compose.yml
    .env.example
    nginx/
    scripts/
  review-engine/
    app/
    data/
    examples/
    tests/
    Dockerfile
    pyproject.toml
    README.md
  review-platform/
    app/
      api/
      db/
      git/
      pr/
      web/
      auth/
    tests/
    Dockerfile
    pyproject.toml
    README.md
  review-bot/
    app/
      api/
      bot/
      jobs/
      providers/
      storage/
    tests/
    Dockerfile
    pyproject.toml
    README.md
```

## 3. 서비스 책임

### 3.1 `review-engine`

책임:

- Altibase `CODING_CONVENTION.md` 파싱
- C++ Core Guidelines 파싱
- conflict resolution
- active/reference/excluded 규칙셋 관리
- ChromaDB 적재
- 코드/`diff` 패턴 추출
- 규칙 검색과 재랭킹
- `inspect_rule`, `review_code`, `review_diff` API
- vector DB 정제

넣지 말아야 할 것:

- 사용자/세션
- PR 목록/상세
- 댓글 저장
- Git 저장소 CRUD
- 리뷰 게시 이력 DB

### 3.2 `review-platform`

책임:

- bare Git 저장소 등록
- 사용자 인증
- 저장소 목록/상세
- PR 생성/목록/상세
- branch 비교와 diff 생성
- 코멘트와 리뷰 UI
- PR 상태 저장

넣지 말아야 할 것:

- ChromaDB 접근
- 규칙 파서
- LLM 호출
- 자동 리뷰 랭킹 정책

### 3.3 `review-bot`

책임:

- PR 생성/업데이트 이벤트 수신
- `review-platform`에서 diff 조회
- `review-engine`에서 규칙 후보 조회
- LLM/Codex 호출
- finding 생성 및 점수화
- dedupe
- 상위 5개 게시
- 재실행 시 다음 5개 게시
- 리뷰 런 상태 저장

넣지 말아야 할 것:

- Git 저장소 직접 소유
- 규칙 파서/ingest
- 사용자 웹 UI

## 4. 서비스 간 의존 규칙

의존 방향은 반드시 아래를 지킨다.

```text
review-platform ---> review-bot ---> review-engine
         \__________________________/
                 API 호출만 허용
```

세부 규칙:

1. `review-platform`은 `review-engine`을 직접 호출하지 않는다.
2. `review-platform`은 자동 리뷰 요청을 `review-bot`에 전달한다.
3. `review-bot`만 `review-engine`을 호출한다.
4. `review-engine`은 다른 서비스의 DB를 직접 읽지 않는다.
5. 서비스 간 통신은 HTTP JSON 계약으로만 한다.

## 5. 데이터 소유권

### `review-engine`

- ChromaDB 컬렉션
- 규칙 원문 파싱 결과 JSON
- active/reference/excluded 데이터셋

### `review-platform`

- Postgres
- 사용자
- 저장소
- PR
- 파일 diff
- 사람이 남긴 댓글
- 봇 댓글이 표시되는 UI 상태

### `review-bot`

- 리뷰 런 상태
- finding
- publication history
- batch 상태
- queue 작업 상태

## 6. 공용 객체

공용 객체는 최소한으로 유지한다.

### `PullRequestRef`

```json
{
  "repo_id": 12,
  "pr_id": 34,
  "base_branch": "main",
  "head_branch": "feature/memory-fix",
  "base_sha": "abc123",
  "head_sha": "def456"
}
```

### `ChangedFile`

```json
{
  "path": "src/id/idu/iduShmDump.cpp",
  "status": "modified",
  "additions": 12,
  "deletions": 3,
  "patch": "@@ -10,6 +10,10 @@ ..."
}
```

### `RuleCandidate`

```json
{
  "rule_no": "ALTI-MEM-007",
  "source_family": "altibase",
  "authority": "internal",
  "priority": 0.98,
  "score": 0.94,
  "summary": "free() 직후 NULL을 대입한다."
}
```

### `BotFinding`

```json
{
  "fingerprint": "pr34:src/a.cpp:120:ALTI-MEM-007:free-null-reset",
  "file_path": "src/a.cpp",
  "line_no": 120,
  "rule_no": "ALTI-MEM-007",
  "title": "free() 이후 포인터를 NULL로 재설정하지 않음",
  "summary": "이중 해제 또는 해제 후 사용 위험을 줄이기 위해 즉시 NULL 재설정이 필요합니다.",
  "severity": "high",
  "confidence": 0.92
}
```

## 7. 런타임 구성

초기 compose 기준 서비스:

- `platform-web`
- `bot-worker`
- `bot-api`
- `engine-api`
- `postgres`
- `redis`
- `chroma`
- `nginx`

권장 포트:

- `platform-web`: `18080`
- `bot-api`: `18081`
- `engine-api`: `18082`
- `postgres`: `15432`
- `redis`: `16379`
- `chroma`: `18000`

## 8. 구현 순서

### 8.1 1차

- 현재 코드를 `review-engine` 개념으로 고정
- `docs/`와 `ops/` 추가
- `review-platform` 골격 생성
- `review-bot` 골격 생성

### 8.2 2차

- `review-platform`에 DB/PR/Git diff 구현
- `review-engine`에 vector DB 정제 스키마 추가
- `review-bot`에 review run/finding/publication 모델 추가

### 8.3 3차

- `review-platform` UI 추가
- `review-bot`에 LLM provider 추가
- top 5 정책과 재실행 정책 연결

## 9. 현재 저장소에서의 이동 계획

현 저장소의 내용은 사실상 `review-engine` 후보이다.

현재 파일들은 아래처럼 이동하는 것이 맞다.

- `app/` -> `review-engine/app/`
- `data/` -> `review-engine/data/`
- `examples/` -> `review-engine/examples/`
- `tests/` -> `review-engine/tests/`
- `CODING_CONVENTION.md` -> `review-engine/CODING_CONVENTION.md`
- `README.md` -> `review-engine/README.md`

루트에 남길 것:

- `docs/`
- `ops/`
- workspace 공통 실행 문서

## 10. repo 분리 시점

처음에는 별도 git repo로 나누지 않는다. 아래 조건이 충족되면 분리한다.

1. `review-engine` API 계약이 안정됨
2. `review-platform`과 `review-bot`이 독립 배포 가능함
3. cross-service 변경 빈도가 줄어듦

그 전까지는 한 workspace 안에서 폴더로 유지한다.
