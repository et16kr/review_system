# Altibase Review Bot — 심층 분석 및 개선 보고서

> 작성일: 2026-04-20  
> 분석 대상: `/home/et16/work/review_system` (branch: `new_version`)  
> 분석 범위: 코드베이스 전수 검토 + 산업계 주요 리뷰봇 조사 + 학술 연구 동향

---

## 목차

1. [Executive Summary](#1-executive-summary)
2. [현재 시스템 아키텍처 분석](#2-현재-시스템-아키텍처-분석)
3. [현재 시스템의 핵심 문제점](#3-현재-시스템의-핵심-문제점)
4. [산업계 주요 리뷰봇 비교](#4-산업계-주요-리뷰봇-비교)
5. [방향성 평가: 현재 접근법은 맞는가?](#5-방향성-평가-현재-접근법은-맞는가)
6. [개선 로드맵](#6-개선-로드맵)
7. [결론](#7-결론)

---

## 1. Executive Summary

본 리뷰 봇은 **Altibase C++ 코딩 컨벤션을 기반으로 한 자동 코드 리뷰 시스템**으로, 3단계 파이프라인(Detect → Publish → Sync)과 벡터 DB 기반 규칙 검색을 결합한 구조를 취하고 있다. 기본 골격은 견고하나, 다음 세 가지 근본적 한계를 안고 있다.

| 구분 | 평가 |
|------|------|
| 아키텍처 방향성 | ✅ 올바른 방향 (Detect→Publish→Sync 파이프라인은 업계 표준에 부합) |
| LLM 활용 수준 | ⚠️ 미흡 (기본값이 stub provider, LLM 미사용) |
| 리뷰 품질 메커니즘 | ❌ 취약 (단순 vector search → template 생성, 컨텍스트 부재) |
| 운영 안정성 | ⚠️ 위험 요소 다수 (동시성, N+1 쿼리, 페이지네이션 누락 등) |

**핵심 결론:** 현재 방향은 맞지만, 리뷰 품질의 핵심인 "컨텍스트 이해"와 "LLM 활용"이 구조적으로 결여되어 있다. 이를 해결하지 않으면 리뷰봇이 생성하는 코멘트가 개발자에게 신뢰를 얻기 어렵다.

---

## 2. 현재 시스템 아키텍처 분석

### 2.1 전체 파이프라인

```
GitLab MR 이벤트 (@review-bot 멘션)
          │
          ▼
  review-bot API (FastAPI)
  ├─ Webhook 검증 (secret, bot 필터)
  ├─ ReviewRun 생성 (PostgreSQL)
  └─ Redis 큐 → execute_detect_job
          │
          ▼
  [DETECT PHASE] review_runner.py:execute_detect_phase()
  ├─ GitLab API로 MR diff 수신
  ├─ C++ 파일만 필터 (.cpp, .h, .cc 등)
  ├─ 80줄 단위로 hunk 분할
  ├─ 각 unit → review-engine API 호출 (top_k=8)
  ├─ 5가지 페널티 점수 계산
  └─ FindingEvidence + FindingDecision DB 저장
          │
          ▼
  [PUBLISH PHASE] review_runner.py:execute_publish_phase()
  ├─ eligible 상태 FindingDecision 조회
  ├─ LLM provider로 코멘트 초안 생성
  │   └─ (기본값: stub_provider — LLM 미사용!)
  ├─ 배치 선택 (상위 10개, rule_family_cap=2)
  └─ GitLab inline discussion 생성/업데이트
          │
          ▼
  [SYNC PHASE] review_runner.py:execute_sync_phase()
  ├─ GitLab 스레드 상태 수집 (resolved/open)
  ├─ 피드백 이벤트 수집 (reply, resolve)
  └─ Finding 상태 업데이트 (resolved/stale)
```

### 2.2 review-engine 내부

```
diff 텍스트 입력
    │
    ▼
C++ 패턴 추출 (change_analysis.py)
├─ malloc/free, raw new/delete
├─ continue/goto, switch without default
├─ IDE_ASSERT, IDE_RC 패턴
└─ 직접 libc 호출, 이식성 문제
    │
    ▼
패턴 → 시맨틱 쿼리 변환
    │
    ▼
ChromaDB 벡터 검색 (로컬 임베딩)
├─ Altibase 규칙 111개
└─ C++ Core Guidelines 418개 (충돌 제외)
    │
    ▼
재순위 (authority, priority, severity, pattern 가중치)
    │
    ▼
상위 8개 규칙 반환
```

### 2.3 LLM Provider 구조

```python
# providers/stub_provider.py (기본값)
issue_type = classify_by_keyword(diff)  # 6개 유형
return TEMPLATE_MAP[issue_type]  # 하드코딩된 한국어 템플릿

# providers/openai_provider.py (옵션)
prompt = f"""
  rule_no: {rule_no}, title: {title}
  change_snippet: {diff_text}
  candidate_line_nos: {lines}
"""
return openai.parse(ReviewDraftPayload)
```

---

## 3. 현재 시스템의 핵심 문제점

### 3.1 🔴 치명적 문제 (즉시 수정 필요)

#### P1-A: LLM이 기본값으로 비활성화됨

**현상:** `BOT_PROVIDER` 환경변수 미설정 시 `stub_provider` 사용. stub은 LLM을 전혀 호출하지 않고, 6개 이슈 유형별 하드코딩된 한국어 템플릿을 반환한다.

**문제:** 코드 내용을 전혀 이해하지 못한 채 패턴 매칭만으로 코멘트 생성. 동일한 `malloc` 호출이라도 컨텍스트에 따라 완전히 다른 리뷰가 필요할 수 있으나, 항상 같은 템플릿 반환.

```python
# stub_provider.py — 실제 코드
if issue_type == "malloc_free":
    return FindingDraft(
        title="메모리를 직접 할당하고 해제하고 있습니다",
        summary="malloc/free로 버퍼 수명을 직접 관리하고...",
        # 항상 동일한 텍스트!
    )
```

#### P1-B: 동시성 제어 없음

**현상:** 같은 PR에 대해 여러 webhook이 동시에 들어오면 복수의 ReviewRun이 생성되어 동일한 FindingDecision을 중복 생성하고, ThreadSyncState 유니크 제약이 깨질 수 있음.

**위험:** 중복 코멘트, DB 제약 위반, 부분 게시 상태.

#### P1-C: list_threads() 페이지네이션 미구현

```python
# gitlab.py — 현재 코드
response = self._get(f"/projects/{pid}/merge_requests/{mr_id}/discussions",
                     params={"per_page": 100})  # 100개 초과 시 누락!
```

**위험:** 100개 이상 discussion이 있는 PR에서 기존 스레드를 못 찾아 중복 코멘트 게시.

---

### 3.2 🟠 심각한 품질 문제

#### P2-A: 컨텍스트 부재 — diff만 보고 전체 파일 구조를 모름

현재 review-engine은 변경된 hunk(80줄)만 분석. 해당 함수가 어떤 클래스에 속하는지, 호출 스택이 어떻게 되는지, 관련 헤더 파일이 무엇인지 전혀 알지 못함.

**결과:** 함수 전체 맥락 없이 일부 라인만 보고 규칙 매칭 → 낮은 정확도, 높은 오탐률.

#### P2-B: engine top_k=8 하드코딩

```python
# engine_client.py
results = await self.review_diff(patch, top_k=8)  # 항상 8개
```

파일의 복잡도나 변경 규모와 무관하게 항상 8개 규칙만 검색. 간단한 1줄 변경도 복잡한 100줄 리팩터링도 동일하게 처리.

#### P2-C: 오탐 감소 메커니즘 부재

산업계 표준은 5~15% 오탐률을 목표로 하지만, 현재 시스템에는:
- 검증 단계 없음 (벡터 검색 결과를 그대로 신뢰)
- 앙상블 없음 (단일 임베딩 모델)
- 증거 기반 필터링 없음
- 자가 검증(self-consistency) 없음

#### P2-D: 리뷰 코멘트 본문 길이 제한 없음

GitLab 코멘트 최대 4,000자 제한이 있으나 코드에서 truncation 처리 없음 → 게시 실패 시 `failed_publication` 상태로 빠져 복구 불가.

---

### 3.3 🟡 운영/성능 문제

#### P3-A: N+1 피드백 쿼리

publish 단계에서 각 FindingDecision별로 피드백 이벤트를 개별 조회 → 50개 finding이면 50개 서브쿼리.

#### P3-B: 정책 경로 매칭 O(findings × policies)

`rules_for_path(file_path)`가 모든 정책에 대해 fnmatch 실행. 캐싱 없음.

#### P3-C: Dead Letter 테이블 무제한 증가

TTL 없이 계속 쌓임 → `build_state()` 호출 시 점점 느려짐.

#### P3-D: OpenAI provider 테스트 없음

현재 테스트는 모두 stub mock 사용. OpenAI 프롬프트 품질, 응답 파싱, timeout 처리 등 전혀 검증되지 않음.

---

## 4. 산업계 주요 리뷰봇 비교

### 4.1 주요 플레이어 개요

| 도구 | 방식 | 특징 | 오탐률 |
|------|------|------|--------|
| **CodeRabbit** | LLM + 정적분석 + 시맨틱 인덱스 | 다중 에이전트, Codegraph, 검증 스크립트 | 낮음 |
| **GitHub Copilot Review** | 목적 맞춤 LLM (멀티모델) | 30초 완료, 71% 액션 가능 피드백 | 중간 |
| **Sourcery** | LLM + 규칙 기반 혼합 | 언어별 특화, 다중 특화 에이전트 | 낮음 |
| **Qodo PR-Agent** | 오픈소스 LLM | 단일 LLM 호출, 토큰 압축, 자체 호스팅 가능 | 중간 |
| **Snyk/DeepCode** | 기호적 AI + ML + LLM 혼합 | 데이터플로우 분석, 보안 특화 | 매우 낮음 |
| **Altibase 현재** | 벡터 검색 + 템플릿/LLM | Altibase 특화, 한국어 | 알 수 없음 |

### 4.2 CodeRabbit — 가장 앞선 접근법

**아키텍처 특징:**

```
PR diff 입력
    │
    ├── Codegraph (파일 의존성 맵, 공동 변경 이력)
    ├── Code Index (함수/클래스 임베딩, 유사 구현 탐색)
    ├── 다중 특화 에이전트 (병렬 실행)
    │   ├── 보안 에이전트
    │   ├── 복잡도 에이전트
    │   ├── 문서/테스트 에이전트
    │   └── 커스텀 규칙 에이전트
    ├── 검증 스크립트 생성 (grep, ast-grep로 주장 검증)
    └── 다단계 필터링 (중복제거 → 신뢰도 → 헛소리 감지)
```

**핵심 차별점:**
- **증거 기반 코멘트:** 모든 코멘트에 `file:line` 인용 필수. 추론이 아닌 실제 코드 참조.
- **검증 에이전트:** 주장을 게시하기 전에 실제로 코드에서 확인하는 grep/AST 쿼리 생성.
- **저장소 전체 인덱싱:** diff만 보지 않고 전체 저장소를 벡터화. 오탐 60% 감소.
- **점진적 리뷰:** PR 전체가 아닌 각 커밋별 리뷰로 비용↓, 노이즈↓.

### 4.3 Qodo PR-Agent — 오픈소스 참조 구현

```
# PR-Agent 핵심 프롬프트 전략
system: "You are a Principal Software Architect reviewing..."
context: {
    "pr_title": ...,
    "pr_description": ...,
    "changed_files": [...],  # 전체 파일 구조
    "diff": ...,
    "repo_language": ...,
    "custom_guidelines": ...
}
```

**핵심 차별점:**
- PR 전체 컨텍스트(제목, 설명, 브랜치 이름)를 프롬프트에 포함
- 단일 LLM 호출로 PR summary + review를 한 번에 생성 (비용 효율)
- 토큰 압축 전략으로 대형 PR도 처리

### 4.4 Snyk DeepCode — 기호적 AI + LLM 혼합

```
단순 LLM 접근 문제점:
  LLM만 → 환각(hallucination) 높음
  규칙만 → 컨텍스트 이해 부재

DeepCode 해결책:
  기호적 AI (데이터플로우 분석) → 사실 기반 발견
       +
  LLM → 설명 생성 + 수정 제안
       +
  기호적 AI → LLM 수정안 재검증
```

**결과:** 80%+ 정확한 자동 수정안, 25M+ 데이터플로우 케이스 처리.

### 4.5 학술 연구 주요 발견

**Atlassian RovoDev (2025, 12개월 실제 배포):**
- 2,000개 저장소, 54,000개 코멘트 생성
- **38.7%의 코멘트가 실제 코드 변경으로 이어짐**
- PR 사이클 타임 30.8% 단축
- 인간 작성 리뷰 35.6% 감소

**Mozilla & Ubisoft 연구 (2024):**
- 공식 수락률: 8.1% (Mozilla), 7.2% (Ubisoft)
- 유용하다고 평가: 23% (Mozilla), 28.3% (Ubisoft)
- 리팩터링 코멘트 수락률이 기능 코멘트의 3~4배 높음

**핵심 인사이트:** LLM 코드 리뷰의 목표는 100% 수락이 아닌 **개발자의 인지 부하 감소와 맥락 이해 지원**이다.

---

## 5. 방향성 평가: 현재 접근법은 맞는가?

### 5.1 올바른 것들 ✅

| 설계 결정 | 평가 | 이유 |
|-----------|------|------|
| Detect → Publish → Sync 3단계 파이프라인 | ✅ 업계 표준 | CodeRabbit, PR-Agent 동일 구조 |
| Redis 큐 기반 비동기 처리 | ✅ 적절 | 응답 지연 없이 처리 가능 |
| GitLab 어댑터 패턴 | ✅ 확장성 있음 | Gerrit, GitHub 추가 용이 |
| Altibase 규칙 우선순위 | ✅ 핵심 가치 | 내부 표준 반드시 반영해야 함 |
| Finding 생명주기 관리 | ✅ 필요함 | 피드백 루프 구현에 필수 |
| 한국어 코멘트 | ✅ 적합 | 내부 팀 대상이므로 당연 |
| 점진적 리뷰(incremental mode) | ✅ 업계 권장 | 커밋별 리뷰가 노이즈 감소 |

### 5.2 근본적으로 바꿔야 할 것들 ❌

| 설계 결정 | 평가 | 문제점 |
|-----------|------|--------|
| Stub provider 기본값 | ❌ 잘못됨 | LLM 없이 의미 있는 리뷰 불가 |
| Diff hunk만 분석 (파일 컨텍스트 없음) | ❌ 불충분 | 맥락 없는 리뷰 = 오탐률 높음 |
| 단일 벡터 검색 → 바로 게시 | ❌ 미흡 | 검증 단계 없음 |
| 80줄 단위 고정 분할 | ❌ 조잡 | 함수/클래스 경계 무시 |
| top_k=8 하드코딩 | ❌ 경직됨 | 복잡도에 무관한 고정값 |

### 5.3 보완이 필요한 것들 ⚠️

| 설계 결정 | 평가 | 보완 방향 |
|-----------|------|-----------|
| ChromaDB 벡터 검색 | ⚠️ 개선 필요 | BM25 하이브리드 추가, 재순위 강화 |
| 피드백 루프 | ⚠️ 구조는 있으나 활용 미흡 | 피드백으로 규칙 가중치 조정 |
| 배치 정책 (상위 10개) | ⚠️ 기계적 | 심각도 기반 동적 배치 |
| 오류 처리 | ⚠️ Dead letter만 있음 | Circuit breaker, 자동 재시도 |

---

## 6. 개선 로드맵

### Phase 1: 즉시 수정 (1~2주) — 안정성 확보

#### 1-1. LLM을 기본값으로 전환

```python
# config.py 변경
BOT_PROVIDER: str = "openai"  # "stub" → "openai"

# openai_provider.py 프롬프트 강화
SYSTEM_PROMPT = """당신은 Altibase C++ 코드베이스의 선임 리뷰어입니다.
다음 원칙에 따라 리뷰하세요:
1. 실제 코드 내용을 분석하고, 구체적인 문제를 설명하세요
2. Altibase 내부 코딩 컨벤션을 우선 기준으로 삼으세요
3. 수정 방법은 Altibase 코드베이스 스타일에 맞게 제안하세요
4. 규칙 ID나 가이드라인 이름을 직접 언급하지 마세요
5. 개발자가 이해할 수 있는 자연스러운 한국어로 작성하세요
"""
```

#### 1-2. 동시성 제어 추가

```python
# review_runner.py에 추가
async def create_review_run_for_key(self, ...):
    # PostgreSQL advisory lock 또는 SELECT FOR UPDATE
    async with session.begin():
        existing = await session.execute(
            select(ReviewRun)
            .where(ReviewRun.request_id == request_id)
            .where(ReviewRun.status.in_(["queued", "running"]))
            .with_for_update(skip_locked=True)
        )
        if existing.scalar():
            raise ReviewAlreadyRunningError()
```

#### 1-3. GitLab 페이지네이션 구현

```python
# gitlab.py
async def list_threads(self, ...):
    threads = []
    page = 1
    while True:
        batch = await self._get("/discussions",
                                params={"per_page": 100, "page": page})
        threads.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return threads
```

#### 1-4. 코멘트 본문 길이 제한

```python
# review_runner.py
MAX_COMMENT_BODY = 3800  # GitLab 4000자 제한 여유

def render_comment(self, draft: FindingDraft) -> str:
    body = self._render_full(draft)
    if len(body) > MAX_COMMENT_BODY:
        body = body[:MAX_COMMENT_BODY - 20] + "\n...(이하 생략)"
    return body
```

---

### Phase 2: 리뷰 품질 향상 (2~4주) — 핵심 가치 개선

#### 2-1. 파일 전체 컨텍스트 포함 (가장 중요)

현재는 변경된 hunk만 분석. 전체 파일 컨텍스트를 LLM 프롬프트에 포함해야 함.

```python
# engine_client.py 수정
async def review_diff(self, patch: str, file_path: str,
                       full_file_content: str | None = None,
                       top_k: int = 8) -> ReviewResponse:
    payload = {
        "patch": patch,
        "file_path": file_path,
        "file_context": full_file_content[:4000] if full_file_content else None,
        "top_k": top_k,
    }
```

```python
# openai_provider.py 프롬프트 개선
USER_TEMPLATE = """
[변경 파일 전체 구조 (참고용)]
{file_context}

[실제 변경 내용 (diff)]
{change_snippet}

[적용 가능한 규칙]
{rule_title}: {rule_summary}
{fix_guidance}

위 변경 내용에서 이 규칙이 실제로 위반되고 있는지 분석하고,
구체적인 수정 방법을 제안하세요.
확실하지 않으면 should_publish=false로 설정하세요.
"""
```

#### 2-2. PR 메타데이터 컨텍스트 추가

```python
# 프롬프트에 PR 컨텍스트 추가
pr_context = f"""
[PR 정보]
제목: {mr_meta.title}
소스 브랜치: {mr_meta.source_branch}
대상 브랜치: {mr_meta.target_branch}
"""
```

#### 2-3. 함수/클래스 경계 기반 분할

```python
# review_runner.py — _iter_review_units() 개선
def _iter_review_units(self, patch: str, file_path: str):
    # 현재: 80줄 고정 분할
    # 개선: 함수/클래스 경계 인식
    if file_path.endswith(('.cpp', '.cc', '.h')):
        yield from self._split_by_cpp_boundaries(patch)
    else:
        yield from self._split_by_lines(patch, max_lines=80)

def _split_by_cpp_boundaries(self, patch: str):
    # { } 중괄호 레벨 추적으로 함수 단위 분할
    # 함수 하나가 완전히 포함되도록 경계 설정
    ...
```

#### 2-4. 신뢰도 기반 동적 top_k

```python
# engine_client.py
def compute_top_k(patch: str) -> int:
    lines = patch.count('\n')
    if lines < 20:   return 5
    if lines < 50:   return 8
    if lines < 100:  return 12
    return 15
```

#### 2-5. 검증 단계 추가 (오탐 감소)

```python
# providers/openai_provider.py — 2단계 검증 추가
async def build_draft(self, evidence, decision) -> FindingDraft:
    # 1단계: 초안 생성
    draft = await self._generate_draft(evidence, decision)

    if not draft.should_publish:
        return draft

    # 2단계: 자가 검증 (Self-consistency check)
    verification = await self._verify_draft(draft, evidence.change_snippet)
    if not verification.confirmed:
        draft.should_publish = False
        draft.confidence = max(0.0, draft.confidence - 0.3)

    return draft

async def _verify_draft(self, draft, snippet) -> VerificationResult:
    prompt = f"""
    다음 코드 리뷰 코멘트가 아래 코드 변경에 실제로 적용되는지 확인하세요.
    코멘트: {draft.summary}
    코드: {snippet}
    
    이 코멘트가 정확한가? 코드에 실제로 이 문제가 있는가?
    JSON으로 응답: {{"confirmed": true/false, "reason": "..."}}
    """
    ...
```

---

### Phase 3: 아키텍처 고도화 (1~2개월) — 업계 수준 달성

#### 3-1. RAG 기반 저장소 인덱싱

업계 연구에 따르면 diff만 보지 않고 **전체 저장소를 인덱싱**하면 오탐률이 60% 감소.

```
[저장소 인덱싱 파이프라인]

1. 전체 .cpp/.h 파일 파싱
   └── 함수/클래스 단위로 청크 분할

2. 각 청크 임베딩 (ChromaDB)
   └── 메타: 파일경로, 함수명, 클래스, 수정일

3. MR diff 도착 시
   └── 변경된 함수와 유사한 기존 코드 검색
   └── 프롬프트에 유사 구현 패턴 추가
   └── "이 코드베이스에서는 보통 이렇게 함" 컨텍스트 제공

4. 결과
   └── 코드베이스 스타일 일관성 확인
   └── 중복 구현 감지
   └── 기존 유사 패턴과 비교 리뷰
```

#### 3-2. 다중 특화 에이전트 (CodeRabbit 방식)

```python
# 단일 리뷰 에이전트 → 특화 에이전트 분리
AGENTS = {
    "memory_safety": MemorySafetyAgent(),      # malloc/free, 스마트포인터
    "error_handling": ErrorHandlingAgent(),    # IDE_RC, 에러 전파
    "naming_convention": NamingAgent(),        # Altibase 명명 규칙
    "thread_safety": ThreadSafetyAgent(),      # 동시성, 잠금
    "portability": PortabilityAgent(),         # 플랫폼 독립성
}

async def review_diff(patch, context):
    tasks = [agent.analyze(patch, context) for agent in AGENTS.values()]
    results = await asyncio.gather(*tasks)  # 병렬 실행
    return merge_and_deduplicate(results)
```

#### 3-3. 피드백 기반 규칙 가중치 학습

```python
# 현재: 피드백을 페널티로만 활용
# 개선: 피드백으로 규칙 유용성 학습

class RuleEffectivenessTracker:
    def record_resolution(self, rule_no: str, resolved: bool):
        # resolved=True: 개발자가 실제로 수정함 (좋은 리뷰)
        # resolved=False (ignored): 오탐일 가능성 높음
        self._update_rule_score(rule_no, delta=+0.1 if resolved else -0.05)

    def get_rule_weight(self, rule_no: str) -> float:
        # ChromaDB 재순위 시 이 가중치 적용
        return self._rule_scores.get(rule_no, 1.0)
```

#### 3-4. Circuit Breaker 및 운영 모니터링

```python
# engine_client.py
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def review_diff(self, patch: str) -> ReviewResponse:
    ...

# metrics.py (추가 필요)
REVIEW_LATENCY = Histogram('review_bot_latency_seconds', ...)
FINDINGS_PUBLISHED = Counter('review_bot_findings_published_total', ...)
FALSE_POSITIVE_RATE = Gauge('review_bot_false_positive_rate', ...)
```

---

### Phase 4: 장기 비전 (3개월+)

#### 4-1. 증거 기반 코멘트 (CodeRabbit 수준)

모든 코멘트에 실제 코드 인용 강제:
```
[봇 리뷰] 메모리 수명 관리 문제

`keys[i] = (char *)malloc(keyLen + 1);` (68번 줄)에서 
직접 malloc을 사용하고 있습니다.

이 버퍼는 반드시 `free(keys[i])` 쌍으로 해제되어야 하며,
예외 경로에서 누수가 발생할 수 있습니다.

권장 수정:
```cpp
std::vector<std::string> keys(keyCount);
keys[i] = std::string(keyValue, keyLen);
```
이렇게 수정하면 소멸자가 자동으로 메모리를 해제합니다.

근거: `malloc` 호출이 68번 줄에 확인됨, 해당 경로에 `free` 없음.
```

#### 4-2. PR 설명 자동 생성

```
현재: 리뷰만 함
추가: PR diff → 한국어 변경 요약 자동 생성
     - 무엇이 바뀌었는가
     - 왜 바뀌었는가 (브랜치명, 커밋 메시지 분석)
     - 리뷰어가 집중해야 할 부분
```

#### 4-3. 자동 수정 제안 (Auto-fix)

```python
# 단순하고 확실한 케이스에 한해 수정 코드 자동 생성
if finding.rule_no == "A2.5" and confidence > 0.9:
    fix_diff = await generate_fix(original_code, rule_guidance)
    # GitLab suggestion 블록으로 게시 (원클릭 적용 가능)
    suggestion = f"```suggestion\n{fix_diff}\n```"
```

---

## 7. 결론

### 7.1 현재 시스템 종합 평가

```
리뷰봇 성숙도 평가

아키텍처 설계    ████████░░  80%  (3단계 파이프라인, 어댑터 패턴 양호)
LLM 활용        ██░░░░░░░░  20%  (기본값이 stub, LLM 미활성)
리뷰 품질        ███░░░░░░░  30%  (컨텍스트 없음, 검증 없음)
운영 안정성      █████░░░░░  50%  (Dead letter 있으나 동시성 취약)
테스트 커버리지  ██████░░░░  60%  (주요 흐름 커버, LLM 경로 미검증)
```

### 7.2 우선순위 요약

**즉시 (이번 주):**
1. `BOT_PROVIDER=openai`를 기본값으로 변경
2. GitLab list_threads 페이지네이션 구현
3. 코멘트 본문 길이 제한 추가

**단기 (2~4주):**
4. 파일 전체 컨텍스트를 LLM 프롬프트에 포함
5. 동시성 제어 (Advisory Lock)
6. LLM 검증 단계 추가 (오탐 감소)

**중기 (1~2개월):**
7. 저장소 인덱싱 (RAG for codebase)
8. 다중 특화 에이전트 분리
9. 피드백 기반 규칙 가중치 학습
10. 운영 메트릭 및 Circuit Breaker

### 7.3 최종 권고

현재 시스템은 **좋은 골격을 가진 MVP**다. 3단계 파이프라인, GitLab 통합, Finding 생명주기 관리는 모두 올바른 방향이다.

그러나 **리뷰봇의 본질적 가치인 "정확하고 유용한 코멘트 생성"** 에서 아직 충분하지 않다. 이는 LLM 미활성화와 컨텍스트 부재라는 두 가지 구조적 결함에서 비롯된다.

**가장 빠른 품질 향상 경로:**
> LLM 활성화 → 파일 전체 컨텍스트 추가 → 검증 단계 추가

이 세 가지만으로도 현재 대비 리뷰 품질이 크게 향상될 것으로 판단된다.

---

*본 보고서는 /home/et16/work/review_system 코드베이스 전수 분석과 CodeRabbit, GitHub Copilot, Sourcery, Qodo PR-Agent, Snyk DeepCode 등 주요 도구 조사, 그리고 Atlassian(2025), Mozilla/Ubisoft(2024) 등 실제 배포 연구를 기반으로 작성되었습니다.*
