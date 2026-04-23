# AGENTS.md

이 문서는 `/home/et16/work/review_system`에서 작업하는 사람이나 AI agent가
매번 다시 찾게 되는 정보만 모아 둔 운영 메모입니다.

목표는 두 가지입니다.

1. 작업을 시작할 때 어디를 먼저 봐야 하는지 바로 알 수 있게 한다.
2. `review-bot` / GitLab / local harness 관련 반복 체크를 놓치지 않게 한다.

## 1. Workspace Map

- `review-engine/`
  - 규칙 검색, diff/code review, ChromaDB 기반 검색 엔진
- `review-bot/`
  - 외부 Git review system adapter, webhook/API, detect/publish/sync lifecycle
- `review-platform/`
  - 로컬 데모와 통합 테스트용 harness
- `ops/`
  - compose, local GitLab, smoke/replay/baseline 스크립트
- `docs/`
  - 현재 구조, API 계약, 운영 절차, 앞으로 할 일

루트 `docker-compose.yml`은 엔진 단독 실행용입니다.
실제 통합 스택은 `ops/docker-compose.yml` 기준으로 봅니다.

## 2. 먼저 확인할 것

작업을 시작할 때 아래 순서로 확인하면 대부분의 컨텍스트를 빠르게 복구할 수 있습니다.

1. 변경 대상이 어디인지 확인
   - `review-engine`, `review-bot`, `review-platform`, `ops`, `docs`
2. `review-bot` 변경이면 먼저 아래 문서를 확인
   - [README.md](/home/et16/work/review_system/README.md:1)
   - [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)
   - [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:1)
   - [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)
   - [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)
3. DB schema를 건드리면 Alembic head를 확인
   - current head: `20260421_000004`
4. GitLab webhook / adapter / thread sync를 건드리면 local GitLab smoke까지 돌릴 준비를 한다
5. local compose를 쓸지, 단위 테스트만 쓸지 먼저 결정한다

## 3. Canonical Invariants

아래는 현재 시스템에서 사실상 고정된 전제입니다. 이 부분을 깨면 문서, 테스트, smoke를 같이 봐야 합니다.

- canonical business identity:
  - `ReviewRequestKey(review_system, project_ref, review_request_id)`
- `project_ref`는 GitLab webhook의 `project.path_with_namespace`가 canonical source입니다
- `review-bot`은 `detect -> publish -> sync` lifecycle을 책임집니다
- `review-platform`은 운영 표준이 아니라 local harness입니다
- GitLab에서는 MR open/update만으로 자동 리뷰하지 않습니다
- GitLab 리뷰 트리거는 MR note의 `@review-bot ...` 또는 `/review-bot ...` 명령입니다
- 현재 지원 명령은 `review`, `full-report`, `backlog`, `help`입니다
- `review-bot`의 verify는 runner-level canonical flow입니다
  - provider 내부 ad hoc verify에 의존하지 않습니다
- Phase A 이후 lifecycle analytics의 source of truth는 mutable state가 아니라 immutable event입니다
- wrong-language detector backlog는 `actionability=fix_detector` 후보만 바로 수정 대상으로 봅니다
- smoke fixture가 만든 wrong-language event는 `synthetic_smoke` 검증 이벤트로 분리합니다

## 4. Important Files

작업 유형별로 제일 먼저 볼 파일입니다.

- API / webhook
  - [review-bot/review_bot/api/main.py](/home/et16/work/review_system/review-bot/review_bot/api/main.py:1)
- detect / publish / sync / verify / lifecycle
  - [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1)
- wrong-language telemetry classification
  - [review-bot/review_bot/analytics/wrong_language.py](/home/et16/work/review_system/review-bot/review_bot/analytics/wrong_language.py:1)
- GitLab adapter
  - [review-bot/review_bot/review_systems/gitlab.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/gitlab.py:1)
- local harness adapter
  - [review-bot/review_bot/review_systems/local_platform.py](/home/et16/work/review_system/review-bot/review_bot/review_systems/local_platform.py:1)
- bot schema / metrics / config
  - [review-bot/review_bot/db/models.py](/home/et16/work/review_system/review-bot/review_bot/db/models.py:1)
  - [review-bot/review_bot/metrics.py](/home/et16/work/review_system/review-bot/review_bot/metrics.py:1)
  - [review-bot/review_bot/config.py](/home/et16/work/review_system/review-bot/review_bot/config.py:1)
- local harness API / git diff
  - [review-platform/app/api/main.py](/home/et16/work/review_system/review-platform/app/api/main.py:1)
  - [review-platform/app/git/diff_service.py](/home/et16/work/review_system/review-platform/app/git/diff_service.py:1)

## 5. Runtime Ports And Services

개별 개발 서버 기본 포트:

- `review-platform`: `18080`
- `review-bot`: `18081`
- `review-engine`: `18082`

local GitLab 기본 포트:

- HTTP: `18929`
- HTTPS: `19443`
- SSH: `12224`

주요 compose 파일:

- 엔진 단독: `/home/et16/work/review_system/docker-compose.yml`
- 통합 스택: `/home/et16/work/review_system/ops/docker-compose.yml`
- local GitLab: `/home/et16/work/review_system/ops/gitlab-local-compose.yml`

환경 변수의 실제 운영 기준은 `ops/.env`이고,
버전 관리 기준 샘플은 [ops/.env.example](/home/et16/work/review_system/ops/.env.example:1)입니다.

주의:

- 코드 default와 `ops/.env.example` 값이 항상 같지는 않습니다
- 예를 들어 `BOT_BATCH_SIZE`는 코드 default가 `10`이지만 예시 env는 `5`입니다
- provider도 코드 default는 `openai`지만 예시 env는 `stub/stub`입니다
- `openai` provider를 실제로 쓰려면 `OPENAI_API_KEY`가 필요합니다
- `BOT_VERIFY_ENABLED` default는 `0`입니다

## 6. Standard Commands

### 단위 / 통합 테스트

`review-bot` 변경 시 최소 권장:

```bash
cd review-bot && uv run pytest tests/test_gitlab_adapter.py -q
cd review-bot && uv run pytest tests/test_review_runner.py -q
cd review-bot && uv run pytest tests/test_integration_phase1_4.py -q
cd review-bot && uv run pytest tests/test_api_queue.py -q
cd review-platform && uv run pytest tests/test_pr_flow.py -q
```

### local GitLab replay / smoke

표준 smoke:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

이 스크립트는 아래를 한 번에 수행합니다.

- local GitLab MR 재시드
- bot 재부착
- baseline review
- 3회 incremental update replay
- 첫 open thread에 human reply 추가
- 같은 thread resolve
- sync 실행
- smoke assertion 검증

`ops/scripts/smoke_local_gitlab_tde_review.sh`는 기존 이름을 위한 compatibility wrapper로 유지합니다.

로컬 GitLab을 처음 띄울 때:

```bash
python3 /home/et16/work/review_system/ops/scripts/bootstrap_local_gitlab_tde_review.py
```

MR만 재구성하고 bot까지 붙일 때:

```bash
python3 /home/et16/work/review_system/ops/scripts/attach_local_gitlab_bot.py
```

clean replay 가능한 baseline으로 다시 맞출 때:

```bash
python3 /home/et16/work/review_system/ops/scripts/replay_local_gitlab_tde_review.py
```

Phase A baseline snapshot:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_review_bot_baseline.py \
  --baseline-kind v0
```

wrong-language telemetry snapshot:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_wrong_language_telemetry.py \
  --window 28d
```

wrong-language detector backlog:

```bash
python3 /home/et16/work/review_system/ops/scripts/build_wrong_language_backlog.py \
  --window 28d
```

mixed-language smoke:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture synthetic-mixed-language
```

이 smoke는 `markdown + yaml + sql + FastAPI` 조합에서 compact language tag와
wrong-language feedback loop를 함께 검증합니다.
각 fixture의 `expected_smoke.json`은 first batch density contract도 검증합니다.

provider quality gate:

```bash
cd /home/et16/work/review_system/review-bot
uv run python -m review_bot.cli.evaluate_provider_quality --provider stub
```

OpenAI comparison은 `OPENAI_API_KEY`가 있을 때만 opt-in으로 실행하고,
키가 없으면 `skipped` report로 성공 종료합니다.

CUDA targeted smoke:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture cuda-targeted \
  --project-ref root/review-system-cuda-smoke
```

curated polyglot smoke:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture curated-polyglot \
  --project-ref root/review-system-curated-polyglot-smoke
```

## 7. Phase A Trust Foundation Summary

Phase A에서 이미 들어간 핵심 변화입니다. 이 영역을 만지면 관련 문서와 테스트를 같이 봐야 합니다.

- runner-level canonical verify 도입
- 신규 resolution reason
  - `fixed_in_followup_commit`
  - `remote_resolved_manual_only`
- immutable lifecycle history
  - `finding_lifecycle_events`
- analytics endpoint 추가
  - `GET /internal/analytics/finding-outcomes`
- local harness도 incremental diff `base_sha`를 지원

관련 문서:

- [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)
- [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)
- [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)

## 8. GitLab-Specific Gotchas

최근에 실제로 다시 확인할 가치가 높았던 항목입니다.

### 8.1 Note Hook head race

GitLab에서 force-push 직후 곧바로 `@review-bot review` note가 들어오면,
webhook payload의 `merge_request.last_commit.id`가 잠깐 이전 head를 가리킬 수 있습니다.

현재 완화 방식:

- webhook 처리 시 source branch의 현재 head를 다시 조회해 stale head를 보정합니다
- detect phase 시작 시 expected head와 GitLab MR diff head가 다르면 짧게 settle retry 합니다

그래서 GitLab webhook이나 head handling을 건드리면,
반드시 `ops/scripts/smoke_local_gitlab_lifecycle_review.sh`까지 다시 돌려야 합니다.

### 8.2 analytics endpoint 404

`/internal/analytics/finding-outcomes`가 `404`면 코드가 없는 것이 아니라,
대부분은 실행 중인 `review-bot-api` 프로세스가 예전 이미지/예전 코드입니다.

확인 순서:

1. 현재 서비스가 새 코드로 재기동됐는지 확인
2. migration이 반영됐는지 확인
3. `review-bot-api`, `review-bot-worker`를 다시 올림

### 8.3 migration 운영 규칙

운영 표준은 startup에 기대지 말고 Alembic을 먼저 반영하는 것입니다.

예시:

```bash
docker compose exec review-bot-api uv run alembic upgrade head
docker compose up -d review-bot-api review-bot-worker
curl http://127.0.0.1:18081/health
```

## 9. Useful API Checks

상태 확인:

```bash
curl http://127.0.0.1:18081/health
curl http://127.0.0.1:18081/metrics
```

review request 상태 확인:

```bash
curl http://127.0.0.1:18081/internal/review/requests/gitlab/root/review-system-smoke/14
```

analytics:

```bash
curl http://127.0.0.1:18081/internal/analytics/rule-effectiveness
curl "http://127.0.0.1:18081/internal/analytics/finding-outcomes?window=28d"
curl "http://127.0.0.1:18081/internal/analytics/wrong-language-feedback?window=28d"
```

## 10. Last Known Good Validation Path

다음 경로는 실제로 끝까지 성공한 표준 검증 흐름입니다.

- `review-bot` 핵심 테스트 4종
- `review-platform` 테스트
- `ops/scripts/smoke_local_gitlab_lifecycle_review.sh`
- `review-bot` provider quality gate
- `ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture synthetic-mixed-language`
- 필요 시 `ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture curated-polyglot`
- 필요 시 `ops/scripts/smoke_local_gitlab_multilang_review.sh --fixture cuda-targeted`

GitLab smoke 성공 기준:

- baseline review 성공
- 3회 incremental replay 성공
- 마지막 replay head가 최신 SHA로 반영됨
- human reply / resolve / sync 이후 feedback 수가 증가함
- resolve 이후 open thread 수가 감소함

## 11. When To Update This File

아래가 생기면 `AGENTS.md`도 같이 갱신하는 편이 좋습니다.

- 새 canonical doc가 생겼을 때
- 테스트 또는 smoke 표준 명령이 바뀌었을 때
- 운영상 반복 확인하는 함정이 새로 발견됐을 때
- 서비스 포트 / compose 경로 / env key가 바뀌었을 때
- migration head revision이 바뀌었을 때
