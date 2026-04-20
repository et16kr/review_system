# 리뷰 봇 재설계 설계 문서

- 문서 상태: Proposed
- 작성일: 2026-04-20
- 기반 문서: `docs/REVIEW_BOT_REDESIGN_AUDIT_REPORT.md`
- 적용 범위: `review-bot`, `review-engine`, GitLab adapter, 내부 DB/queue/worker, 운영 문서
- 설계 관점: GitLab-first, multi-project/multi-SCM 확장 가능, 운영형 리뷰 lifecycle 중심

## 1. 문서 목적

이 문서는 감사 보고서의 결론을 실제 구현 가능한 target design으로 구체화한다.

핵심 목표는 다음과 같다.

- 현재의 `external Git UI -> review-bot -> review-engine` 큰 방향은 유지한다.
- 운영형 리뷰 봇에 필요한 identity, adapter contract, thread lifecycle, observability, feedback loop를 설계한다.
- LLM의 역할을 1차 탐지기보다 설명기와 triage assistant로 재배치한다.
- 향후 구현자가 추가 아키텍처 결정을 최소화하고 바로 구현에 들어갈 수 있도록 한다.

## 2. 범위와 비범위

### 2.1 범위

- `review-bot` target architecture
- `review-engine` target responsibility
- review request identity model
- adapter v2 contract
- internal persistence model
- review pipeline
- publish/thread sync/feedback loop
- migration and rollout strategy
- observability, security, test strategy

### 2.2 비범위

- GitHub/Gerrit adapter의 즉시 구현
- Sonar/Snyk 같은 외부 도구의 실제 연동 코드 작성
- 기존 current-state 문서의 즉시 대체
- 모델 프롬프트 세부 문안 확정

현재 `docs/API_CONTRACTS.md`는 current implementation 문서로 남기고, 본 문서는 target design 문서로 관리한다. 구현 cutover가 끝나면 current-state 문서를 본 설계에 맞게 갱신한다.

## 3. 설계 목표

### 3.1 기능 목표

- GitLab MR open/reopen/update with new commit에 대해 안정적으로 incremental review를 수행한다.
- inline discussion 기반 게시를 기본으로 한다.
- 게시 후 thread 상태를 주기적으로 동기화한다.
- reviewer feedback을 suppression/rerank signal로 회수한다.
- multi-project GitLab 운영이 가능해야 한다.
- 장기적으로 GitHub/Gerrit adapter를 추가할 수 있어야 한다.

### 3.2 품질 목표

- 탐지 정확도보다 노이즈 억제를 더 우선한다.
- 동일 finding의 중복 게시를 최소화한다.
- 문서와 런타임의 drift를 줄인다.
- 운영자가 실패 원인과 상태를 구조적으로 확인할 수 있어야 한다.
- 테스트가 실행 위치에 따라 달라지지 않도록 package/workspace 경계를 정리한다.

### 3.3 설계 원칙

1. 외부 SCM이 canonical state owner다.
2. `review-bot`은 orchestration, sync, publish, learn을 맡는다.
3. `review-engine`은 detection과 evidence shaping을 맡는다.
4. LLM은 publishing-ready explanation을 생성한다.
5. 게시는 생성(create)보다 동기화(sync)를 우선한다.
6. rule metadata와 reviewer feedback은 scoring에 반영된다.
7. current-state와 target-state는 cutover 이전까지 분리 문서로 관리한다.

## 4. 목표 아키텍처

### 4.1 상위 구조

```text
GitLab / Other SCM
    -> Webhook Intake
    -> review-bot
        -> Event Normalizer
        -> Review Run Orchestrator
        -> SCM Adapter v2
        -> Scoring / Policy / Dedupe
        -> LLM Explainer
        -> Publication Manager
        -> Thread Sync Worker
        -> Feedback Collector
        -> Postgres
        -> Redis / Queue
    -> review-engine
        -> Pattern Extractor
        -> Guideline Retriever
        -> Candidate Builder
        -> Metadata / Reviewability / Rule Profiles
```

### 4.2 컴포넌트 책임

| 컴포넌트 | 책임 | 비고 |
| --- | --- | --- |
| Webhook Intake | SCM webhook 수신, secret 검증, event normalize | GitLab-specific payload를 내부 공통 event로 변환 |
| Review Run Orchestrator | run 생성, mode 결정, queue enqueue | full/incremental/manual 구분 |
| SCM Adapter v2 | diff/meta/thread/check/feedback 인터페이스 제공 | GitLab/GitHub/Gerrit 별 구현 |
| review-engine | diff 패턴 추출, candidate evidence 생성, reviewability metadata 제공 | deterministic signal 중심 |
| Scoring / Policy | severity, confidence, dedupe, suppression, batching | LLM 호출 전 단계 |
| LLM Explainer | reviewer-facing 설명문과 수정 가이드 생성 | publish 대상에만 호출 |
| Publication Manager | comment upsert, status publish, publication state 저장 | create보다 upsert 중심 |
| Thread Sync Worker | thread resolve/stale 상태 동기화 | push 이후 reconcile 수행 |
| Feedback Collector | resolve/reply/reaction 이벤트 수집 | score와 suppression에 반영 |

### 4.3 큐 구성

초기 target queue는 아래 4개를 권장한다.

- `review-intake`
  - webhook 이후 run 생성/스케줄링
- `review-detect`
  - diff fetch, engine detect, score
- `review-publish`
  - explanation 생성, comment upsert, status publish
- `review-sync`
  - thread reconcile, feedback collect, stale/resolve 처리

초기 구현에서는 물리적으로 하나의 Redis를 사용해도 되지만, 논리적으로는 job type을 분리한다.

## 5. 목표 리뷰 파이프라인

### 5.1 파이프라인

```text
event intake
-> identity normalize
-> fetch review request meta
-> fetch diff
-> detect
-> validate
-> score
-> explain
-> publish
-> sync
-> learn
```

### 5.2 단계별 책임

#### detect

- diff에서 review unit을 생성한다.
- `review-engine`이 pattern, guideline candidate, rule metadata를 반환한다.
- 이 단계에서는 가능한 finding을 넓게 찾되, 최종 게시 여부는 결정하지 않는다.

#### validate

- `manual_only`와 `reference_only` 여부 확인
- anchor 후보의 changed-line 유효성 확인
- adapter capability 확인
- SCM가 제공한 `head_sha`, `base_sha`, `start_sha` 정합성 확인
- invalid/stale candidate 제거

#### score

- 기본 규칙 score
- false positive risk
- severity
- confidence
- historical suppression 여부
- reviewer resolved history
- duplicate/stale 여부
- batch diversity

#### explain

- score threshold를 넘긴 finding에만 LLM 호출
- 결과물:
  - 리뷰 제목
  - 왜 중요한지
  - 수정 방향
  - optional suggested fix

#### publish

- thread upsert
- status/check publish
- publication state update

#### sync

- 기존 thread와 이번 run의 finding을 reconcile
- 해결된 thread resolve
- 더 이상 유효하지 않은 thread stale 표시
- 게시 실패 재시도 분류

#### learn

- resolve/unresolve/reply/reaction 수집
- suppression 규칙 갱신
- 다음 score에 reviewer preference 반영

## 6. 주요 설계 결정

### 6.1 방향 유지

유지한다.

```text
external Git UI -> review-bot -> review-engine
```

이 결정은 다음 이유로 유지한다.

- SCM UI가 팀의 canonical review surface이기 때문이다.
- adapter를 통해 SCM별 차이를 isolate할 수 있기 때문이다.
- `review-engine`을 규칙 탐지 엔진으로 유지할 수 있기 때문이다.

### 6.2 LLM 역할 재배치

LLM은 `detect`보다 `explain` 단계에 둔다.

이유:

- deterministic signal 없이 LLM이 1차 판정까지 맡으면 false positive 통제가 어렵다.
- review-engine의 rule metadata를 기반으로 설명을 생성하는 편이 재현성과 평가 가능성이 높다.
- Sonar Review, Qodo, CodeRabbit 등 성숙한 제품의 공통 패턴과도 맞는다.

### 6.3 게시 전략

- default는 inline discussion
- general note는 summary 용도 또는 명시적 fallback 시에만 사용
- inline anchor가 불확실하면 게시하지 않는 편을 기본 정책으로 삼는다

### 6.4 리뷰 모드

| 모드 | 정의 | 트리거 |
| --- | --- | --- |
| `full` | 현재 open diff 전체를 새로 판단 | 최초 open, reopen, 명시적 수동 재리뷰 |
| `incremental` | 마지막 reviewed head 이후 새 commit 범위만 재검토 | update with new commits |
| `manual` | 운영자 또는 사용자 요청 기반 강제 실행 | 내부 API 또는 slash/comment trigger |
| `sync-only` | 게시 없이 thread/feedback만 동기화 | cron 또는 push 후 reconcile |

## 7. Identity 모델

### 7.1 현재 문제

현재 `pr_id` 단일 정수는 GitLab MR `iid`를 그대로 담고 있어 multi-project 운영에 취약하다.

### 7.2 목표 키

```text
ReviewRequestKey {
  review_system: string
  project_ref: string
  review_request_id: string
}
```

예시:

```json
{
  "review_system": "gitlab",
  "project_ref": "root/altidev4-review",
  "review_request_id": "34"
}
```

### 7.3 규칙

- `review_system`은 `gitlab`, `github`, `gerrit` 등 canonical adapter 이름을 사용한다.
- `project_ref`는 SCM 내부에서 안정적인 project/repo 식별자 문자열을 사용한다.
- `review_request_id`는 외부 시스템의 canonical review request ID를 문자열로 저장한다.
- DB 내부 surrogate key는 별도로 둘 수 있지만, business identity는 composite key를 사용한다.

## 8. Domain 모델

### 8.1 핵심 엔터티

| 엔터티 | 설명 |
| --- | --- |
| `ReviewRequest` | 외부 SCM의 review object를 내부적으로 대표하는 엔터티 |
| `ReviewRun` | 하나의 리뷰 실행 단위 |
| `FindingEvidence` | detector가 수집한 근거 단위 |
| `FindingDecision` | 게시 여부가 결정된 finding 단위 |
| `PublicationState` | 게시 결과 및 comment/thread 참조 |
| `ThreadSyncState` | 외부 thread와 내부 finding의 동기화 상태 |
| `FeedbackEvent` | reviewer 행동 이벤트 |

### 8.2 상태 모델

#### ReviewRun.status

- `queued`
- `running`
- `success`
- `partial`
- `failed`
- `skipped`
- `cancelled`

#### FindingDecision.state

- `candidate`
- `suppressed`
- `eligible`
- `published`
- `failed_publication`
- `resolved`
- `stale`
- `dismissed`

#### ThreadSyncState.sync_status

- `open`
- `resolved`
- `stale`
- `deleted`
- `unknown`

## 9. 데이터베이스 설계

### 9.1 `review_requests`

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | UUID PK | 내부 surrogate key |
| `review_system` | varchar(32) | `gitlab`, `github`, `gerrit` |
| `project_ref` | varchar(255) | repo/project canonical ref |
| `review_request_id` | varchar(128) | external MR/PR id |
| `source_branch` | varchar(255) nullable | source branch |
| `target_branch` | varchar(255) nullable | target branch |
| `latest_head_sha` | varchar(64) nullable | 최신 head |
| `latest_base_sha` | varchar(64) nullable | 최신 base |
| `latest_start_sha` | varchar(64) nullable | GitLab diff start sha |
| `created_at` | timestamptz | 생성 시각 |
| `updated_at` | timestamptz | 갱신 시각 |

제약:

- unique(`review_system`, `project_ref`, `review_request_id`)

### 9.2 `review_runs`

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | UUID PK | run id |
| `review_request_id_fk` | UUID FK | `review_requests.id` |
| `trigger` | varchar(64) | `gitlab:open`, `gitlab:update`, `manual` |
| `mode` | varchar(32) | `full`, `incremental`, `manual`, `sync-only` |
| `base_sha` | varchar(64) nullable | 실행 기준 base |
| `start_sha` | varchar(64) nullable | 실행 기준 start |
| `head_sha` | varchar(64) nullable | 실행 기준 head |
| `status` | varchar(32) | run 상태 |
| `job_id` | varchar(128) nullable | queue job id |
| `error_category` | varchar(64) nullable | failure 분류 |
| `error_message` | text nullable | failure detail |
| `started_at` | timestamptz nullable | 시작 시각 |
| `completed_at` | timestamptz nullable | 종료 시각 |
| `created_at` | timestamptz | 생성 시각 |

### 9.3 `finding_evidences`

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | UUID PK | evidence id |
| `review_run_id_fk` | UUID FK | run id |
| `file_path` | varchar(1000) | 대상 파일 |
| `patch_digest` | varchar(128) | patch hash |
| `hunk_header` | varchar(255) nullable | hunk header |
| `candidate_line_nos` | jsonb | changed line 후보 |
| `matched_patterns` | jsonb | detector signal 목록 |
| `change_snippet` | text | 설명과 검증에 쓰는 snippet |
| `raw_engine_payload` | jsonb | engine 원응답 일부 |
| `created_at` | timestamptz | 생성 시각 |

### 9.4 `finding_decisions`

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | UUID PK | decision id |
| `review_run_id_fk` | UUID FK | run id |
| `evidence_id_fk` | UUID FK | evidence id |
| `review_request_id_fk` | UUID FK | review request |
| `rule_no` | varchar(128) | rule id |
| `source_family` | varchar(64) | `altibase`, `cpp_core` |
| `reviewability` | varchar(32) | `auto_review`, `manual_only`, `reference_only` |
| `severity` | varchar(32) | `low`, `medium`, `high`, `critical` |
| `confidence` | numeric | 0.0~1.0 |
| `score_raw` | numeric | engine 기본 score |
| `score_final` | numeric | publish 최종 score |
| `fingerprint` | varchar(255) | stable finding fingerprint |
| `dedupe_key` | varchar(255) | human-centric dedupe key |
| `anchor_payload` | jsonb | file/line/range/hunk hash |
| `suppression_reason` | varchar(128) nullable | suppression 이유 |
| `state` | varchar(32) | finding 상태 |
| `title` | varchar(300) nullable | explain 이후 제목 |
| `summary` | text nullable | explain 이후 설명 |
| `suggested_fix` | text nullable | optional fix |
| `created_at` | timestamptz | 생성 시각 |
| `updated_at` | timestamptz | 갱신 시각 |

제약:

- unique(`review_request_id_fk`, `fingerprint`, `review_run_id_fk`)

### 9.5 `publication_states`

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | UUID PK | publication id |
| `finding_decision_id_fk` | UUID FK | decision |
| `review_request_id_fk` | UUID FK | review request |
| `adapter_comment_ref` | varchar(255) nullable | SCM comment id |
| `adapter_thread_ref` | varchar(255) nullable | SCM thread/discussion id |
| `body_hash` | varchar(128) nullable | 마지막 게시 본문 hash |
| `batch_no` | integer | 게시 batch |
| `publish_state` | varchar(32) | `pending`, `published`, `failed`, `updated` |
| `error_category` | varchar(64) nullable | publish failure 분류 |
| `error_message` | text nullable | error detail |
| `published_at` | timestamptz nullable | 게시 시각 |
| `updated_at` | timestamptz | 갱신 시각 |

### 9.6 `thread_sync_states`

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | UUID PK | sync state id |
| `review_request_id_fk` | UUID FK | review request |
| `finding_decision_id_fk` | UUID FK nullable | current linked finding |
| `adapter_thread_ref` | varchar(255) | SCM thread id |
| `adapter_comment_ref` | varchar(255) nullable | SCM comment id |
| `sync_status` | varchar(32) | `open`, `resolved`, `stale`, `deleted`, `unknown` |
| `last_seen_head_sha` | varchar(64) nullable | 마지막으로 확인한 head |
| `last_synced_at` | timestamptz | 마지막 동기화 |
| `resolution_reason` | varchar(64) nullable | `fixed`, `stale`, `manual`, `deleted` |

### 9.7 `feedback_events`

| 컬럼 | 타입 | 설명 |
| --- | --- | --- |
| `id` | UUID PK | event id |
| `review_request_id_fk` | UUID FK | review request |
| `adapter_thread_ref` | varchar(255) nullable | thread ref |
| `adapter_comment_ref` | varchar(255) nullable | comment ref |
| `event_type` | varchar(64) | `resolved`, `reopened`, `reply`, `reaction`, `edit` |
| `actor_type` | varchar(32) | `human`, `bot`, `system` |
| `actor_ref` | varchar(255) nullable | user id |
| `payload` | jsonb | raw event 일부 |
| `occurred_at` | timestamptz | event 시각 |
| `ingested_at` | timestamptz | 수집 시각 |

## 10. Fingerprint와 Anchor 설계

### 10.1 목표

- 같은 issue가 line shift 때문에 매번 새 finding으로 보이지 않게 한다.
- 반대로 다른 issue가 같은 line에 있다고 하나의 finding으로 합쳐지지 않게 한다.

### 10.2 Fingerprint 공식

기본 fingerprint는 아래 값을 정규화해 SHA-256으로 만든다.

```text
review_system
project_ref
review_request_id
file_path
rule_no
issue_signature
anchor_signature
```

여기서:

- `issue_signature`
  - matched pattern
  - normalized title class
  - 핵심 snippet digest
- `anchor_signature`
  - hunk header
  - target line range
  - changed line digest

### 10.3 Anchor 모델

```json
{
  "file_path": "src/id/ids/idsTde.cpp",
  "line_type": "new",
  "start_line": 76,
  "end_line": 76,
  "candidate_line_nos": [76, 77, 78],
  "hunk_header": "@@ -70,6 +70,12 @@",
  "changed_line_digest": "sha256:..."
}
```

정책:

- publish는 `line_type = new` anchor만 기본 허용
- changed-line match가 약하면 suppress
- anchor confidence가 낮을 때 general note로 자동 fallback하지 않음

## 11. Adapter v2 설계

### 11.1 Python Protocol

```python
class ReviewSystemAdapterV2(Protocol):
    def fetch_review_request_meta(self, key: ReviewRequestKey) -> ReviewRequestMeta: ...
    def fetch_diff(self, key: ReviewRequestKey, *, mode: str, base_sha: str | None = None) -> DiffPayload: ...
    def list_threads(self, key: ReviewRequestKey) -> list[ThreadSnapshot]: ...
    def upsert_comment(self, key: ReviewRequestKey, request: CommentUpsertRequest) -> CommentUpsertResult: ...
    def resolve_thread(self, key: ReviewRequestKey, thread_ref: str, *, reason: str) -> ResolveThreadResult: ...
    def publish_check(self, key: ReviewRequestKey, request: CheckPublishRequest) -> CheckPublishResult: ...
    def collect_feedback(self, key: ReviewRequestKey, *, since: str | None = None) -> FeedbackPage: ...
```

### 11.2 핵심 타입

#### `ReviewRequestMeta`

```json
{
  "key": {
    "review_system": "gitlab",
    "project_ref": "root/altidev4-review",
    "review_request_id": "34"
  },
  "title": "TDE 리뷰 개선",
  "state": "opened",
  "draft": false,
  "source_branch": "feature/tde-review",
  "target_branch": "main",
  "base_sha": "abc123",
  "start_sha": "abc123",
  "head_sha": "def456"
}
```

#### `DiffPayload`

```json
{
  "pull_request": {
    "base_sha": "abc123",
    "start_sha": "abc123",
    "head_sha": "def456"
  },
  "files": [
    {
      "path": "src/a.cpp",
      "status": "modified",
      "patch": "@@ -10,6 +10,10 @@ ...",
      "old_path": "src/a.cpp",
      "new_path": "src/a.cpp"
    }
  ]
}
```

#### `CommentUpsertRequest`

```json
{
  "fingerprint": "sha256:...",
  "body": "메모리 해제 이후 NULL reset이 없습니다...",
  "anchor": {
    "file_path": "src/a.cpp",
    "line_type": "new",
    "start_line": 76,
    "end_line": 76,
    "hunk_header": "@@ -70,6 +70,12 @@"
  },
  "existing_thread_ref": null,
  "existing_comment_ref": null,
  "mode": "create_or_update"
}
```

#### `CommentUpsertResult`

```json
{
  "comment_ref": "note-123",
  "thread_ref": "discussion-999",
  "action": "created",
  "ok": true
}
```

### 11.3 GitLab adapter v2 정책

- diff 조회는 `GET /merge_requests/:iid/changes`를 기본 사용
- large diff 생략 시 raw file fetch로 patch 재구성
- inline discussion이 가능하면 discussion 사용
- `discussion` 재사용이 가능한 경우 update/upsert 우선
- commit status 또는 check 유사 상태는 별도 publish path 사용
- feedback는 discussion resolve 상태, reply, note 변경을 수집

## 12. `review-engine` target contract

### 12.1 역할

`review-engine`은 아래만 맡는다.

- diff/code pattern extraction
- guideline retrieval
- rule metadata merge
- candidate evidence shaping

`review-engine`은 아래를 맡지 않는다.

- SCM thread lifecycle
- external status publishing
- reviewer feedback sync
- LLM comment generation

### 12.2 응답 원칙

`review-engine`은 자연어 코멘트보다 구조화된 candidate를 반환한다.

```json
{
  "results": [
    {
      "rule_no": "ALTI-MEM-007",
      "source_family": "altibase",
      "reviewability": "auto_review",
      "severity_default": 0.92,
      "false_positive_risk": "low",
      "score": 0.97,
      "category": "memory",
      "matched_patterns": ["malloc_free", "free_without_null_reset"],
      "candidate_line_nos": [76, 77, 78],
      "issue_signature": "malloc_free+free_without_null_reset",
      "title_hint": "메모리 해제 규칙 후보",
      "summary_hint": "manual allocation/free pattern detected",
      "fix_guidance": "RAII, owner wrapper..."
    }
  ]
}
```

### 12.3 Detector 계약 강화

현재처럼 diff manifest와 extractor logic이 어긋나는 문제를 막기 위해 아래를 mandatory로 둔다.

- example diff manifest는 detector contract의 일부로 본다.
- rule section별 representative diff corpus를 유지한다.
- 신규/수정된 pattern은 contract test를 먼저 추가한다.
- `manual_only`와 `reference_only`는 detect는 가능하되 publish eligibility는 bot에서 다시 검증한다.

## 13. `review-bot` 내부 모듈 구조

### 13.1 권장 패키지 분리

현재 `app` namespace 충돌을 피하기 위해 target package를 아래처럼 바꾸는 것을 권장한다.

- `review_bot`
- `review_engine`

최소 목표:

- 루트와 하위 서비스가 동일한 top-level `app`을 공유하지 않음
- 테스트 import가 실행 위치와 무관하게 결정됨

### 13.2 `review-bot` 모듈 제안

```text
review_bot/
  api/
  events/
  orchestrator/
  adapters/
  scoring/
  explanation/
  publication/
  sync/
  feedback/
  db/
  queueing/
  telemetry/
```

## 14. 주요 시퀀스

### 14.1 MR open / reopen

```text
GitLab webhook
-> EventNormalizer
-> ReviewRun(full) 생성
-> fetch_review_request_meta
-> fetch_diff(full)
-> review-engine detect
-> validate / score
-> explain
-> publish inline threads
-> publish running/success status
-> schedule sync job
```

### 14.2 MR update with new commit

```text
GitLab webhook(update + oldrev)
-> ReviewRun(incremental) 생성
-> fetch meta
-> fetch diff(incremental)
-> detect / validate / score
-> list_threads
-> upsert_comment or suppress
-> resolve stale threads if needed
-> schedule feedback collection
```

### 14.3 MR update without new commit

```text
GitLab webhook(update without oldrev)
-> ignore
-> optional sync-only job only if metadata changed
```

### 14.4 게시 실패

```text
publish attempt
-> adapter error
-> classify error
-> mark failed_publication
-> if transient: enqueue retry
-> if anchor invalid: suppress and record anchor_failure
-> do not fallback to general note automatically
```

### 14.5 reviewer가 thread를 resolve

```text
feedback collector
-> collect resolve event
-> store FeedbackEvent(resolved)
-> ThreadSyncState = resolved
-> future scoring receives suppression bonus
```

## 15. Scoring과 게시 정책

### 15.1 score 계산식

최종 score는 아래 요소를 결합한다.

```text
final_score =
  engine_score
  + severity_weight
  + confidence_weight
  + novelty_bonus
  - false_positive_penalty
  - reviewer_resolved_penalty
  - duplicate_penalty
  - weak_anchor_penalty
```

### 15.2 기본 정책

- `reviewability != auto_review` 이면 기본 suppress
- `minimum_publish_score` 미만이면 suppress
- weak anchor면 suppress
- 같은 `dedupe_key`가 현재 open thread에 있으면 새 publish 대신 upsert 또는 skip
- batch는 diversity를 우선한다
- push가 짧은 간격으로 반복되면 commit threshold pause를 둘 수 있다

### 15.3 summary 정책

summary는 별도 생성 가능하되, target design의 핵심은 inline discussion lifecycle이다.

초기 목표:

- summary는 optional
- inline finding이 canonical

## 16. Thread Sync와 Feedback Loop

### 16.1 Thread Sync Worker

주기:

- publish 직후
- MR update 이후
- 주기적 cron

역할:

- existing thread 조회
- 현재 open finding과 external thread mapping
- 해결된 thread close sync
- deleted/stale thread 감지
- 불필요한 중복 thread 정리

### 16.2 Feedback Collector

수집 대상:

- resolve/unresolve
- human reply
- reaction
- edited note

활용 방식:

- resolved가 반복되는 rule/path 조합은 score penalty 강화
- 특정 reviewer가 자주 dismiss하는 rule은 candidate threshold를 상향
- human reply가 수정 요청으로 이어진 경우 explainer prompt 개선 후보로 사용

## 17. Internal API 제안

외부 표준 인터페이스는 SCM webhook이지만, 운영과 테스트를 위해 내부 API는 아래 수준을 권장한다.

### 17.1 `POST /internal/review/events`

정규화된 event를 수동 주입한다.

### 17.2 `POST /internal/review/runs`

특정 `ReviewRequestKey`에 대해 full/manual/sync-only run을 강제 생성한다.

### 17.3 `POST /internal/review/runs/{run_id}/publish`

detect/score가 끝난 run을 재게시한다.

### 17.4 `POST /internal/review/runs/{run_id}/sync`

thread sync를 수동 수행한다.

### 17.5 `GET /internal/review/requests/{review_system}/{project_ref}/{review_request_id}`

state, latest run, open findings, open threads를 조회한다.

## 18. 운영, 보안, 관측성

### 18.1 로그 필드

모든 structured log에 아래 필드를 포함한다.

- `review_system`
- `project_ref`
- `review_request_id`
- `review_run_id`
- `job_type`
- `mode`
- `head_sha`
- `adapter_name`
- `rule_no`
- `fingerprint`
- `thread_ref`
- `error_category`

### 18.2 핵심 메트릭

- `review_runs_total`
- `review_run_duration_seconds`
- `detector_candidates_total`
- `eligible_findings_total`
- `published_findings_total`
- `suppressed_findings_total`
- `anchor_failures_total`
- `duplicate_suppression_total`
- `thread_resolved_total`
- `feedback_events_total`
- `publish_failures_total`

### 18.3 재시도 정책

- network timeout, 5xx, rate limit은 transient로 분류
- invalid anchor, missing diff refs, validation failure는 non-transient로 분류
- transient는 exponential backoff 적용
- non-transient는 즉시 `failed_publication` 또는 `suppressed` 처리

### 18.4 토큰과 권한

GitLab service account는 최소 아래 scope를 갖는다.

- MR diff 조회
- discussion 조회/생성/갱신
- 상태 게시

운영 원칙:

- bot user를 사람과 구분 가능한 계정으로 운용
- token scope는 가능한 한 최소화
- project별 bot install 또는 허용 목록 기반 운영

### 18.5 데이터 보관

제안:

- raw webhook payload: 7일
- diff snippet/evidence: 30일
- decision/publication/thread/feedback 메타데이터: 장기 보존

## 19. 마이그레이션 전략

### 19.1 Phase 1: 병행 스키마 도입

- 신규 테이블 추가
- 기존 `pr_id` 경로 유지
- 신규 `ReviewRequestKey`를 side-write
- observability 필드 추가

### 19.2 Phase 2: adapter v2 전환

- GitLab adapter v2 구현
- fetch meta / list threads / upsert / feedback 수집 추가
- publication path를 new table 기반으로 전환

### 19.3 Phase 3: scoring / sync cutover

- dedupe와 suppression을 `FindingDecision` 중심으로 전환
- thread reconcile과 feedback collector 활성화
- current-state `ReviewFinding.status` 의존 제거

### 19.4 Phase 4: package boundary 정리

- `app` namespace 분리
- service별 package rename
- 테스트와 CI 명령 정리

### 19.5 롤백 전략

- current publish path를 feature flag로 유지
- adapter v2도 create-only mode와 upsert mode를 분리
- feedback collector는 read-only부터 시작

## 20. 테스트 전략

### 20.1 단위 테스트

- fingerprint stability
- anchor validation
- score calculation
- suppression policy
- thread state mapping

### 20.2 계약 테스트

- detector manifest contract
- adapter v2 contract
- GitLab inline discussion create/update/resolve contract

### 20.3 통합 테스트

- webhook -> run -> detect -> publish -> sync end-to-end
- update without new commit ignore
- large diff patch reconstruction
- inline anchor failure no-general-note policy
- multi-project 동일 `iid` 충돌 방지

### 20.4 평가 harness

gold diff corpus를 유지한다.

필수 평가지표:

- publish precision proxy
- repeated false positive ratio
- resolved-after-publish ratio
- stale thread cleanup latency

## 21. 수용 기준

이 설계가 구현되었다고 판단하는 최소 기준은 다음과 같다.

- `ReviewRequestKey` composite identity가 실제 persistence와 adapter 경로에 반영됨
- `ReviewSystemAdapterV2`가 GitLab에서 동작함
- `detect -> validate -> score -> explain -> publish -> learn` 단계가 코드에서 구분됨
- `manual_only` / `reference_only`가 게시 경로에서 구조적으로 차단됨
- inline discussion이 create뿐 아니라 upsert/resolve까지 지원됨
- thread sync와 feedback collector가 동작함
- package/workspace 경계가 실행 위치와 무관하게 안정적임
- current detector contract failure가 복구되고 regression harness가 추가됨

## 22. 구현 우선순위

1. detector contract 복구
2. composite identity와 신규 스키마 도입
3. GitLab adapter v2 도입
4. publication state / thread sync state 도입
5. score/suppression 재구성
6. feedback collector
7. package boundary 정리

## 23. 열린 이슈

- LLM provider 호출은 `review-bot` 내부에서 할지, 별도 explanation service로 분리할지
- summary comment를 초기 버전에서 유지할지 여부
- GitLab commit status와 checks 유사 모델을 어느 수준까지 추상화할지
- push 폭주 시 auto-pause 정책을 언제 도입할지
- reviewer feedback을 개인 단위로 반영할지 팀 단위로만 반영할지

## 24. 최종 권고

이 설계의 핵심은 "기존 아이디어를 버리는 것"이 아니라 "좋은 MVP를 운영형 계약으로 승격하는 것"이다.

따라서 구현 순서는 다음처럼 가는 것이 가장 안전하다.

- 먼저 detector contract와 identity를 바로잡는다.
- 다음으로 GitLab adapter를 thread lifecycle 기준으로 재설계한다.
- 그 다음 scoring, explanation, feedback loop를 붙인다.

이 순서를 따르면 현재 자산을 최대한 보존하면서도, 실제로 팀이 신뢰할 수 있는 리뷰 봇으로 발전시킬 수 있다.
