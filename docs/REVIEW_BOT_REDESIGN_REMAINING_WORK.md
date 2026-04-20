# 리뷰 봇 재설계 남은 작업 목록

- 문서 상태: Completed Backlog
- 최종 갱신일: 2026-04-20
- 기준 문서:
  - `docs/REVIEW_BOT_REDESIGN_AUDIT_REPORT.md`
  - `docs/REVIEW_BOT_REDESIGN_DESIGN.md`

## 1. 결론

초기 backlog에 있던 핵심 항목은 현재 차수에서 모두 코드 또는 운영 문서로 내려왔다.

즉, 이 문서는 더 이상 “미완료 작업 목록”이 아니라
“무엇을 완료했고 어디에 정리했는지”를 보여 주는 close-out 문서로 읽으면 된다.

## 2. 완료된 항목

### P0. 파일럿 안정화

- `P0-1 incremental publish 정책`
  - incremental 새 thread는 touched line anchor만 허용
  - untouched file thread는 incremental sync가 닫지 않음
  - 기존 backlog 재노출 억제 정책을 문서와 코드에 고정
- `P0-2 thread lifecycle vs batch`
  - 기존 open/resolved thread의 update/reopen이 새 finding보다 우선
  - unchanged open thread는 `skipped`로 기록하고 batch slot 무소모
  - resolved thread는 full reconcile에서 reopen/update 가능
- `P0-3 clean replay / smoke`
  - baseline reset/reseed
  - default incremental replay
  - human reply / resolve / sync replay
  - smoke invariant 검증과 JSON artifact 출력
- `P0-4 observability`
  - structured log 공통 필드 정리
  - detect/publish/sync 단계별 이벤트 정형화
  - error category / retryable / dead-letter 기록

### P1. 운영형 보강

- `P1-1 feedback learning`
  - resolved / reply history penalty 반영
  - human reply의 `bot:ignore` / `bot:allow` override 반영
  - path/rule 정책 파일 지원
- `P1-2 retry/backoff/dead-letter`
  - GitLab adapter retry/backoff
  - engine client retry/backoff
  - publish/sync/queue follow-up 실패 dead-letter 기록
- `P1-3 migration / cutover`
  - Alembic head와 cutover 절차 문서화
  - no-backfill 기본 정책 문서화
  - schema mismatch 운영 원칙 문서화
- `P1-4 legacy API 정리`
  - legacy `pr_id` endpoint 제거
  - current-state API를 `ReviewRequestKey` 기준으로 정리

### P2. 중기 설계 항목

- `P2-1 adapter capability 정리`
  - GitLab capability와 향후 GitHub/Gerrit 확장 matrix 문서화
- `P2-2 evaluation harness`
  - `review_engine.cli.evaluate_diff_contracts` 추가
  - evaluation harness 문서화
- `P2-3 scoring/policy`
  - rule family cap 설정화
  - path-specific policy 파일 지원
  - feedback 기반 rerank/suppression 반영
- `P2-4 summary/overview`
  - current-state는 inline 중심으로 유지
  - summary output의 역할과 추가 순서를 설계 문서로 고정

### P3. 장기 확장 준비

- `P3-1 multi-SCM 준비`
  - adapter capability matrix 문서화
- `P3-2 self-hosted 보안/retention`
  - token scope, rotation, retention 정책 문서화

## 3. 코드 반영 위치

핵심 코드:

- `review-bot/review_bot/bot/review_runner.py`
- `review-bot/review_bot/review_systems/gitlab.py`
- `review-bot/review_bot/clients/engine_client.py`
- `review-bot/review_bot/worker.py`
- `review-bot/review_bot/policy.py`
- `review-bot/review_bot/errors.py`
- `review-bot/review_bot/api/main.py`
- `review-bot/alembic/versions/20260420_000002_dead_letter_records.py`
- `review-engine/review_engine/cli/evaluate_diff_contracts.py`

운영 스크립트:

- `ops/scripts/replay_local_gitlab_tde_review.py`
- `ops/scripts/smoke_local_gitlab_tde_review.sh`
- `ops/review-bot-policy.example.json`

## 4. 문서 반영 위치

- current-state 계약:
  - `docs/API_CONTRACTS.md`
- 운영:
  - `docs/OPERATIONS_RUNBOOK.md`
  - `docs/GITLAB_TDE_REVIEW_SETUP.md`
- cutover:
  - `docs/REVIEW_BOT_MIGRATION_CUTOVER.md`
- adapter capability:
  - `docs/REVIEW_SYSTEM_ADAPTER_CAPABILITY_MATRIX.md`
- 보안/retention:
  - `docs/REVIEW_BOT_SECURITY_AND_RETENTION.md`
- summary 설계:
  - `docs/REVIEW_BOT_SUMMARY_OUTPUT_DESIGN.md`
- evaluation:
  - `docs/REVIEW_ENGINE_EVALUATION_HARNESS.md`

## 5. 완료 기준 점검

현재 기준으로 아래 항목이 충족된다.

- incremental update가 commit 범위를 벗어난 새 thread를 만들지 않도록 정책이 고정되었다.
- untouched file의 open thread는 incremental sync 때문에 닫히지 않는다.
- 기존 bot thread lifecycle은 batch cap보다 우선한다.
- local GitLab open -> push -> stale resolve -> human reply -> re-sync를 clean replay와 smoke로 재현할 수 있다.
- review-bot 로그와 dead-letter로 run 흐름과 실패 원인을 추적할 수 있다.

## 6. 메모

앞으로도 개선 아이디어는 생길 수 있다. 다만 현재 시점에서
감사 문서와 설계 문서를 기준으로 정의했던 backlog는 모두 소진되었다.

이후 작업은 “남은 필수 작업”이 아니라 새로운 기능 또는 다음 세대 개선 과제로 분리해 다루면 된다.
