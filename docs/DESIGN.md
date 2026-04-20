# Altibase Review System — 종합 설계 문서

> 버전: 1.0  
> 작성일: 2026-04-20  
> 상태: 설계 확정 (구현 진행 중)  
> 대상 독자: 개발자, 아키텍트, 운영팀

---

## 목차

1. [문서 목적 및 범위](#1-문서-목적-및-범위)
2. [시스템 목표 및 설계 원칙](#2-시스템-목표-및-설계-원칙)
3. [전체 아키텍처](#3-전체-아키텍처)
4. [review-engine 상세 설계](#4-review-engine-상세-설계)
5. [review-bot 상세 설계](#5-review-bot-상세-설계)
6. [LLM 프로바이더 설계](#6-llm-프로바이더-설계)
7. [데이터 모델](#7-데이터-모델)
8. [API 명세](#8-api-명세)
9. [리뷰 품질 제어](#9-리뷰-품질-제어)
10. [운영 설계](#10-운영-설계)
11. [보안 설계](#11-보안-설계)
12. [테스트 전략](#12-테스트-전략)
13. [구현 로드맵](#13-구현-로드맵)
14. [미결 설계 이슈](#14-미결-설계-이슈)

---

## 1. 문서 목적 및 범위

### 1.1 목적

본 문서는 Altibase C++ 코드 자동 리뷰 시스템의 **전체 설계 명세**를 정의한다. 개발자가 구현 결정을 내릴 때 참조하는 단일 진실 공급원(Single Source of Truth)으로 기능한다.

### 1.2 범위

| 포함 | 제외 |
|------|------|
| 시스템 아키텍처 및 컴포넌트 경계 | GitLab 서버 내부 설정 |
| 데이터 모델 및 상태 기계 | C++ Core Guidelines 원문 |
| API 계약 (내부 서비스 간) | Altibase 코딩 컨벤션 원문 |
| LLM 프롬프트 설계 | CI/CD 파이프라인 구성 |
| 품질 제어 메커니즘 | 인프라 프로비저닝 |
| 운영 및 모니터링 요구사항 | |
| 보안 설계 | |
| 테스트 전략 | |

### 1.3 관련 문서

| 문서 | 내용 |
|------|------|
| `docs/REVIEW_BOT_ANALYSIS_REPORT.md` | 현재 시스템 문제점 및 산업계 비교 분석 |
| `docs/API_CONTRACTS.md` | 외부 시스템 어댑터 계약 |
| `docs/WORKSPACE_SPLIT_ARCHITECTURE.md` | 서비스 경계 및 데이터 소유권 |
| `docs/OPERATIONS_RUNBOOK.md` | 운영 절차 |
| `CODING_CONVENTION.md` | Altibase C++ 코딩 컨벤션 원문 |

---

## 2. 시스템 목표 및 설계 원칙

### 2.1 시스템 목표

**1순위 목표 — 코드 품질 향상**
- Altibase C++ 코딩 컨벤션 준수를 자동으로 검증한다
- 개발자가 리뷰 요청 없이 즉시 피드백을 받는다
- 리뷰어의 반복 지적 부담을 줄인다

**2순위 목표 — 리뷰 신뢰성**
- 오탐(false positive)률을 15% 이하로 유지한다
- 모든 코멘트는 실제 코드 위치를 인용한다
- 불확실한 경우 게시하지 않는다 (`should_publish=false`)

**3순위 목표 — 운영 안정성**
- GitLab API 장애 시 자체 복구한다
- review-engine 장애 시 서킷 브레이커로 격리한다
- 모든 실패를 추적하고 재처리 가능하게 한다

### 2.2 설계 원칙

```
원칙 1: Altibase 규칙 우선 (Altibase-First)
  └─ 내부 컨벤션이 C++ Core Guidelines보다 항상 우선한다
  └─ 규칙 충돌 시 Altibase 규칙이 active, C++ 규칙이 excluded

원칙 2: 확신 없으면 침묵 (Silence over Noise)
  └─ should_publish=false로 필터링된 것은 게시하지 않는다
  └─ 낮은 score_final 발견은 suppressed 처리한다
  └─ 중복 코멘트는 절대 게시하지 않는다

원칙 3: 증거 기반 코멘트 (Evidence-Backed)
  └─ 모든 코멘트는 file_path + line_no를 포함한다
  └─ LLM 주장은 실제 change_snippet 내용에 근거한다
  └─ 추론이 아닌 관찰로 서술한다

원칙 4: 피드백 학습 (Feedback-Driven)
  └─ 개발자가 resolve한 스레드는 긍정 신호로 기록한다
  └─ 반박 댓글이 많은 규칙의 가중치를 낮춘다
  └─ 리뷰봇은 사용할수록 정확해진다

원칙 5: 운영 투명성 (Observable by Default)
  └─ 모든 결정을 DB에 기록한다 (FindingDecision.suppression_reason)
  └─ 실패한 게시는 DeadLetterRecord로 추적한다
  └─ 메트릭과 로그로 상태를 언제나 파악할 수 있다
```

### 2.3 비기능 요구사항

| 항목 | 목표값 | 측정 방법 |
|------|--------|-----------|
| Detect 지연 | < 60초 (파일 10개 기준) | p95 latency |
| Publish 지연 | < 30초 (배치 10개 기준) | p95 latency |
| 오탐률 | < 15% | 월별 resolve/suppress 비율 |
| 가용성 | > 99% (업무시간 기준) | 5분 단위 health check |
| 중복 코멘트 | 0건 | body_hash 중복 모니터링 |

---

## 3. 전체 아키텍처

### 3.1 서비스 구성

```
┌─────────────────────────────────────────────────────────────────┐
│                     외부 Git 시스템                              │
│                   (GitLab / Gerrit)                             │
└────────────────────────┬────────────────────────────────────────┘
                         │ Webhook (MR 이벤트)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     review-bot-api                              │
│  FastAPI + uvicorn · 포트 18081                                 │
│  ┌─────────────────┐  ┌──────────────────┐                     │
│  │ Webhook Handler │  │  Internal API    │                     │
│  │ /webhooks/*     │  │ /internal/review │                     │
│  └────────┬────────┘  └──────────────────┘                     │
└───────────┼─────────────────────────────────────────────────────┘
            │ enqueue
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Redis                                    │
│  review-detect · review-publish · review-sync                   │
└───────────┬─────────────────────────────────────────────────────┘
            │ consume
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    review-bot-worker                            │
│  RQ Worker · 3 큐 처리                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Detect Phase │  │ Publish Phase│  │   Sync Phase       │   │
│  │ (diff 분석)  │  │ (코멘트 게시)│  │ (스레드 동기화)    │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────────────┘   │
└─────────┼────────────────┼────────────────────────────────────┘
          │                │
    ┌─────┘    ┌───────────┘
    │          │
    ▼          ▼
┌──────────────────┐   ┌─────────────────────────────────────────┐
│  review-engine   │   │           PostgreSQL                    │
│  포트 18082      │   │  ReviewRequest, ReviewRun,              │
│                  │   │  FindingEvidence, FindingDecision,      │
│  ┌────────────┐  │   │  PublicationState, ThreadSyncState,     │
│  │ FastAPI    │  │   │  FeedbackEvent, DeadLetterRecord        │
│  │ /review/*  │  │   └─────────────────────────────────────────┘
│  └────────────┘  │
│  ┌────────────┐  │
│  │  ChromaDB  │  │   ┌─────────────────────────────────────────┐
│  │  벡터 DB   │  │   │       LLM Provider (OpenAI)            │
│  └────────────┘  │   │  gpt-4o 또는 claude-sonnet-4-6         │
└──────────────────┘   └─────────────────────────────────────────┘
```

### 3.2 서비스 책임 분담

| 서비스 | 책임 | 데이터 소유 |
|--------|------|------------|
| **review-engine** | 규칙 파싱, 벡터 검색, 패턴 추출, 규칙 반환 | ChromaDB, 규칙 JSON |
| **review-bot-api** | Webhook 수신, 검증, ReviewRun 생성, 큐 삽입 | - |
| **review-bot-worker** | 3단계 파이프라인 실행, GitLab API 호출, LLM 호출 | PostgreSQL |
| **PostgreSQL** | 영속 상태 저장 | Finding 생명주기 전체 |
| **Redis** | 비동기 작업 큐 | 임시 job 상태 |
| **ChromaDB** | 규칙 벡터 인덱스 | 임베딩 + 메타데이터 |

### 3.3 컨테이너 포트 매핑

| 컨테이너 | 내부 포트 | 호스트 포트 | 역할 |
|----------|-----------|-------------|------|
| postgres | 5432 | 15432 | 메인 DB |
| redis | 6379 | 16379 | 큐 |
| chroma | 8000 | 18083 | 벡터 DB |
| review-engine | 8000 | 18082 | 엔진 API |
| review-platform | 18080 | 18080 | 로컬 테스트 플랫폼 |
| review-bot-api | 18081 | 18081 | 봇 API |
| nginx | 80 | 18084 | 리버스 프록시 |

---

## 4. review-engine 상세 설계

### 4.1 모듈 구조

```
review_engine/
├── api/
│   └── main.py          # FastAPI 앱, 엔드포인트 정의
├── parser/
│   ├── altibase.py      # CODING_CONVENTION.md 파싱
│   └── cpp_guidelines.py # C++ Core Guidelines HTML 파싱
├── ingest/
│   ├── normalizer.py    # 규칙 레코드 정규화
│   ├── conflict.py      # Altibase vs C++ 충돌 해소
│   └── store.py         # ChromaDB 저장
├── query/
│   ├── patterns.py      # C++ 패턴 추출 (change_analysis)
│   └── builder.py       # 패턴 → 시맨틱 쿼리 변환
└── retrieve/
    ├── search.py         # ChromaDB 벡터 검색
    ├── rerank.py         # 결과 재순위
    └── embeddings.py     # 로컬 임베딩 모델
```

### 4.2 규칙 인제스트 파이프라인

```
CODING_CONVENTION.md          C++ Core Guidelines (HTML)
         │                              │
         ▼                              ▼
  altibase_parser()            cpp_guidelines_parser()
  ├─ rule_no: "A2.5"           ├─ rule_no: "C.31"
  ├─ title: "..."              ├─ title: "..."
  ├─ body: "..."               ├─ body: "..."
  └─ authority: "altibase"     └─ authority: "cpp"
         │                              │
         └──────────┬───────────────────┘
                    ▼
           conflict_resolver()
           ├─ 동일 주제 감지 (임베딩 유사도 > 0.85)
           ├─ Altibase 규칙 → active 컬렉션
           └─ 충돌 C++ 규칙 → excluded 컬렉션
                    │
                    ▼
           ChromaDB 저장
           ├─ 컬렉션: "active_rules"   (검색 대상)
           ├─ 컬렉션: "reference_rules" (참고용)
           └─ 컬렉션: "excluded_rules"  (감사 추적)
```

### 4.3 C++ 패턴 탐지기

엔진이 탐지하는 패턴과 연결 규칙:

| 패턴 ID | 탐지 시그널 | 연결 Altibase 규칙 범주 |
|---------|------------|------------------------|
| `malloc_free` | `malloc(`, `free(`, `calloc(`, `realloc(` | 메모리 관리 |
| `raw_new_delete` | `new `, `delete `, `new[]`, `delete[]` | 메모리 관리 |
| `continue_usage` | `\bcontinue\b` | 흐름 제어 |
| `switch_without_default` | `switch(...)` + `default` 없음 | 흐름 제어 |
| `ide_assert` | `IDE_ASSERT(` | Altibase 에러 처리 |
| `ide_rc_flow` | `IDE_RC`, `IDE_TEST`, `IDE_ERROR` | Altibase 에러 처리 |
| `direct_libc_format` | `printf(`, `sprintf(`, `fprintf(` | 이식성 |
| `portability` | `int `, `long ` (플랫폼 의존 타입) | 이식성 |

### 4.4 검색 및 재순위 알고리즘

```python
# 재순위 가중치 공식
score = (
    engine_similarity_score * 0.40   # ChromaDB 코사인 유사도
  + authority_weight        * 0.25   # altibase=1.0, cpp=0.7
  + severity_weight         * 0.20   # critical=1.0, high=0.8, ...
  + pattern_match_weight    * 0.15   # 탐지된 패턴과 규칙 매핑 일치도
)
```

### 4.5 엔진 API 계약

**POST /review/diff**

```
Request:
{
  "patch": "<unified diff 텍스트>",
  "file_path": "src/foo.cpp",          // 선택
  "file_context": "<전체 파일 내용>",  // 선택, 4000자 이하
  "top_k": 8                           // 반환할 최대 규칙 수
}

Response:
{
  "results": [
    {
      "rule_no": "A2.5",
      "score": 0.87,
      "title": "메모리 직접 할당 금지",
      "summary": "...",
      "category": "memory_management",
      "authority": "altibase",
      "severity": "high",
      "fix_guidance": "...",
      "rule_text": "..."  // 선택적 전문
    }
  ],
  "detected_patterns": ["malloc_free", "raw_new_delete"]
}
```

---

## 5. review-bot 상세 설계

### 5.1 모듈 구조

```
review_bot/
├── api/
│   └── main.py           # FastAPI: webhook + internal endpoints
├── bot/
│   └── review_runner.py  # 3단계 파이프라인 오케스트레이터 (핵심)
├── clients/
│   ├── engine_client.py  # review-engine HTTP 클라이언트
│   └── platform_client.py # review-platform HTTP 클라이언트
├── db/
│   ├── models.py         # SQLAlchemy ORM 모델
│   └── session.py        # DB 세션 팩토리
├── providers/
│   ├── base.py           # Provider 추상 인터페이스
│   ├── openai_provider.py # OpenAI 구현 (기본값)
│   ├── stub_provider.py  # 테스트용 템플릿 기반 구현
│   └── fallback_provider.py # Provider 폴백 체인
├── review_systems/
│   ├── base.py           # ReviewSystemAdapterV2 추상 인터페이스
│   ├── gitlab.py         # GitLab MR 어댑터
│   ├── local_platform.py # 로컬 테스트 플랫폼 어댑터
│   └── factory.py        # 환경변수 기반 어댑터 선택
├── config.py             # Pydantic Settings
├── policy.py             # 경로/규칙별 정책 엔진
├── queueing.py           # Redis RQ 큐 관리
├── schemas.py            # Pydantic 스키마 (API I/O)
└── worker.py             # RQ 워커 진입점
```

### 5.2 리뷰 파이프라인 — 3단계 상세

#### 5.2.1 Detect Phase (탐지 단계)

**목적:** PR diff를 분석해 위반 사항을 데이터베이스에 기록한다.

```
입력: review_run_id

1. MR 메타데이터 조회 (fetch_review_request_meta)
   └─ title, draft, source_branch, target_branch
   └─ base_sha, start_sha, head_sha

2. diff 수신 (fetch_diff)
   └─ GitLab GET /merge_requests/:iid/changes
   └─ incremental 모드: base_sha 기준 필터링

3. 기존 스레드 목록 수신 (list_threads)
   └─ 페이지네이션: per_page=100, 전체 페이지 순회

4. 피드백 이벤트 수집 (collect_feedback)
   └─ 이전 리뷰 코멘트에 대한 resolve/reply 이벤트

5. C++ 파일 필터링
   └─ 확장자: .cpp, .cc, .cxx, .c, .h, .hpp, .hxx

6. 파일별 hunk 분할
   └─ 함수/클래스 경계 인식 분할 (목표)
   └─ 현재: 80줄 단위 고정 분할 (개선 예정)

7. 각 unit에 대해:
   a. engine_client.review_diff(patch, file_path, file_context, top_k)
   b. 각 결과에 대해 FindingEvidence 생성
   c. _build_decision() 호출 → FindingDecision 생성

8. FindingDecision 상태 결정
   └─ eligible: 게시 대상
   └─ suppressed: 정책/점수/피드백에 의해 제외
   └─ suppression_reason에 이유 기록

출력: DB에 FindingEvidence + FindingDecision 레코드 저장
```

#### 5.2.2 Publish Phase (게시 단계)

**목적:** eligible 상태의 Finding을 LLM으로 설명 생성 후 GitLab에 게시한다.

```
입력: review_run_id

1. eligible FindingDecision 조회
   └─ score_final DESC, created_at ASC 정렬

2. 각 Finding에 대해 PublicationCandidate 생성
   a. provider.build_draft() → FindingDraft (title, summary, fix)
   b. render_comment() → 최종 코멘트 본문 (≤ 3800자)
   c. body_hash 계산 (SHA256)
   d. 기존 ThreadSyncState 조회 (fingerprint 기준)
   e. 우선순위 그룹 분류:
      - group 0: 재오픈 후보 (resolved 또는 anchor 변경)
      - group 1: 신규 발견
      - group 2: 리마인더 (기존 오픈 스레드)
      - group 3: 스킵 (동일 body_hash)

3. 배치 선택 (_select_batch_candidates)
   └─ group 3 제외
   └─ (file_path, rule_no) 중복 제거
   └─ rule_family_cap 적용 (기본: 동일 규칙 분류 최대 2개)
   └─ batch_size 제한 (기본: 10개)

4. 각 선택된 후보 게시
   a. 기존 thread + 동일 body_hash → skip
   b. 기존 thread + body 변경 → 기존 스레드에 note 추가
   c. 신규 → 새 inline discussion 생성
   d. PublicationState 기록
   e. ThreadSyncState 생성/업데이트

5. 파이프라인 체크 상태 게시
   └─ success: 부분 또는 전체 게시 성공
   └─ partial: 일부 failed_publication 존재
   └─ failed: 전체 실패

출력: GitLab inline discussion 생성, DB PublicationState 기록
```

#### 5.2.3 Sync Phase (동기화 단계)

**목적:** GitLab의 최신 스레드 상태를 DB와 동기화한다.

```
입력: review_run_id

1. 추적 중인 ThreadSyncState 조회 (sync_status="open")

2. GitLab 현재 스레드 목록 수신

3. 각 추적 스레드에 대해:
   a. GitLab에서 resolved → sync_status="resolved"
   b. GitLab에서 human reply 추가 → FeedbackEvent 기록
   c. anchor(file+line) 변경됨 → sync_status="stale"

4. FindingDecision 상태 업데이트
   └─ resolved 스레드 → Finding.state = "resolved"
   └─ stale 스레드 → Finding.state = "stale"

5. 해소된 Finding 통계 수집 (다음 리뷰 scoring에 활용)

출력: DB ThreadSyncState, FindingDecision 상태 업데이트
```

### 5.3 Finding 상태 기계

```
                    ┌─────────────┐
    webhook 수신 ──▶│  candidate  │
                    └──────┬──────┘
                           │ _build_decision()
              ┌────────────┼────────────────┐
              │ 점수 충분   │ 점수 부족/     │
              │            │ 정책 차단/     │
              │            │ 피드백 무시    │
              ▼            ▼               │
         ┌─────────┐ ┌───────────┐        │
         │eligible │ │suppressed │◀───────┘
         └────┬────┘ └───────────┘
              │ publish phase
    ┌─────────┼─────────────────────────┐
    │         │                         │
    ▼         ▼                         ▼
┌──────────┐ ┌──────────────────┐ ┌──────────────┐
│published │ │failed_publication│ │  suppressed  │
│          │ │(GitLab API 실패) │ │(동일 body)   │
└────┬─────┘ └──────────────────┘ └──────────────┘
     │ sync phase
┌────┴──────────────────────┐
│                           │
▼                           ▼
┌──────────┐            ┌────────┐
│ resolved │            │ stale  │
│(개발자   │            │(anchor │
│ resolve) │            │ 변경)  │
└──────────┘            └────────┘
```

### 5.4 점수 계산 공식

```python
score_final = score_raw - penalties + bonuses

# penalties
weak_anchor_penalty  = 0.10  # target_line_no가 None인 경우
resolved_penalty     = 0.08  # 이전에 resolved 처리된 규칙
reply_penalty        = min(0.05 * human_reply_count, 0.18)
fp_risk_penalty      = {0.0: 0.0, 0.03: "medium", 0.08: "high"}

# bonuses (정책 기반)
policy_bonus         = +0.08  # allowed_rules 목록에 포함

# 게시 최소 임계값
MINIMUM_PUBLISH_SCORE = 0.65  # 이하 → suppressed
```

### 5.5 중복 방지 메커니즘

**레벨 1 — Fingerprint (Finding 수준)**
```python
fingerprint = SHA256(
    f"{review_system}|{project_ref}|{mr_id}"
    f"|{file_path}|{line_no // 64}"  # 64줄 블록 정규화
    f"|{rule_no}|{issue_signature}"
)
```
동일 PR의 동일 위치 + 동일 규칙은 항상 같은 fingerprint → DB 중복 삽입 방지.

**레벨 2 — body_hash (코멘트 수준)**
```python
body_hash = SHA256(render_comment(draft))
```
동일 내용이 이미 GitLab에 게시됐으면 재게시하지 않음.

**레벨 3 — publication_key (배치 수준)**
```python
publication_key = (file_path, line_no, title)
```
단일 배치 내 동일 위치+제목 중복 제거.

### 5.6 GitLab 어댑터

#### Webhook 처리 흐름

```
POST /webhooks/gitlab/merge-request
    │
    ├─ X-Gitlab-Token 검증
    ├─ object_kind == "note" 확인
    ├─ @review-bot 멘션 확인
    ├─ 봇 자신의 코멘트 필터링 (author.name != BOT_AUTHOR_NAME)
    │
    ├─ ReviewRequest 조회/생성 (upsert)
    ├─ ReviewRun 생성 (trigger="gitlab:note_mention", mode="manual")
    └─ Redis review-detect 큐 삽입
```

#### Inline Comment 위치 지정

```python
position = {
    "position_type": "text",
    "base_sha":  diff_refs.base_sha,
    "start_sha": diff_refs.start_sha,
    "head_sha":  diff_refs.head_sha,
    "new_path":  file_path,
    "new_line":  target_line_no,    # added 줄 기준
}
```

GitLab 422 (라인 위치 오류) 수신 시 → `failed_publication` (재처리 불가로 표시).

#### 오류 분류

| 오류 유형 | 재시도 | 처리 방법 |
|-----------|--------|-----------|
| `gitlab_timeout` | 예 | 지수 백오프 (최대 2회) |
| `gitlab_api_5xx` | 예 | 지수 백오프 |
| `gitlab_api_4xx` | 아니오 | DeadLetterRecord 기록 |
| `inline_anchor` | 아니오 | failed_publication, 무시 |
| `gitlab_transport` | 예 | 즉시 재시도 |

---

## 6. LLM 프로바이더 설계

### 6.1 프로바이더 추상 인터페이스

```python
class ReviewProvider(ABC):
    @abstractmethod
    async def build_draft(
        self,
        evidence: FindingEvidence,
        decision: FindingDecision,
        pr_context: PRContext | None = None,
    ) -> FindingDraft:
        """Finding에 대한 한국어 리뷰 코멘트 초안을 생성한다."""
        ...

@dataclass
class PRContext:
    title: str
    source_branch: str
    target_branch: str
    mr_description: str | None = None

@dataclass
class FindingDraft:
    title: str            # 단문 한국어 제목 (50자 이하)
    summary: str          # 상세 설명 (무엇이, 왜, 어떻게)
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float     # 0.0 ~ 1.0
    line_no: int | None   # 최종 확정 라인 번호
    suggested_fix: str | None  # 수정 제안 (cpp 코드 블록 포함 가능)
    should_publish: bool  # False이면 게시하지 않음
```

### 6.2 OpenAI 프로바이더 — 프롬프트 설계

#### 시스템 프롬프트

```
당신은 Altibase C++ 코드베이스의 선임 리뷰어입니다.

역할:
- 변경된 코드에서 실제로 발생한 문제를 정확히 식별한다
- 문제가 없거나 불확실하면 should_publish=false로 응답한다
- 모든 응답은 자연스러운 한국어로 작성한다

코멘트 작성 원칙:
1. 무엇이 문제인가 (구체적인 코드 위치와 함께)
2. 왜 문제인가 (Altibase 코드베이스에서의 위험성)
3. 어떻게 고치는가 (Altibase 코딩 스타일에 맞는 수정 방법)

금지 사항:
- 규칙 ID나 가이드라인 이름 직접 언급 금지
- 코드에서 실제로 보이지 않는 문제 언급 금지
- 불확실한 내용을 확실한 것처럼 서술 금지
- 50자를 초과하는 제목 금지
```

#### 사용자 프롬프트 템플릿

```
[PR 정보]
제목: {pr_title}
브랜치: {source_branch} → {target_branch}

[검토 파일]
파일: {file_path}
변경 내용:
{change_snippet}

[파일 컨텍스트 (참고용)]
{file_context_summary}

[적용 규칙]
분류: {category}
문제: {rule_title}
설명: {rule_summary}
수정 지침: {fix_guidance}

[위치 정보]
후보 라인 번호: {candidate_line_nos}
확정 라인: {line_no}

위 변경 내용에서 이 규칙이 실제로 위반되고 있는지 분석하고
구조화된 JSON으로 응답하세요.
```

#### 응답 스키마 (Structured Output)

```python
class ReviewDraftPayload(BaseModel):
    title: str = Field(description="50자 이하 한국어 제목")
    summary: str = Field(description="문제-이유-해결 구조의 한국어 설명")
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0)
    line_no: int | None = Field(description="candidate_line_nos 중 하나 또는 None")
    suggested_fix: str | None = Field(description="수정 예시 (cpp 코드 블록 포함 가능)")
    should_publish: bool = Field(default=True, description="False이면 코멘트 게시 안 함")
```

### 6.3 2단계 검증 (Self-Consistency)

오탐률 감소를 위해 LLM 응답 후 자가 검증 단계를 적용한다.

```python
async def build_draft_with_verification(self, evidence, decision, pr_context):
    # 1단계: 초안 생성
    draft = await self._generate_draft(evidence, decision, pr_context)
    
    if not draft.should_publish or draft.confidence < 0.6:
        return draft
    
    # 2단계: 자가 검증 (신뢰도 0.75 이상 고신뢰 케이스에만 생략)
    if draft.confidence < 0.75:
        verified = await self._verify_claim(draft, evidence.change_snippet)
        if not verified:
            draft.should_publish = False
            draft.confidence = max(0.0, draft.confidence - 0.25)
    
    return draft

async def _verify_claim(self, draft: FindingDraft, snippet: str) -> bool:
    """LLM 주장이 실제 코드 내용에 근거하는지 확인한다."""
    prompt = f"""
    다음 코드 리뷰 코멘트가 아래 코드 변경에 실제로 적용되는지만 답하세요.
    코멘트: {draft.summary}
    코드: {snippet}
    JSON 응답: {{"applies": true/false}}
    """
    result = await self._call_llm(prompt)
    return result.get("applies", False)
```

### 6.4 코멘트 렌더링 형식

```markdown
**[봇 리뷰] {title}**

{summary}

{suggested_fix_section}  ← suggested_fix 있을 때만

---
*이 코멘트는 자동 생성됩니다. 문제가 없다면 스레드를 Resolve 해주세요.*
```

- 최대 길이: 3,800자 (GitLab 4,000자 제한 여유)
- 초과 시: `{본문[:3760]}\n\n...(내용이 잘렸습니다. 파일을 직접 확인하세요.)`

### 6.5 프로바이더 설정

| 환경변수 | 기본값 | 설명 |
|----------|--------|------|
| `BOT_PROVIDER` | `openai` | 기본 프로바이더 (`openai` / `stub`) |
| `BOT_FALLBACK_PROVIDER` | `stub` | 기본 프로바이더 실패 시 폴백 |
| `BOT_OPENAI_MODEL` | `gpt-4o` | 사용할 OpenAI 모델 |
| `BOT_OPENAI_TIMEOUT_SECONDS` | `30` | API 호출 타임아웃 |
| `BOT_OPENAI_MAX_RETRIES` | `2` | 재시도 횟수 |
| `OPENAI_API_KEY` | — | OpenAI API 키 (필수) |

---

## 7. 데이터 모델

### 7.1 엔티티 관계도

```
ReviewRequest (1) ──── (N) ReviewRun
                              │
               ┌──────────────┤
               │              │
               ▼              ▼
        FindingEvidence  DeadLetterRecord
               │
               ▼
        FindingDecision (1) ──── (N) PublicationState
               │
               ▼
        ThreadSyncState
               │
               ▼
        FeedbackEvent
```

### 7.2 ReviewRequest

PR/MR 식별 정보를 저장한다. 동일 PR에 여러 ReviewRun이 연결된다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | UUID | PK |
| `review_system` | str(32) | `gitlab`, `gerrit`, `local_platform` |
| `project_ref` | str(255) | `group/project` |
| `review_request_id` | str(128) | GitLab MR IID |
| `title` | str(500) | MR 제목 |
| `draft` | bool | Draft MR 여부 |
| `source_branch` | str(255) | 소스 브랜치 |
| `target_branch` | str(255) | 대상 브랜치 |
| `latest_head_sha` | str(64) | 최신 HEAD 커밋 |
| `latest_base_sha` | str(64) | 최신 base 커밋 |
| `latest_start_sha` | str(64) | 최신 start 커밋 |

유니크 제약: `(review_system, project_ref, review_request_id)`

### 7.3 ReviewRun

단일 리뷰 실행을 추적한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | UUID | PK |
| `review_request_pk` | UUID | FK → ReviewRequest |
| `trigger` | str(64) | `gitlab:note_mention`, `api:manual` 등 |
| `mode` | str(32) | `full`, `incremental`, `manual`, `sync_only` |
| `status` | str(32) | `queued` → `running` → `completed`/`failed` |
| `base_sha` | str(64) | 리뷰 기준 커밋 |
| `head_sha` | str(64) | 리뷰 대상 커밋 |
| `error_category` | str(64) | 실패 분류 |
| `started_at` | datetime | 실행 시작 시각 |
| `completed_at` | datetime | 실행 완료 시각 |

### 7.4 FindingEvidence

엔진이 반환한 원시 결과를 저장한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | UUID | PK |
| `review_run_id` | UUID | FK → ReviewRun |
| `file_path` | str(1000) | 분석된 파일 경로 |
| `patch_digest` | str(128) | 분석된 hunk SHA256 |
| `hunk_header` | str(255) | `@@ -12,7 +12,9 @@` 형식 |
| `candidate_line_nos` | JSON(list[int]) | 추천 라인 번호 목록 |
| `matched_patterns` | JSON(list[str]) | 탐지된 패턴 ID 목록 |
| `change_snippet` | Text | 분석된 diff 텍스트 |
| `raw_engine_payload` | JSON | 엔진 원시 응답 전체 |

### 7.5 FindingDecision

처리된 Finding의 게시 여부와 스코어를 저장한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | UUID | PK |
| `evidence_id` | UUID | FK → FindingEvidence |
| `fingerprint` | str(255) | 중복 방지 식별자 |
| `file_path` | str(1000) | 파일 경로 |
| `line_no` | int | 최종 라인 번호 |
| `rule_no` | str(128) | 규칙 번호 |
| `source_family` | str(64) | 규칙 분류 (배치 캡 적용 단위) |
| `severity` | str(20) | `low`/`medium`/`high`/`critical` |
| `confidence` | float | 0.0 ~ 1.0 |
| `score_raw` | float | 엔진 원점수 |
| `score_final` | float | 페널티 적용 후 최종점수 |
| `anchor_signature` | str(255) | `SHA1(file|line|hunk_header)` |
| `anchor_payload` | JSON | GitLab position 객체 |
| `state` | str(32) | 상태 기계 참조 |
| `suppression_reason` | str(128) | suppressed 이유 |
| `title` | str(300) | 한국어 제목 |
| `summary` | Text | 한국어 설명 |
| `suggested_fix` | Text | 한국어 수정 제안 |

**state 허용값:** `candidate`, `eligible`, `suppressed`, `published`, `failed_publication`, `resolved`, `stale`

### 7.6 ThreadSyncState

GitLab discussion 스레드 추적 상태.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `adapter_thread_ref` | str(255) | GitLab discussion ID (유니크) |
| `finding_fingerprint` | str(255) | 연결된 Finding fingerprint |
| `anchor_signature` | str(255) | 현재 anchor 서명 |
| `body_hash` | str(128) | 현재 코멘트 본문 해시 |
| `sync_status` | str(32) | `open`, `resolved`, `stale` |
| `last_seen_head_sha` | str(64) | 마지막 동기화 시점 HEAD |

### 7.7 FeedbackEvent

개발자의 피드백을 기록한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `event_key` | str(255) | 중복 방지 유니크 키 |
| `adapter_thread_ref` | str(255) | GitLab discussion ID |
| `event_type` | str(64) | `resolved`, `reopened`, `human_reply`, `bot_command` |
| `actor_type` | str(32) | `human`, `bot` |
| `payload` | JSON | 원시 이벤트 데이터 |

---

## 8. API 명세

### 8.1 review-bot API

**기본 URL:** `http://localhost:18081`

#### POST /webhooks/gitlab/merge-request
GitLab MR Webhook 수신 진입점.

```
Headers:
  X-Gitlab-Token: {GITLAB_WEBHOOK_SECRET}
  Content-Type: application/json

Body: GitLab Webhook Payload (object_kind, project, object_attributes, etc.)

Response 200:
{
  "accepted": true,
  "review_run_id": "uuid",
  "message": "review queued"
}

Response 400: Webhook 검증 실패
Response 422: 처리할 수 없는 이벤트 유형
Response 503: Redis 큐 삽입 실패
```

#### POST /internal/review/runs
수동 리뷰 실행 트리거.

```
Body:
{
  "review_system": "gitlab",
  "project_ref": "group/project",
  "review_request_id": "42",
  "trigger": "api:manual",
  "mode": "full"
}

Response 202:
{
  "review_run_id": "uuid",
  "status": "queued"
}
```

#### GET /internal/review/requests/{system}/{project}/{mr_id}
ReviewRequest 상태 조회.

```
Response 200:
{
  "review_request_id": "uuid",
  "latest_run": {
    "id": "uuid",
    "status": "completed",
    "published_count": 5,
    "suppressed_count": 12,
    "failed_count": 0
  },
  "open_threads": 5
}
```

#### GET /health
헬스 체크.

```
Response 200: {"status": "ok", "db": "ok", "redis": "ok"}
Response 503: {"status": "degraded", "db": "ok", "redis": "error"}
```

### 8.2 review-engine API

**기본 URL:** `http://localhost:18082`

#### POST /review/diff

```
Body:
{
  "patch": "unified diff text",
  "file_path": "src/AltibaseDB.cpp",
  "file_context": "// 전체 파일 앞부분 4000자",
  "top_k": 8
}

Response 200:
{
  "results": [
    {
      "rule_no": "A2.5",
      "score": 0.87,
      "title": "메모리 직접 할당 금지",
      "summary": "malloc/free 대신 스마트 포인터를 사용하세요",
      "category": "memory_management",
      "authority": "altibase",
      "severity": "high",
      "fix_guidance": "std::vector 또는 std::unique_ptr 사용 권장",
      "rule_text": "규칙 전문..."
    }
  ],
  "detected_patterns": ["malloc_free"]
}
```

#### GET /rule/{rule_no}

```
Response 200:
{
  "rule_no": "A2.5",
  "title": "...",
  "body": "...",
  "authority": "altibase",
  "collection": "active",
  "severity": "high",
  "category": "memory_management"
}
```

---

## 9. 리뷰 품질 제어

### 9.1 오탐(False Positive) 감소 전략

**전략 1 — 신뢰도 임계값**
```
confidence < 0.65  → suppressed (게시 안 함)
should_publish = false → 항상 suppressed
score_final < 0.65 → suppressed
```

**전략 2 — LLM 자가 검증**
```
초안 생성 후 confidence < 0.75이면
  → 검증 LLM 호출로 주장이 코드에 실제 근거하는지 확인
  → 검증 실패 시 should_publish = false
```

**전략 3 — 피드백 페널티 누적**
```
human_reply_count >= 2 && score_final < 0.72 → suppressed
resolved_by_human 이력 있음 → resolved_penalty 적용
```

**전략 4 — 배치 다양성 캡**
```
동일 rule_family에서 최대 rule_family_cap (기본 2)개만 게시
→ 동일 유형 문제 반복 스팸 방지
```

**전략 5 — 파일 컨텍스트 제공**
```
review-engine 호출 시 file_context (파일 전체 앞부분) 포함
→ LLM이 함수/클래스 전체 맥락을 보고 판단
→ 단순 패턴 매칭보다 정확한 판단 가능
```

### 9.2 배치 정책

```python
# policy.py - 경로별 정책 예시
{
  "path_policies": [
    {
      "pattern": "src/core/**",
      "score_adjustment": +0.05,  # 핵심 코드 → 더 엄격
      "promote_rules": ["A2.5", "A3.1"]
    },
    {
      "pattern": "tests/**",
      "score_adjustment": -0.15,  # 테스트 코드 → 관대
      "suppress_rules": ["A2.5"]  # 테스트에서 malloc 허용
    },
    {
      "pattern": "third_party/**",
      "suppress_rules": ["*"]     # 서드파티 → 모두 억제
    }
  ],
  "global_allowed_rules": ["A2.5", "A2.6"],
  "global_suppressed_rules": []
}
```

### 9.3 리뷰 품질 메트릭 (목표값)

| 메트릭 | 목표 | 측정 방법 |
|--------|------|-----------|
| 게시 후 resolve율 | > 40% | resolved / published |
| 오탐 추정율 | < 15% | 명시적 ignore / published |
| 평균 코멘트 신뢰도 | > 0.75 | avg(confidence) of published |
| 규칙별 유용성 점수 | 월별 검토 | resolved / (published per rule) |

---

## 10. 운영 설계

### 10.1 인프라 구성

```yaml
# 프로덕션 구성 (docker-compose 기준)
services:
  postgres:
    image: postgres:16-alpine
    환경변수: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
    볼륨: postgres-data (영속)
    
  redis:
    image: redis:7-alpine
    설정: maxmemory-policy allkeys-lru (큐 오버플로 방지)
    
  chroma:
    image: chromadb/chroma:0.5.5
    환경변수: IS_PERSISTENT=TRUE
    볼륨: chroma-data (영속)
    
  review-engine:
    replicas: 1  # ChromaDB 접근 단일화
    리소스: 2 CPU, 4GB RAM (임베딩 모델 로딩)
    
  review-bot-api:
    replicas: 2  # 수평 확장 가능
    리소스: 0.5 CPU, 512MB RAM
    
  review-bot-worker:
    replicas: 2  # 큐 처리량에 따라 조정
    리소스: 1 CPU, 1GB RAM (LLM 호출 대기)
```

### 10.2 환경변수 전체 목록

#### 필수 환경변수

| 변수 | 설명 |
|------|------|
| `BOT_DATABASE_URL` | PostgreSQL 연결 문자열 |
| `BOT_REDIS_URL` | Redis 연결 문자열 |
| `ENGINE_BASE_URL` | review-engine 내부 URL |
| `OPENAI_API_KEY` | OpenAI API 키 |
| `GITLAB_TOKEN` | GitLab Private Token |
| `GITLAB_WEBHOOK_SECRET` | Webhook 서명 검증 시크릿 |
| `REVIEW_SYSTEM_ADAPTER` | `gitlab` (프로덕션) |
| `REVIEW_SYSTEM_BASE_URL` | GitLab 인스턴스 URL |

#### 선택적 환경변수 (기본값 포함)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `BOT_PROVIDER` | `openai` | LLM 프로바이더 |
| `BOT_OPENAI_MODEL` | `gpt-4o` | 모델명 |
| `BOT_BATCH_SIZE` | `10` | 배치당 최대 게시 수 |
| `BOT_RULE_FAMILY_CAP` | `2` | 동일 규칙 분류 최대 수 |
| `BOT_MINIMUM_PUBLISH_SCORE` | `0.65` | 게시 최소 점수 |
| `BOT_ENGINE_TIMEOUT_SECONDS` | `30` | 엔진 API 타임아웃 |
| `BOT_GITLAB_API_TIMEOUT_SECONDS` | `30` | GitLab API 타임아웃 |
| `BOT_DEAD_LETTER_ENABLED` | `1` | Dead Letter 활성화 |
| `BOT_POLICY_PATH` | — | 정책 JSON 파일 경로 |

### 10.3 모니터링 요구사항

#### 핵심 메트릭 (Prometheus 형식)

```python
# review_bot/metrics.py (구현 필요)

# 카운터
review_runs_total{status="completed|failed", trigger="..."}
findings_published_total{severity="...", rule_family="..."}
findings_suppressed_total{reason="..."}
findings_resolved_total{rule_no="..."}

# 히스토그램
detect_phase_duration_seconds{p50, p95, p99}
publish_phase_duration_seconds{p50, p95, p99}
llm_call_duration_seconds{provider="openai", p95}
engine_call_duration_seconds{p95}

# 게이지
redis_queue_depth{queue="detect|publish|sync"}
open_threads_total{project="..."}
dead_letter_count_total
```

#### 알림 규칙

| 조건 | 심각도 | 조치 |
|------|--------|------|
| `detect_phase_duration_seconds p95 > 120s` | warning | 엔진 성능 점검 |
| `redis_queue_depth{queue="detect"} > 50` | warning | 워커 증설 검토 |
| `review_runs_total{status="failed"} / total > 10%` | critical | 즉시 조사 |
| `dead_letter_count_total 증가율 > 10/hour` | warning | Dead Letter 조사 |
| `llm_call_duration_seconds p95 > 60s` | warning | LLM 타임아웃 조정 |

### 10.4 장애 대응

#### review-engine 장애

```
감지: engine_client HTTP 타임아웃 또는 5xx
처리:
  1. 지수 백오프로 2회 재시도
  2. 재시도 실패 → ReviewRun.status = "failed"
  3. DeadLetterRecord 기록 (replayable=True)
  4. 운영팀 알림

복구:
  1. review-engine 재시작
  2. replayable=True인 DeadLetterRecord 재처리
```

#### GitLab API 장애

```
감지: HTTP 5xx 또는 타임아웃
처리:
  1. 지수 백오프로 2회 재시도
  2. 재시도 실패 → failed_publication 상태
  3. DeadLetterRecord 기록

복구:
  1. 관리자가 수동 재발행 API 호출
  2. POST /internal/review/runs/{id}/publish
```

#### Redis 장애

```
감지: RQ 큐 연결 실패
처리:
  1. Webhook 수신 → 503 반환 (큐 삽입 실패)
  2. 진행 중인 작업 → DeadLetterRecord 기록

복구:
  1. Redis 재시작
  2. 실패한 ReviewRun을 수동으로 재큐잉
```

### 10.5 데이터 보존 정책

| 데이터 | 보존 기간 | 이유 |
|--------|-----------|------|
| ReviewRun (completed) | 90일 | 리뷰 이력 감사 |
| ReviewRun (failed) | 30일 | 디버깅 |
| FindingDecision (published) | 180일 | 품질 분석 |
| FindingDecision (suppressed) | 30일 | 튜닝 참고 |
| FeedbackEvent | 180일 | 피드백 학습 |
| DeadLetterRecord | 14일 | 재처리 창 |
| ThreadSyncState (resolved) | 90일 | 이력 참조 |

---

## 11. 보안 설계

### 11.1 인증 및 권한

**Webhook 인증**
```python
# HMAC-SHA256 또는 고정 토큰 (GitLab 방식)
def verify_webhook(request: Request, secret: str) -> bool:
    token = request.headers.get("X-Gitlab-Token")
    return secrets.compare_digest(token or "", secret)
```

**GitLab API 인증**
```
헤더: PRIVATE-TOKEN: {GITLAB_TOKEN}
토큰 권한 최소화: api, read_api 범위만 요구
토큰 로그 마스킹: 로그에서 토큰 값 제거 필수
```

**내부 서비스 통신**
```
현재: 인증 없음 (내부 Docker 네트워크로 격리)
권장: mTLS 또는 내부 Bearer 토큰 (향후 외부 배포 시)
```

### 11.2 민감 데이터 처리

| 데이터 | 처리 방법 |
|--------|-----------|
| GitLab Token | 환경변수, 로그 마스킹 |
| OpenAI API Key | 환경변수, 로그 마스킹 |
| 코드 스니펫 (DB 저장) | 내부망 한정, 암호화 고려 |
| Webhook Secret | 환경변수 |

### 11.3 입력 검증

```python
# 봇 자신의 코멘트 필터링 (무한 루프 방지)
if payload.object_attributes.author.name == settings.bot_author_name:
    return  # 처리 안 함

# Draft MR 필터링 (선택적)
if review_request.draft and not settings.allow_draft_reviews:
    return

# 파일 크기 제한
if len(patch) > MAX_PATCH_SIZE:
    patch = patch[:MAX_PATCH_SIZE]
```

### 11.4 Rate Limiting (구현 필요)

```python
# Webhook 엔드포인트에 rate limit 적용
@app.post("/webhooks/gitlab/merge-request")
@ratelimit(calls=100, period=60)  # 분당 100회
async def webhook_handler(...):
    ...
```

---

## 12. 테스트 전략

### 12.1 테스트 계층

```
E2E 테스트 (5%)
  └─ 실제 GitLab 인스턴스 + 전체 스택
  └─ 핵심 시나리오만: webhook 수신 → 코멘트 게시

통합 테스트 (25%)
  └─ 실제 PostgreSQL (test DB)
  └─ 실제 Redis (test 큐)
  └─ review-engine mock HTTP 서버
  └─ GitLab API mock HTTP 서버

단위 테스트 (70%)
  └─ 개별 함수/클래스 독립 테스트
  └─ 점수 계산, 중복 제거, 렌더링
```

### 12.2 필수 테스트 시나리오

#### 파이프라인 통합 테스트

```python
# 반드시 검증해야 하는 시나리오

1. test_single_finding_full_pipeline()
   # webhook → detect → publish → GitLab comment 생성

2. test_duplicate_prevention()
   # 동일 PR에 두 번 webhook → 코멘트 중복 없음

3. test_pagination_large_pr()
   # 100개 이상 discussion이 있는 PR에서 정상 동작

4. test_concurrent_runs_same_pr()
   # 동시 webhook 두 개 → 하나만 처리, 하나는 거부

5. test_feedback_suppression()
   # 3회 이상 reply → 다음 리뷰에서 해당 finding suppressed

6. test_engine_timeout_recovery()
   # engine timeout → dead letter 기록 → 수동 재처리

7. test_gitlab_anchor_failure()
   # 라인이 이동된 후 게시 → failed_publication, 재처리 안 함

8. test_comment_body_truncation()
   # 4000자 초과 코멘트 → 3800자로 잘려 게시

9. test_llm_should_not_publish()
   # LLM이 should_publish=false → 게시 안 함

10. test_policy_path_suppression()
    # tests/** 경로 → A2.5 규칙 suppressed
```

#### LLM 프로바이더 테스트

```python
# OpenAI 프로바이더는 반드시 실제 호출 테스트 포함 (integration)
def test_openai_provider_real_call():
    # OPENAI_API_KEY 환경변수 있을 때만 실행
    # 실제 C++ diff로 응답 품질 검증
    # should_publish, confidence, line_no 형식 검증

def test_openai_provider_timeout():
    # 타임아웃 시 fallback_provider 동작 확인

def test_openai_provider_structured_output():
    # 응답이 ReviewDraftPayload 스키마 준수 확인
```

### 12.3 계약 테스트

```python
# review-engine 계약 테스트 (엔진 변경 시 자동 실패)
class TestEngineContract:
    def test_response_has_results_list(self, engine_response):
        assert "results" in engine_response
        
    def test_result_has_required_fields(self, engine_response):
        for r in engine_response["results"]:
            assert "rule_no" in r
            assert "score" in r
            assert "severity" in r
            
    def test_score_in_valid_range(self, engine_response):
        for r in engine_response["results"]:
            assert 0.0 <= r["score"] <= 1.0
```

### 12.4 테스트 픽스처

```python
# 표준 테스트 픽스처 (conftest.py)

@pytest.fixture
def sample_cpp_diff():
    return """
--- a/src/AltibaseDB.cpp
+++ b/src/AltibaseDB.cpp
@@ -65,7 +65,12 @@
 IDE_RC AltibaseDB::executeQuery(const char* sql)
 {
+    char* buffer = (char*)malloc(1024);
+    if (buffer == NULL) {
+        return IDE_FAILURE;
+    }
     // ... 기존 코드
 }
"""

@pytest.fixture  
def mock_engine_response():
    return {
        "results": [{
            "rule_no": "A2.5",
            "score": 0.87,
            "title": "메모리 직접 할당 금지",
            "severity": "high",
            "authority": "altibase",
            "category": "memory_management",
            "fix_guidance": "std::vector 사용 권장",
        }],
        "detected_patterns": ["malloc_free"]
    }
```

---

## 13. 구현 로드맵

### Phase 1 — 안정화 (1~2주)

**목표:** 프로덕션 배포 가능한 안정성 확보

| 작업 | 파일 | 중요도 |
|------|------|--------|
| `BOT_PROVIDER` 기본값을 `openai`로 변경 | `config.py` | 🔴 최우선 (P1-A) |
| GitLab list_threads 페이지네이션 구현 | `gitlab.py` | 🔴 최우선 (P1-C) |
| ReviewRun 동시성 제어 (Advisory Lock) | `review_runner.py` | 🔴 최우선 (P1-B) |
| 코멘트 본문 3800자 트런케이션 | `review_runner.py` | 🟠 높음 (P2-D) |
| 헬스 체크에 Redis 상태 추가 | `api/main.py` | 🟡 중간 |
| DeadLetterRecord TTL 정리 작업 | `worker.py` | 🟡 중간 (P3-C) |

### Phase 2 — 품질 향상 (2~4주)

**목표:** 리뷰 코멘트 정확도 개선

| 작업 | 파일 | 중요도 |
|------|------|--------|
| `file_context` 파라미터 엔진 API 추가 | `engine/api/main.py` | 🔴 최우선 |
| `file_context` 클라이언트 전달 구현 | `engine_client.py` | 🔴 최우선 |
| OpenAI 프롬프트 PR 컨텍스트 포함 | `openai_provider.py` | 🟠 높음 |
| LLM 자가 검증 단계 추가 | `openai_provider.py` | 🟠 높음 |
| 함수 경계 기반 hunk 분할 개선 | `review_runner.py` | 🟡 중간 |
| 동적 top_k 계산 (복잡도 기반) | `engine_client.py` | 🟡 중간 |
| OpenAI 프로바이더 통합 테스트 추가 | `tests/` | 🟡 중간 |

### Phase 3 — 운영 성숙 (1~2개월)

**목표:** 프로덕션 운영 투명성 및 확장성

| 작업 | 파일 | 중요도 |
|------|------|--------|
| Prometheus 메트릭 엔드포인트 | `metrics.py` | 🟠 높음 |
| Circuit Breaker (engine 클라이언트) | `engine_client.py` | 🟠 높음 (P3-4) |
| RAG 기반 저장소 인덱싱 (오탐 60% 감소) | `review_engine/ingest/` | 🟠 높음 (P3-1) |
| 피드백 기반 규칙 가중치 조정 | `policy.py` | 🟡 중간 (P3-3) |
| N+1 피드백 쿼리 최적화 | `review_runner.py` | 🟡 중간 (P3-A) |
| 정책 경로 매칭 캐싱 (O→O(1)) | `policy.py` | 🟡 중간 (P3-B) |
| Rate Limiting (webhook 엔드포인트) | `api/main.py` | 🟡 중간 |
| DeadLetterRecord 보존 정책 시행 | `worker.py` | 🟢 낮음 (P3-C) |

### Phase 4 — 고도화 (3개월+)

**목표:** 업계 선진 리뷰봇 수준 달성

| 작업 | 설명 | 출처 |
|------|------|------|
| 증거 기반 코멘트 강제 | 모든 코멘트에 `file:line` 코드 인용 + "근거:" 절 추가 (CodeRabbit 수준) | P4-1 |
| 다중 특화 에이전트 | 메모리, 에러처리, 명명, 이식성별 독립 에이전트 병렬 실행 | P3-2 |
| Auto-fix 제안 | 확실한 케이스(confidence>0.9)에 한해 GitLab suggestion 블록 게시 | P4-3 |
| PR 요약 생성 | diff → 한국어 변경 요약 자동 생성 (무엇이/왜/집중점) | P4-2 |
| 규칙 유효성 대시보드 | 규칙별 해소율, 오탐 추정율 시각화 | - |

---

## 14. 미결 설계 이슈

다음 사항은 설계 결정이 필요하다.

| # | 이슈 | 옵션 | 권장 |
|---|------|------|------|
| 1 | LLM 모델 선택 | `gpt-4o` vs `claude-sonnet-4-6` | `gpt-4o` (Structured Output 안정적) |
| 2 | 자가 검증 LLM 분리 | 동일 모델 vs 경량 모델 | 경량 모델 (`gpt-4o-mini`) |
| 3 | 함수 경계 분할 방법 | Tree-sitter vs 정규식 | Tree-sitter (C++ AST 파싱) |
| 4 | 저장소 인덱싱 시점 | 매 push vs 야간 배치 | 야간 배치 (비용 효율) |
| 5 | 다중 GitLab 프로젝트 지원 | 단일 토큰 vs 프로젝트별 토큰 | 프로젝트별 토큰 |
| 6 | 코멘트 언어 | 항상 한국어 vs 설정 가능 | 항상 한국어 (내부 팀 전용) |
| 7 | 드래프트 MR 처리 | 항상 무시 vs 설정 가능 | 설정 가능 (`BOT_REVIEW_DRAFT_MRS`) |

---

*본 문서는 구현 진행에 따라 지속 업데이트된다.*  
*구현 현황: `IMPLEMENTATION_PROGRESS.md` 참조*  
*운영 절차: `docs/OPERATIONS_RUNBOOK.md` 참조*
