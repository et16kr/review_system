# Review Bot Migration / Cutover

## 목적

이 문서는 `review-bot` V2 스키마를 shared staging 또는 production에 반영할 때의 기준 절차를 고정한다.

기준:

- runtime schema owner: Alembic
- canonical identity: `ReviewRequestKey(review_system, project_ref, review_request_id)`
- current head revision:
  - `20260421_000004`

## 현재 스키마 구성

핵심 테이블:

- `review_requests`
- `review_runs`
- `finding_evidences`
- `finding_decisions`
- `publication_states`
- `thread_sync_states`
- `feedback_events`
- `finding_lifecycle_events`
- `dead_letter_records`

## Cutover 원칙

1. 로컬/파일럿은 `drop/recreate`를 허용한다.
2. shared staging/prod는 Alembic upgrade만 허용한다.
3. startup 시 schema mismatch가 있으면 API/worker는 migration 이후에만 기동한다.
4. legacy `pr_id` 테이블/endpoint와의 backfill은 기본 범위에서 제외한다.

## 배포 절차

1. 새 이미지 배포 전에 DB backup을 확보한다.
2. Alembic head를 먼저 반영한다.
3. `review-bot-api`, `review-bot-worker`를 순차 재기동한다.
4. `GET /health`와 smoke를 확인한다.

예시:

```bash
docker compose exec review-bot-api uv run alembic upgrade head
docker compose up -d review-bot-api review-bot-worker
curl http://127.0.0.1:18081/health
```

추가 확인:

```bash
curl http://127.0.0.1:18081/internal/analytics/rule-effectiveness
curl "http://127.0.0.1:18081/internal/analytics/finding-outcomes?window=28d"
```

## Backfill 정책

기본 정책은 `no backfill`이다.

이유:

- 기존 `pr_id` 기반 식별자는 `project_ref`를 잃고 있어 정확한 복원 근거가 약하다.
- inline lifecycle, feedback, dead-letter는 V2 모델에 맞춰 다시 수집하는 편이 안전하다.

예외:

- 특정 shared staging에서 꼭 필요한 경우에만 read-only export 후 별도 스크립트로 변환한다.
- 이 경우에도 `feedback_events`와 `dead_letter_records`는 backfill 대상에서 제외한다.

## Schema Version 운영 규칙

- Alembic revision은 append-only로 관리한다.
- 운영 배포는 항상 `head` 기준이다.
- app startup이 migration을 자동 호출하더라도, 운영 표준은 사전 upgrade 후 기동이다.
- rollback은 코드 rollback보다 DB snapshot restore를 우선 검토한다.

## 장애 시 복구

1. migration 실패
   - app 기동 중지
   - Alembic error 원인 확인
   - 필요하면 backup restore
2. app 기동 후 runtime 오류
   - `dead_letter_records`와 `review_run_event` 로그 확인
   - replay 가능한 실패면 publish/sync 재실행
3. schema mismatch
   - 현재 revision 확인 후 `alembic upgrade head`

## Phase A Cutover Notes

- `ThreadSyncState.resolution_reason`는 기존 값과 새 값이 한동안 공존할 수 있다.
- historical `remote_resolved` 데이터는 기본적으로 backfill하지 않는다.
- 새 배포 후 관측되는 resolve event부터 `fixed_in_followup_commit` /
  `remote_resolved_manual_only`가 기록된다.
- `baseline_v1`은 새 analytics window가 충분히 채워진 뒤 기록한다.

## Legacy API 정리

current-state에서 제거된 endpoint:

- `POST /internal/review/pr-opened`
- `POST /internal/review/pr-updated`
- `POST /internal/review/next-batch`
- `GET /internal/review/state/{pr_id}`

대체 경로:

- `POST /internal/review/runs`
- `POST /internal/review/runs/{run_id}/publish`
- `POST /internal/review/runs/{run_id}/sync`
- `GET /internal/review/requests/{review_system}/{project_ref}/{review_request_id}`
