# Workspace 분리 구조 제안

## 목적

이 문서는 `~/work/review_system` 워크스페이스를
**기존 Git 리뷰 시스템에 붙는 봇 중심 구조**로 유지하기 위한 경계 문서다.

운영에서 canonical UI는 외부 Git 리뷰 시스템이며, 이 워크스페이스는 그 위에 붙는
엔진과 봇을 제공한다.

## 추천 구조

```text
~/work/review_system/
  docs/
    WORKSPACE_SPLIT_ARCHITECTURE.md
    SERVICE_PYPROJECT_TEMPLATES.md
    API_CONTRACTS.md
    OPERATIONS_RUNBOOK.md
  ops/
    docker-compose.yml
    .env.example
    nginx/
  review-engine/
    app/
    data/
    tests/
    Dockerfile
    pyproject.toml
  review-bot/
    app/
      api/
      bot/
      db/
      providers/
      queueing.py
      review_systems/
      worker.py
    tests/
    Dockerfile
    pyproject.toml
  review-platform/
    ...
```

## 서비스 책임

### `review-engine`

책임:

- Altibase `CODING_CONVENTION.md` 파싱
- C++ Core Guidelines 파싱
- conflict resolution
- active/reference/excluded 규칙셋 관리
- ChromaDB 적재
- 코드/`diff` 패턴 추출
- 규칙 검색과 재랭킹
- vector DB 정제

넣지 말아야 할 것:

- PR/MR 메타데이터
- webhook 처리
- 외부 리뷰 시스템 API 호출
- 댓글 게시 이력 저장

### `review-bot`

책임:

- 외부 Git 리뷰 시스템 webhook 수신
- diff 조회
- `review-engine` 호출
- LLM/Codex 호출
- dedupe
- 상위 5개 게시 정책
- 해결/미해결 상태 관리
- 리뷰 런, finding, publication 이력 저장

넣지 말아야 할 것:

- 규칙 파싱/ingest
- Git 저장소 호스팅
- 별도 PR UI 제품화

### `review-platform`

책임:

- 로컬 bare repo 생성
- 로컬 PR 생성/목록/상세
- diff UI
- bot/engine 통합 테스트 harness

제한:

- 운영 canonical UI가 아니다.
- 운영 필수 구성요소가 아니다.

## 의존 방향

```text
External Git Review System ---> review-bot ---> review-engine
```

예시:

- GitLab Self-Managed
- Gerrit
- 사내 기존 리뷰 도구

세부 원칙:

1. 기존 Git 리뷰 시스템이 canonical UI다.
2. `review-bot`만 `review-engine`을 호출한다.
3. `review-engine`은 다른 서비스 DB를 읽지 않는다.
4. 외부 시스템 연동은 `review-bot/app/review_systems/` 아래 adapter로 분리한다.
5. `review-platform`은 local harness로만 유지한다.

## 데이터 소유권

### `review-engine`

- Chroma 컬렉션
- 규칙 파싱 결과 JSON
- active/reference/excluded 데이터셋

### `review-bot`

- Postgres
- review run
- finding
- publication history
- queue 작업 상태

### `review-platform`

- 로컬 bare repo
- 로컬 PR/댓글/상태 샘플 데이터

## 현재 adapter 상태

### 구현됨

- `local_platform`
  - 로컬 harness 용
- `gitlab`
  - GitLab MR diff 조회
  - GitLab note 게시
  - GitLab webhook 수신 진입점

### 후속 예정

- `gerrit`
  - patchset 이벤트
  - change diff 조회
  - review label/comment 게시

## 운영 결론

이 워크스페이스의 운영 핵심은 아래 두 서비스다.

- `review-engine`
- `review-bot`

`review-platform`은 계속 남겨 둘 수 있지만, 운영 아키텍처의 중심으로 간주하지 않는다.
