# 사내 Git PR 리뷰 시스템 및 리뷰 봇 구축 실행 설계서

## 1. 문서 목적

이 문서는 현재 저장소를 출발점으로 하여 아래 세 가지를 모두 구축하기 위한
실행 문서이다.

1. 사내에서 사용할 최소 기능의 Git PR 리뷰 시스템
2. 벡터DB와 LLM을 사용하는 자동 코드리뷰 봇
3. 봇 리뷰에 맞게 정제된 C++ 가이드라인 벡터DB

이 문서는 "더 좋은 일반론"이 아니라, **이 저장소를 기준으로 내가 그대로
구현을 진행하기 위한 작업 지시서**로 작성한다.

## 2. 목표와 범위

### 2.1 최종 목표

개발자가 사내 Git 서버에 브랜치를 push 하고 PR을 생성하면, 시스템은 다음을 수행해야 한다.

1. PR의 diff를 수집한다.
2. 변경된 C/C++ 파일에서 리뷰 패턴을 추출한다.
3. 벡터DB에서 관련 Altibase 규칙과 호환 가능한 C++ Core Guidelines를 검색한다.
4. LLM이 코드와 가이드라인을 바탕으로 리뷰 코멘트를 생성한다.
5. 봇이 PR에 코멘트를 남긴다.
6. 한 번에 상위 5개만 게시한다.
7. 사용자가 수정 후 다시 push 하면, 이미 해결된 항목은 제외하고 다음 우선순위 5개를 게시한다.

### 2.2 MVP 범위

MVP는 아래만 보장한다.

- 사내 bare Git 저장소 호스팅
- SSH를 통한 `git push`, `git clone`
- 웹에서 PR 생성, PR 목록, PR 상세, diff 확인
- inline comment와 summary comment
- 봇 자동 리뷰 실행
- 최대 5개 finding 게시
- 재실행 시 해결된 항목 제외
- Altibase 규칙 우선의 벡터 검색
- 리뷰 실행 이력 저장

### 2.3 MVP에서 제외할 항목

다음은 1차 구현에서 제외한다.

- 조직/팀/권한 복잡 모델
- merge queue
- 대규모 알림 시스템
- 다국어 코드리뷰
- 대형 monorepo 최적화
- 정교한 IDE 통합
- 고급 코드 오너 자동 지정

## 3. 현재 저장소의 출발점

현재 저장소는 **리뷰 엔진 MVP** 상태이다. 이미 구현된 것은 다음과 같다.

- Altibase `CODING_CONVENTION.md` 파서
- C++ Core Guidelines HTML 파서
- 충돌 해소 및 활성 규칙셋 생성
- ChromaDB 적재
- 코드/`diff`에서 패턴을 추출하는 질의 변환기
- 규칙 검색 및 재랭킹
- CLI
- FastAPI 기본 API
- Altibase 코드 excerpt / diff fixture 기반 테스트

현재 상태의 한계는 다음과 같다.

- Git PR 시스템 자체는 없다.
- PR/MR diff 수집기가 없다.
- 봇 계정/코멘트 게시기가 없다.
- 리뷰 이력 저장 DB가 없다.
- 현재 벡터DB는 "검색 엔진" 중심이며 "운영용 리뷰 지식베이스" 메타데이터가 부족하다.
- 임베딩이 해시 기반이라 의미 검색 품질이 제한적이다.

## 4. 최종 시스템 아키텍처

이 문서는 전체 제품을 end-to-end로 설명하는 상위 실행 문서이다. 실제 워크스페이스
분리 구조와 서비스 경계는 아래 문서를 기준으로 함께 유지한다.

- `docs/WORKSPACE_SPLIT_ARCHITECTURE.md`
- `docs/SERVICE_PYPROJECT_TEMPLATES.md`
- `docs/API_CONTRACTS.md`

### 4.1 구성요소

최종 시스템은 하나의 workspace 안에서 아래 구성요소를 가진다.

1. `review-engine`
   - Altibase / C++ Core Guideline 파싱
   - conflict resolution
   - ChromaDB 적재
   - 코드/`diff` 질의 변환
   - 규칙 검색 및 재랭킹

2. `review-platform`
   - Git 저장소 관리
   - PR 생성/목록/상세
   - diff UI
   - 댓글/리뷰 UI
   - 사용자와 권한

3. `review-bot`
   - PR 이벤트 수신
   - 리뷰 작업 큐 등록
   - 리뷰 결과 저장
   - 댓글 게시
   - 5개 배치 정책 관리

4. `Git Storage`
   - bare repo 저장소
   - OpenSSH + `git-shell`

5. `LLM Provider Layer`
   - Codex/OpenAI provider
   - 필요 시 로컬 모델 provider로 교체 가능한 추상화

6. `Operational Database`
   - Postgres
   - PR, 리뷰 런, finding, 댓글, 게시 이력 저장

7. `Queue`
   - Redis 기반 작업 큐

8. `Vector Store`
   - ChromaDB
   - 정제된 활성 규칙 컬렉션

### 4.2 배포 구조

초기 배포는 Docker Compose 기준으로 구성한다.

- `review-platform`: FastAPI + server-rendered UI
- `review-bot`: 비동기 리뷰 작업 처리
- `review-engine`: 규칙 검색 API
- `postgres`
- `redis`
- `chroma`
- `nginx`

## 5. 핵심 설계 결정

### 5.1 Git PR 시스템은 직접 구축하되 Git 프로토콜 전체를 새로 만들지 않는다

직접 구현할 범위는 "PR 메타데이터와 리뷰 UI"이며, Git object storage와 transport는
기존 `git`과 `git-shell`을 사용한다.

즉, 구조는 다음과 같다.

- 저장소는 `/srv/git/repos/<name>.git` 형태의 bare repo
- 사용자는 `git@host:<name>.git`로 push/clone
- 웹 애플리케이션은 같은 bare repo를 읽어서 branch 비교와 diff 생성

이 방식은 "사내 Git PR 리뷰 시스템"을 만들면서도 구현 난이도를 크게 줄인다.

### 5.2 서비스는 세 개로 분리하되, 처음에는 하나의 workspace에서 함께 개발한다

MVP 구현은 아래 세 서비스를 기준으로 나눈다.

- `review-engine`
- `review-platform`
- `review-bot`

단, 처음부터 별도 git repo로 분리하지는 않는다. 먼저 한 workspace 안에 폴더로
분리하고, 인터페이스가 안정되면 독립 repo로 승격한다.

이 방식의 장점:

- 책임 경계가 명확하다.
- cross-service contract를 일찍 고정할 수 있다.
- 초기 개발 속도를 잃지 않는다.
- 이후 독립 배포로 넘어가기 쉽다.

### 5.3 벡터DB는 "참고 규칙 저장소"가 아니라 "게시 가능한 리뷰 후보 저장소"로 재설계한다

현재 ChromaDB는 규칙 검색용으로는 동작하지만, 운영용 봇 기준으로는 아래가 부족하다.

- 게시 가능 여부
- diff 기반 자동 리뷰 적합성
- 코멘트 템플릿
- false positive 위험도
- 적용 단위
- 설명과 예시의 충분성

따라서 벡터DB 레코드 스키마를 확장하고, 일부 규칙은 active review set에서 제외한다.

## 6. 최종 사용자 시나리오

1. 사용자가 저장소를 생성한다.
2. 사용자가 feature branch를 push 한다.
3. 사용자가 base branch와 head branch를 선택하여 PR을 생성한다.
4. 시스템이 PR diff를 계산한다.
5. 리뷰 봇이 자동 실행된다.
6. 봇이 상위 5개 finding을 게시한다.
7. 사용자가 코드를 수정하고 같은 PR에 다시 push 한다.
8. 시스템이 새 commit 기준으로 diff를 갱신한다.
9. 이미 해결된 finding은 closed 처리한다.
10. 아직 남아 있는 finding 중 다음 우선순위 5개를 다시 게시한다.

## 7. 데이터 모델 설계

### 7.1 Postgres 테이블

#### `users`
- `id`
- `username`
- `display_name`
- `password_hash`
- `is_admin`
- `created_at`

#### `repositories`
- `id`
- `name`
- `description`
- `storage_path`
- `default_branch`
- `created_by`
- `created_at`

#### `pull_requests`
- `id`
- `repository_id`
- `title`
- `description`
- `base_branch`
- `head_branch`
- `base_sha`
- `head_sha`
- `status`
- `created_by`
- `created_at`
- `updated_at`

#### `pull_request_files`
- `id`
- `pull_request_id`
- `path`
- `status`
- `additions`
- `deletions`
- `patch_text`

#### `pull_request_comments`
- `id`
- `pull_request_id`
- `file_path`
- `line_no`
- `comment_type`
- `author_type`
- `author_id`
- `body`
- `created_at`

#### `review_runs`
- `id`
- `pull_request_id`
- `head_sha`
- `status`
- `trigger`
- `started_at`
- `completed_at`
- `error_message`

#### `review_findings`
- `id`
- `review_run_id`
- `pull_request_id`
- `fingerprint`
- `file_path`
- `line_no`
- `rule_no`
- `source_family`
- `severity`
- `confidence`
- `score`
- `title`
- `summary`
- `guideline_excerpt`
- `suggested_fix`
- `status`

#### `finding_publications`
- `id`
- `pull_request_id`
- `finding_id`
- `batch_no`
- `published_comment_id`
- `published_at`

#### `bot_review_state`
- `pull_request_id`
- `last_review_run_id`
- `last_published_batch_no`
- `last_head_sha`
- `open_finding_count`
- `resolved_finding_count`

### 7.2 Chroma 레코드 확장 필드

기존 `GuidelineRecord`에 아래 필드를 추가한다.

- `reviewability`
  - `auto`
  - `semi_auto`
  - `reference_only`
- `applies_to`
  - `line`
  - `hunk`
  - `file`
  - `pr`
- `category`
  - `memory`
  - `portability`
  - `error_handling`
  - `naming`
  - `format`
  - `control_flow`
  - `ownership`
  - `concurrency`
- `trigger_patterns`
- `false_positive_risk`
- `bot_comment_template`
- `fix_guidance`
- `good_example`
- `bad_example`
- `review_rank_default`

### 7.3 컬렉션 분리

Chroma 컬렉션은 세 개로 분리한다.

1. `guideline_rules_active`
   - 자동 리뷰 후보

2. `guideline_rules_reference`
   - 참고용 규칙

3. `guideline_rules_excluded`
   - 충돌 또는 비활성 규칙

## 8. 벡터DB 정제 설계

### 8.1 현재 문제

현재 데이터셋에는 아래 문제가 있다.

- `summary == title`인 레코드가 많다.
- 일부 C++ Core 파싱 결과에 `???` 같은 노이즈가 있다.
- 규칙 중 상당수가 diff 기반 자동 리뷰에 적합하지 않다.
- 해시 기반 임베딩은 의미 검색 품질이 약하다.

### 8.2 정제 목표

정제 후 active review set은 아래 조건을 만족해야 한다.

- PR diff에 대해 자동으로 코멘트를 만들 수 있는 규칙만 포함
- 규칙 설명이 짧고 명확해야 함
- 실제 코멘트에 들어갈 핵심 근거가 준비되어 있어야 함
- Altibase 우선 정책이 유지되어야 함

### 8.3 정제 단계

#### 단계 A. 파싱 품질 보정
- `???` 노이즈 제거
- 지나치게 짧거나 비어 있는 summary 보완
- title/summary/text 정규화
- 키워드 보강

#### 단계 B. 리뷰 가능성 분류
- 각 규칙에 `reviewability` 부여
- 예:
  - `ALTI-MEM-007`: `auto`
  - `ALTI-PRE-004`: `auto`
  - `ALTI-NAE-001`: `semi_auto`
  - 추상적인 설계 원칙: `reference_only`

#### 단계 C. 적용 단위 분류
- `line`
- `hunk`
- `file`
- `pr`

#### 단계 D. 봇용 문구 생성 정보 추가
- 기본 코멘트 템플릿
- 고치기 힌트
- false positive 리스크

#### 단계 E. 임베딩 교체
- 테스트 환경: 현재 해시 임베딩 유지 가능
- 운영 환경: 실제 임베딩 provider 추가
- provider 인터페이스를 도입하여 교체 가능하게 구현

### 8.4 구현 파일

추가 또는 수정 대상:

- `app/models.py`
- `app/ingest/build_records.py`
- `app/ingest/chroma_store.py`
- `app/retrieve/embeddings.py`
- `data/source_priority.json`
- `data/conflict_rules.json`
- 신규:
  - `data/reviewability_rules.json`
  - `data/comment_templates.json`
  - `data/trigger_patterns.json`

## 9. Git PR 리뷰 시스템 설계

### 9.1 서버 구성

#### Git 저장소
- 경로: `/srv/git/repos`
- 포맷: bare repo
- 접근: OpenSSH + `git-shell`

#### 애플리케이션
- FastAPI
- Jinja2 템플릿 기반 웹 UI
- HTMX 사용 가능

### 9.2 최소 기능

#### 저장소 관리
- 저장소 생성
- 저장소 목록 조회
- 기본 브랜치 표시

#### PR 기능
- PR 생성
- PR 목록 조회
- PR 상세 조회
- base/head branch 비교
- changed files 목록
- unified diff 보기

#### 리뷰 기능
- summary comment
- inline comment
- comment thread
- approve / request changes / comment

#### 봇 기능
- PR 생성 시 자동 리뷰
- 새 commit push 시 재리뷰
- 수동 "다음 5개 보기" 실행 버튼

### 9.3 API 설계

#### 저장소
- `POST /api/repos`
- `GET /api/repos`
- `GET /api/repos/{repo_id}`

#### PR
- `POST /api/pull-requests`
- `GET /api/pull-requests`
- `GET /api/pull-requests/{pr_id}`
- `GET /api/pull-requests/{pr_id}/diff`

#### 댓글
- `POST /api/pull-requests/{pr_id}/comments`
- `GET /api/pull-requests/{pr_id}/comments`

#### 봇
- `POST /api/pull-requests/{pr_id}/bot/review`
- `POST /api/pull-requests/{pr_id}/bot/next-batch`
- `GET /api/pull-requests/{pr_id}/bot/state`

### 9.4 구현 모듈

신규 디렉터리:

- `app/db/`
- `app/git/`
- `app/pr/`
- `app/web/`
- `app/bot/`
- `app/providers/`
- `app/jobs/`

예상 파일:

- `app/db/models.py`
- `app/db/session.py`
- `app/git/repository_service.py`
- `app/git/diff_service.py`
- `app/pr/service.py`
- `app/pr/router.py`
- `app/web/routes.py`
- `app/web/templates/...`
- `app/bot/review_runner.py`
- `app/bot/finding_ranker.py`
- `app/bot/publisher.py`
- `app/providers/llm_base.py`
- `app/providers/openai_provider.py`
- `app/jobs/queue.py`

## 10. 리뷰 봇 설계

### 10.1 봇의 역할

봇은 아래 책임만 가진다.

1. PR diff 수집
2. 리뷰 대상 파일 필터링
3. 코드 패턴 추출
4. 벡터DB 규칙 검색
5. LLM으로 finding 생성
6. finding 랭킹 및 중복 제거
7. 상위 5개 게시
8. 재실행 시 해결 여부 판정

### 10.2 리뷰 파이프라인

1. `review_run` 생성
2. PR diff 로딩
3. 대상 파일 필터링 (`.c`, `.cc`, `.cpp`, `.h`, `.hpp`)
4. 파일/헝크 단위 분석
5. 패턴 추출
6. 벡터DB 후보 규칙 검색
7. 후보 규칙 + 코드 조각으로 LLM 호출
8. finding 생성
9. fingerprint 생성
10. 기존 finding과 dedupe
11. 점수화
12. 아직 게시되지 않은 상위 5개 선택
13. 댓글 게시
14. 게시 이력 저장

### 10.3 finding fingerprint 규칙

fingerprint는 다음 값을 기준으로 생성한다.

- `pull_request_id`
- `file_path`
- `normalized_line_no`
- `rule_no`
- `issue_signature`

같은 문제가 같은 위치에서 반복되면 중복 게시하지 않는다.

### 10.4 "5개씩만 보여주기" 정책

지인 시스템의 동작을 그대로 재현하기 위해 다음 정책을 적용한다.

1. 전체 finding은 모두 계산한다.
2. 게시는 상위 5개만 한다.
3. 다음 리뷰 런에서는 다음 순위를 게시한다.
4. 이미 게시된 finding은 중복 게시하지 않는다.
5. 코드 수정으로 위치가 사라지거나 조건이 해소되면 resolved 처리한다.

### 10.5 봇 코멘트 형식

각 코멘트는 다음 구조를 기본으로 한다.

1. 문제 요약
2. 왜 문제인지
3. 관련 규칙
4. 권장 수정 방향
5. 필요 시 짧은 예시

예시:

```text
[봇 리뷰] `free()` 이후 포인터를 즉시 NULL로 재설정하지 않고 있습니다.

- 이유: 해제 후 재사용 또는 이중 해제 위험을 줄이기 위해 Altibase 메모리 규칙은 즉시 NULL 대입을 요구합니다.
- 관련 규칙: ALTI-MEM-007
- 권장 방향: `free(ptr); ptr = NULL;` 형태로 정리하세요.
```

## 11. Codex / LLM 연동 설계

### 11.1 기본 원칙

LLM provider는 추상화한다.

- `LLMReviewProvider` 인터페이스 정의
- 운영 정책에 따라 provider 교체 가능

### 11.2 1차 구현

1차 구현은 두 provider를 지원하도록 설계한다.

1. `OpenAI/Codex provider`
2. `Stub provider`

`Stub provider`는 테스트와 내부 개발용이며, 실제 운영에서 외부 전송이 불가한 경우
추후 로컬 모델 provider를 추가한다.

### 11.3 LLM 입력

LLM에는 아래만 전달한다.

- 변경된 코드 조각
- 파일 경로
- 주변 헝크 정보
- 검색된 상위 규칙
- 내부 우선순위 정책
- 응답 스키마

PR 전체 소스 전체를 통째로 보내지 않는다.

### 11.4 LLM 출력

LLM 출력은 구조화 JSON으로 받는다.

- `title`
- `summary`
- `severity`
- `confidence`
- `rule_no`
- `line_no`
- `suggested_fix`
- `should_publish`

## 12. 구현 단계

### 단계 0. 설계 및 기준선 고정

목표:
- 현재 엔진 상태를 고정하고 새로운 아키텍처 문서화

작업:
- 본 문서 작성
- 기존 엔진의 public contract 고정
- vector DB 현황 평가 결과를 별도 체크리스트로 관리

완료 기준:
- 구현 순서와 파일 구조가 문서에 확정되어 있음

### 단계 1. 운영 DB 및 공통 인프라

목표:
- Postgres, Redis, SQLAlchemy/Alembic, 설정 체계 추가

작업:
- `app/db/` 추가
- 세션/모델/마이그레이션 추가
- `docker-compose.yml` 확장
- health check 추가

완료 기준:
- `docker compose up`으로 web/postgres/redis/chroma가 실행됨

### 단계 2. Git 저장소 관리와 PR 데이터 모델

목표:
- bare repo 기반 저장소 등록 및 PR 생성 가능

작업:
- repo create/register API
- branch/commit/diff 조회 로직
- PR create/list/detail API
- PR 테이블 저장

완료 기준:
- 로컬에서 bare repo를 등록하고 base/head 기준 PR 생성 가능

### 단계 3. 웹 UI

목표:
- 사람이 실제로 사용할 수 있는 최소 UI 제공

작업:
- 로그인 화면
- 저장소 목록
- PR 목록
- PR 상세
- diff 뷰
- 댓글 UI

완료 기준:
- 브라우저에서 PR 생성과 diff 확인 가능

### 단계 4. 벡터DB 정제 1차

목표:
- 현재 규칙셋을 봇 게시용 active dataset으로 재구성

작업:
- `reviewability` 분류 추가
- `comment_template`, `fix_guidance` 추가
- active/reference/excluded 컬렉션 분리
- 파싱 노이즈 제거

완료 기준:
- active dataset은 자동 리뷰 가능한 규칙 중심으로 축소되어 있음

### 단계 5. 리뷰 엔진 서비스화

목표:
- 현재 CLI 중심 엔진을 PR 런너가 호출 가능한 서비스 계층으로 정리

작업:
- 파일/헝크 입력 API 정리
- result schema 고정
- engine wrapper 추가

완료 기준:
- PR 런너에서 파일/헝크 단위로 엔진 호출 가능

### 단계 6. 리뷰 봇 1차

목표:
- PR 생성/업데이트 시 자동 리뷰 실행

작업:
- review run 생성
- diff 파일 필터링
- finding 생성 및 저장
- 중복 제거
- top 5 게시

완료 기준:
- PR 하나에 대해 봇이 자동으로 5개 코멘트를 게시함

### 단계 7. LLM provider 연동

목표:
- 규칙 검색 결과를 실제 코멘트 문장으로 변환

작업:
- provider 인터페이스
- OpenAI/Codex provider
- stub provider
- structured output parser

완료 기준:
- 룰 번호 나열이 아니라 자연어 코멘트가 게시됨

### 단계 8. 재리뷰와 배치 정책

목표:
- 수정 후 재실행 시 남은 문제만 다음 5개 게시

작업:
- finding fingerprint
- resolved 판정
- batch state 관리
- "다음 5개" 수동/자동 정책

완료 기준:
- 같은 문제를 중복 게시하지 않음

### 단계 9. 운영 품질

목표:
- 파일럿 사용 가능한 수준으로 안정화

작업:
- audit log
- 에러 처리
- retry
- timeout
- admin 화면
- seed 데이터

완료 기준:
- 내부 파일럿 사용자 1팀이 실제로 사용 가능

## 13. 테스트 전략

### 13.1 단위 테스트

- 파서
- 충돌 해소
- 벡터 레코드 생성
- diff 분석
- finding dedupe
- batch 5 정책
- 댓글 게시 포맷

### 13.2 통합 테스트

- bare repo 생성
- branch push
- PR 생성
- diff 조회
- bot review run
- finding 게시
- 수정 후 재리뷰

### 13.3 E2E 테스트

시나리오:

1. 저장소 생성
2. base branch 준비
3. feature branch push
4. PR 생성
5. 봇 리뷰 실행
6. 첫 5개 코멘트 확인
7. 코드 수정 후 다시 push
8. 다음 5개가 게시되는지 확인

## 14. 디렉터리 구조 목표

```text
docs/
ops/
review-engine/
  app/
  data/
  examples/
  tests/
  pyproject.toml
review-platform/
  app/
  tests/
  pyproject.toml
review-bot/
  app/
  tests/
  pyproject.toml
```

## 15. 구현 순서에서 지켜야 할 원칙

1. 먼저 PR 시스템의 최소 기능을 만든다.
2. 그 위에 리뷰 엔진을 붙인다.
3. 그 다음에 LLM provider를 붙인다.
4. 마지막에 UX를 다듬는다.

즉, 순서는 다음과 같다.

1. 저장소/PR/댓글 데이터 모델
2. Git diff 수집
3. 벡터DB 정제
4. finding 생성 파이프라인
5. top 5 게시
6. LLM 고도화

## 16. 작업 체크리스트

### 즉시 시작할 항목

- [ ] Postgres/Redis 추가
- [ ] DB 모델 설계 및 migration 추가
- [ ] bare repo 서비스 추가
- [ ] PR CRUD API 추가
- [ ] diff service 추가
- [ ] bot state 테이블 추가
- [ ] reviewability 분류 데이터 추가
- [ ] comment template 스키마 추가
- [ ] active/reference/excluded 컬렉션 분리
- [ ] review runner 추가
- [ ] finding fingerprint 추가
- [ ] top 5 게시 정책 구현

### 이후 항목

- [ ] UI 템플릿 추가
- [ ] LLM provider 연동
- [ ] 관리자 페이지
- [ ] 운영 로그 및 retry 정책

## 17. 수용 기준

다음 조건을 만족하면 MVP 완성으로 본다.

1. 개발자가 사내 Git 저장소에 push 할 수 있다.
2. 웹에서 PR을 만들 수 있다.
3. PR diff를 볼 수 있다.
4. 봇이 PR에 자동 코멘트를 남긴다.
5. 한 번에 5개만 게시한다.
6. 다시 push 하면 해결된 항목을 제외한 다음 5개를 게시한다.
7. Altibase 규칙이 C++ Core Guidelines보다 우선한다.
8. 벡터DB는 active/reference/excluded로 구분된다.
9. 테스트로 기본 흐름이 재현된다.

## 18. 구현 시작 순서

실제 구현은 아래 순서로 진행한다.

1. `review-engine/` 경계 고정
2. `review-platform/` 생성
3. `review-bot/` 생성
4. `ops/` compose 확장
5. bare repo + PR CRUD
6. diff service
7. vector DB 정제 스키마 확장
8. review runner
9. finding 저장/게시
10. top 5 정책
11. UI
12. LLM provider

이 순서를 바꾸지 않는다. 먼저 PR 시스템 뼈대를 만들고, 그 위에 봇을 얹는다.
