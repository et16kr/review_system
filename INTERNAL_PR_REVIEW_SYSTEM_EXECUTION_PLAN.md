# 기존 Git 리뷰 시스템 연동 봇 구축 실행 설계서

## 목적

이 문서는 `~/work/review_system` 워크스페이스를 **별도 PR 시스템 제품**이 아니라,
**기존 Git PR/MR 리뷰 시스템에 붙는 리뷰 봇과 리뷰 엔진**으로 재정렬하기 위한
실행 기준 문서다.

운영에서 canonical UI는 외부 Git 리뷰 시스템이다.

- GitLab Self-Managed
- Gerrit
- 사내 기존 리뷰 도구

이 저장소가 담당할 범위는 아래 두 가지다.

1. `review-engine`
   - Altibase 우선 C++ 규칙셋 관리
   - 벡터DB 검색
   - diff/code 기반 규칙 후보 생성
2. `review-bot`
   - 외부 리뷰 시스템 webhook 수신
   - diff 조회
   - LLM 리뷰 코멘트 생성
   - 기존 PR/MR 화면에 댓글 게시

`review-platform`은 운영 제품이 아니라 로컬 데모와 통합 테스트를 위한 harness다.

## 최종 목표

개발자가 회사의 기존 Git 리뷰 시스템에 PR/MR을 열면, 봇이 다음 순서로 동작해야 한다.

1. webhook으로 이벤트를 받는다.
2. PR/MR diff를 외부 리뷰 시스템 API로 가져온다.
3. 변경된 C/C++ 파일만 골라 헝크 단위로 분석한다.
4. `review-engine`에서 관련 Altibase 규칙과 호환 가능한 C++ Core Guidelines를 찾는다.
5. LLM이 코드와 규칙을 바탕으로 리뷰 코멘트를 생성한다.
6. 봇이 기존 PR/MR 화면에 코멘트를 남긴다.
7. 한 번에 상위 5개만 게시한다.
8. 사용자가 다시 push 하면 해결된 항목은 제외하고 다음 우선순위 5개를 게시한다.

## 현재 재정렬 원칙

이번 개정에서 고정하는 원칙은 아래와 같다.

1. PR/MR UI는 외부 Git 리뷰 시스템이 담당한다.
2. `review-bot`은 provider adapter를 통해 외부 시스템과 통신한다.
3. `review-engine`은 PR/MR 개념을 모르고, diff/code 입력과 규칙 검색만 담당한다.
4. `review-platform`은 로컬 실험용이며 운영 아키텍처의 필수 요소가 아니다.
5. MVP 범위에서는 GitLab adapter를 먼저 지원하고, Gerrit은 후속 adapter로 확장한다.

## 워크스페이스 역할

### `review-engine`

- Altibase `CODING_CONVENTION.md` 파싱
- C++ Core Guidelines 파싱
- conflict resolution
- active/reference/excluded 규칙셋 관리
- Chroma 컬렉션 적재
- diff/code 패턴 추출
- 규칙 검색 및 재랭킹
- 운영용 메타데이터 정제

### `review-bot`

- webhook 수신
- 외부 리뷰 시스템 adapter 선택
- diff 조회
- 리뷰 런/파인딩/게시 이력 저장
- OpenAI/Codex 호출
- fallback provider 처리
- 상위 5개 게시 정책
- 해결/미해결 상태 관리

### `review-platform`

- bare repo 기반 로컬 PR 데모
- bot/engine 통합 테스트 harness
- 개발 중 수동 검증 화면

운영에서는 없어도 된다.

## 외부 리뷰 시스템 연동 방향

### 1. GitLab

현재 MVP에서 가장 먼저 붙이기 쉬운 대상이다.

- webhook: `Merge Request Hook`
- diff 조회:
  - `GET /api/v4/projects/:id/merge_requests/:iid/changes`
- 댓글 게시:
  - `POST /api/v4/projects/:id/merge_requests/:iid/notes`
- 상태 게시:
  - MVP에서는 bot 내부 상태 저장 우선
  - GitLab commit status / discussion 확장은 후속 과제

### 2. Gerrit

후속 adapter 대상이다.

- patchset 이벤트 수신
- change/revision diff 조회
- review label/comment 게시

현재 코드는 GitLab 기준 adapter 구조를 먼저 갖추고, Gerrit은 같은 adapter interface로 확장한다.

## 구현 완료 상태

현재 워크스페이스에서 이미 반영된 항목:

- `review-engine` active/reference/excluded 컬렉션 분리
- `review-bot`의 외부 리뷰 시스템 adapter 분리
- `local_platform` adapter
- `gitlab` adapter MVP
- OpenAI provider + stub fallback
- Redis queue + worker
- Docker Compose 기반 로컬 실행
- GitLab MR webhook 수신 엔드포인트

## 남아 있는 작업

### 1. GitLab adapter 고도화

- summary note 외에 inline discussion 지원
- commit status / check 반영
- project 단위가 아니라 그룹/여러 저장소 지원

### 2. Gerrit adapter 추가

- 이벤트 payload 파서
- patchset diff 조회
- review comment / vote 게시

### 3. review-engine 정제 강화

- `reviewability`
- `false_positive_risk`
- `trigger_patterns`
- `bot_comment_template`
- `fix_guidance`
- `review_rank_default`

### 4. 운영 안정화

- migration 도입
- 더 정교한 dedupe
- 더 안전한 secret 관리
- 관찰성 로그와 재시도 정책 보강

## 운영 모드 구분

### 로컬 데모 모드

- `REVIEW_SYSTEM_ADAPTER=local_platform`
- `review-platform` 포함 실행
- 로컬에서 전체 흐름 검증

### 외부 시스템 연동 모드

- `REVIEW_SYSTEM_ADAPTER=gitlab`
- `REVIEW_SYSTEM_BASE_URL=https://gitlab.example.com`
- `GITLAB_TOKEN=...`
- `GITLAB_PROJECT_ID=group%2Frepo`
- `GITLAB_WEBHOOK_SECRET=...`

이 모드에서는 외부 Git 리뷰 시스템이 canonical UI이며, `review-platform`은 선택 사항이다.

## 운영 시나리오

### GitLab 기준

1. 사용자가 GitLab에서 MR을 생성하거나 갱신한다.
2. GitLab webhook이 `review-bot`으로 들어온다.
3. `review-bot`이 MR `iid`를 리뷰 요청 ID로 사용한다.
4. `gitlab` adapter가 diff를 조회한다.
5. `review-engine`이 규칙 후보를 반환한다.
6. provider가 리뷰 코멘트를 만든다.
7. 봇이 MR note를 게시한다.
8. 다음 실행에서는 이미 게시한 finding을 제외하고 다음 5개를 게시한다.

## 왜 별도 PR 시스템을 만들지 않는가

이 프로젝트의 핵심 가치는 UI가 아니라 아래에 있다.

- Altibase 우선 규칙 검색
- C++ 리뷰 지식베이스
- diff 기반 자동 리뷰
- 상위 5개 배치 정책
- 해결된 finding 추적

따라서 운영에서는 기존 Git 리뷰 시스템 UI를 그대로 사용하는 편이 맞다.

## 현재 기준 정리

앞으로 이 워크스페이스에서 “완성”의 의미는 아래다.

1. 기존 Git 리뷰 시스템에 webhook으로 붙는다.
2. diff를 읽고 리뷰를 생성한다.
3. 기존 PR/MR 화면에 코멘트를 남긴다.
4. Altibase 우선 규칙셋을 사용한다.
5. 별도 PR UI 없이도 운영 가능하다.
