# Review Bot Security And Retention

## 목적

이 문서는 self-hosted 기준의 bot 운영 보안과 retention 정책을 고정한다.

## Token Scope

GitLab token 최소 권한 원칙:

- MR metadata read
- diff read
- discussion read/write
- commit status write

불필요한 범위:

- admin scope
- unrelated project write

## Secret 주입

권장 순서:

1. `.env`는 local/dev 전용
2. shared staging/prod는 secret manager 또는 orchestrator secret 사용
3. token rotation 시 bot 재기동 전에 새 secret을 주입하고 smoke를 수행

핵심 secret:

- `GITLAB_TOKEN`
- `GITLAB_WEBHOOK_SECRET`
- `OPENAI_API_KEY`

## Rotation

1. 새 token 발급
2. runtime secret 교체
3. `review-bot-api`, `review-bot-worker` 재기동
4. `GET /health` 확인
5. smoke 실행
6. 기존 token revoke

## Data Retention

기본 권고:

- `review_runs`: 90일
- `finding_evidences` / `finding_decisions`: 90일
- `publication_states`: 90일
- `thread_sync_states`: open thread는 유지, resolved/stale는 180일
- `feedback_events`: 180일
- `dead_letter_records`: 30일

이유:

- feedback learning에는 단기~중기 history가 필요하다.
- dead-letter는 복구 후 오래 보관할 필요가 작다.

## Log Retention

권고:

- structured app log: 30일
- error 중심 인덱스: 90일

필수 마스킹:

- token
- webhook secret
- raw credential

## Cache Retention

- MR cache / file cache는 process memory cache로만 유지한다.
- bot 재기동 시 cache는 초기화된다.
- 장기 persistence cache는 current-state 기본 구성에 포함하지 않는다.

## 감사 포인트

정기 점검 항목:

- bot 계정 권한 과대 여부
- token 만료/rotation 상태
- log에 secret 노출 여부
- dead-letter 누적량과 원인
