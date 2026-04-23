# 운영 실행 가이드

## 목적

이 문서는 `review-engine`과 `review-bot`을 기준으로,
기존 Git 리뷰 시스템에 bot을 붙이는 현재 운영 방식을 설명한다.

`review-platform`은 로컬 데모와 통합 테스트용 harness다.

## 1. 실행 모드

### 로컬 harness 모드

- `REVIEW_SYSTEM_ADAPTER=local_platform`
- `review-platform` 포함 실행
- bare repo와 로컬 PR로 전체 흐름 검증

### 외부 GitLab 연동 모드

- `REVIEW_SYSTEM_ADAPTER=gitlab`
- GitLab MR note webhook / discussion / status 사용
- `review-platform`은 선택 사항

## 2. Compose 실행

```bash
cd /home/et16/work/review_system/ops
cp .env.example .env
docker compose up --build
```

권장 `.env` 기본값:

```bash
HOST_UID=1000
HOST_GID=1000
PLATFORM_CLONE_BASE_URL=/home/et16/work/review_system/review-platform/storage/repos
REVIEW_SYSTEM_ADAPTER=local_platform
REVIEW_SYSTEM_BASE_URL=http://review-platform:18080
BOT_PROVIDER=stub
BOT_FALLBACK_PROVIDER=stub
BOT_QUEUE_DETECT_NAME=review-detect
BOT_QUEUE_PUBLISH_NAME=review-publish
BOT_QUEUE_SYNC_NAME=review-sync
BOT_ENGINE_TIMEOUT_SECONDS=30
BOT_ENGINE_MAX_RETRIES=2
BOT_ENGINE_RETRY_BACKOFF_SECONDS=0.5
BOT_BATCH_SIZE=5
BOT_GITLAB_API_TIMEOUT_SECONDS=30
BOT_GITLAB_API_MAX_RETRIES=2
BOT_GITLAB_API_RETRY_BACKOFF_SECONDS=0.5
BOT_FEEDBACK_RESOLVED_PENALTY=0.08
BOT_FEEDBACK_REPLY_PENALTY=0.05
BOT_FEEDBACK_REPLY_SUPPRESSION_THRESHOLD=2
BOT_RULE_FAMILY_CAP=2
BOT_DEAD_LETTER_ENABLED=1
BOT_OPENAI_TIMEOUT_SECONDS=10
BOT_OPENAI_MAX_RETRIES=0
BOT_AUTHOR_NAME=review-bot
BOT_VERIFY_ENABLED=0
BOT_VERIFY_CONFIDENCE_THRESHOLD=0.85
BOT_VERIFY_SCORE_BAND=0.10
```

기본 포트:

- `review-platform`: `http://127.0.0.1:18080`
- `review-bot-api`: `http://127.0.0.1:18081`
- `review-engine`: `http://127.0.0.1:18082`
- `chroma`: `http://127.0.0.1:18083`
- `nginx`: `http://127.0.0.1:18084`

## 3. OpenAI / Codex provider 설정

실제 LLM 설명 생성기를 켜려면 `.env`에서 아래를 지정한다.

```bash
BOT_PROVIDER=openai
BOT_FALLBACK_PROVIDER=stub
BOT_OPENAI_MODEL=gpt-5.2
BOT_OPENAI_TIMEOUT_SECONDS=10
BOT_OPENAI_MAX_RETRIES=0
OPENAI_API_KEY=...
```

운영 기본 정책:

1. OpenAI provider를 먼저 시도한다.
2. structured output이 실패하거나 quota 문제가 있으면 stub로 fallback 한다.
3. detect / publish / sync lifecycle은 가능한 한 계속 진행한다.

verify phase 기본값:

- `BOT_VERIFY_ENABLED=0`
- `BOT_VERIFY_CONFIDENCE_THRESHOLD=0.85`
- `BOT_VERIFY_SCORE_BAND=0.10`

의미:

- 기본값에서는 canonical verify가 꺼져 있다.
- 켜면 publish 직전 runner-level verify가 동작한다.
- `execution_error`는 fail-open으로 처리되어 게시를 막지 않는다.

선택적으로 path/rule 정책 파일을 연결할 수 있다.

```bash
BOT_POLICY_PATH=/home/et16/work/review_system/ops/review-bot-policy.example.json
```

예제 파일:

- `ops/review-bot-policy.example.json`

## 4. GitLab 연동 설정

GitLab Self-Managed 또는 사내 GitLab에 붙일 때 `.env`에 아래를 넣는다.

```bash
REVIEW_SYSTEM_ADAPTER=gitlab
REVIEW_SYSTEM_BASE_URL=https://gitlab.example.com
GITLAB_TOKEN=...
GITLAB_WEBHOOK_SECRET=...
BOT_AUTHOR_NAME=review-bot
```

의미:

- `REVIEW_SYSTEM_BASE_URL`
  - GitLab base URL
- `GITLAB_TOKEN`
  - MR 메타 조회, diff 조회, discussion 게시, status 게시에 쓰는 token
- `GITLAB_WEBHOOK_SECRET`
  - GitLab webhook 검증용 secret
- `BOT_AUTHOR_NAME`
  - discussion note를 bot/human으로 구분할 때 쓰는 GitLab username
- `BOT_BATCH_SIZE`
  - 한 번의 리뷰 run에서 게시할 기본 최대 댓글 수

주의:

- `GITLAB_PROJECT_ID`는 더 이상 사용하지 않는다.
- project identity는 webhook payload의 `project.path_with_namespace`가 canonical source다.
- 코드 default batch cap은 `10`이지만 `ops/.env.example`과 local GitLab smoke 기본값은 `5`다.
  따라서 기본 smoke fixture의 density contract도 first batch 최대 `5`개를 기준으로 검증한다.

### GitLab webhook 등록

GitLab 프로젝트 설정에서 note webhook을 아래 URL로 보낸다.

```text
http://<bot-host>:18081/webhooks/gitlab/merge-request
```

권장 이벤트:

- Note events

현재 지원 조건:

- Merge Request note
- comment body에 `@review-bot`

추가 정책:

- MR open/update 자체로는 더 이상 자동 리뷰하지 않는다.
- `@review-bot` mention comment가 들어왔을 때만 현재 MR 전체 diff 기준으로 리뷰를 실행한다.
- detect phase는 현재 discussion snapshot과 feedback를 먼저 반영한다.
- batch cap이 작아도 기존 open thread의 실제 update는 새 finding보다 먼저 처리한다.
- body/anchor 변화가 없는 기존 open thread는 `skipped` publication으로 남기고, batch slot은 소모하지 않는다.
- resolved thread가 다시 eligible하면 full reconcile에서 기존 thread를 reopen/update 한다.
- human reply에 `bot:ignore`가 있으면 동일 fingerprint를 suppress 한다.
- human reply에 `bot:allow`가 있으면 score penalty를 일부 상쇄한다.
- resolve/reopen lifecycle은 `finding_lifecycle_events`에 immutable history로 남는다.
- 수동 resolve와 실제 follow-up fix는 `remote_resolved_manual_only` / `fixed_in_followup_commit`로 구분된다.

## 5. 리뷰 엔진 적재

`review-engine` 컨테이너가 올라간 뒤 한 번 적재를 수행한다.

```bash
docker compose exec review-engine uv run python -m review_engine.cli.ingest_guidelines
```

산출물:

- active dataset: `review-engine/data/active_guideline_records.json`
- reference dataset: `review-engine/data/reference_guideline_records.json`
- excluded dataset: `review-engine/data/excluded_guideline_records.json`

Chroma 컬렉션:

- `guideline_rules_active_<language>`
- `guideline_rules_reference_<language>`
- `guideline_rules_excluded_<language>`

예를 들어 기본 `cpp` 컬렉션은 `guideline_rules_active_cpp`,
`guideline_rules_reference_cpp`, `guideline_rules_excluded_cpp`다.

선택적으로 codebase similarity 검색을 쓰려면 reviewable file chunk를 별도 collection에 적재한다.

```bash
curl -X POST http://127.0.0.1:18082/codebase/index \
  -H "Content-Type: application/json" \
  -d '{"root_path":"/home/et16/work/review_system","clear_first":true}'
```

주의:

- 기본 collection 이름은 `codebase_chunks`다.
- 현재 이 collection은 project-scoped memory가 아니라 engine instance 단위 shared collection이다.
- 허용 root는 `REVIEW_ENGINE_CODEBASE_ALLOWED_ROOTS`로 제한할 수 있다.

## 6. 로컬 harness 검증

로컬 데모 모드에서는 아래 흐름으로 확인한다.

1. 플랫폼에서 저장소 생성
2. bare repo에 `main`과 feature 브랜치 push
3. 로컬 PR 생성
4. `review-bot` 실행
5. inline comment / status / state 조회 확인

이 모드는 외부 시스템 연동 전, engine/bot 흐름을 빠르게 확인하기 위한 용도다.

## 6-a. Baseline 수집

Phase A 이후 운영 baseline은 아래 스크립트로 Markdown snapshot을 남긴다.

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_review_bot_baseline.py \
  --baseline-kind v0
```

프로젝트 단위로 좁히려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_review_bot_baseline.py \
  --baseline-kind v1 \
  --project-ref group/project \
  --source-family cpp_core
```

기본 저장 위치:

- `docs/baselines/review_bot/`

수집 항목:

- `/health`
- `/internal/analytics/rule-effectiveness`
- `/internal/analytics/finding-outcomes?window=14d`
- `/internal/analytics/finding-outcomes?window=28d`
- `/internal/analytics/wrong-language-feedback?window=28d`
- `/metrics` 중 Phase A 관련 counter snapshot

wrong-language telemetry 해석 기준:

- `top_language_pairs`로 가장 자주 틀리는 detect 조합을 본다.
- `top_profiles`로 framework/profile/context 오분류 집중 구간을 본다.
- `top_paths`로 `.github/workflows`, `src`, `db`, `docs` 같은 경로 기반 blind spot을 본다.
- `triage_candidates`의 `provenance`, `triage_cause`, `actionability`를 함께 본다.
- detector backlog로 바로 옮길 후보는 기본적으로 `actionability=fix_detector`뿐이다.
- `root/review-system-multilang-smoke`, `root/review-system-curated-polyglot-smoke`, `root/review-system-cuda-smoke` 같은 smoke project의 wrong-language event는 `synthetic_smoke` 검증 이벤트다.
- project filter 없이 전체 window를 보면 smoke event와 실제 운영 피드백이 섞일 수 있다.
- `wrong_thread_target`은 사람이 다른 thread에 reply했거나 expected language가 잘못 지정됐을 가능성을 먼저 확인한다.
- `policy_mismatch`는 detector보다 policy 또는 fixture contract를 먼저 맞춘다.

standalone wrong-language telemetry snapshot이 필요하면:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_wrong_language_telemetry.py \
  --window 28d
```

특정 프로젝트만 보려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/capture_wrong_language_telemetry.py \
  --project-ref root/review-system-multilang-smoke \
  --window 28d
```

위 smoke project 예시는 telemetry flow 확인용이다. 운영 detector backlog를 만들 때는 실제 서비스 project_ref로 필터링하거나 smoke project를 해석에서 제외한다.

telemetry를 바로 detector backlog 형태로 정리하려면:

```bash
python3 /home/et16/work/review_system/ops/scripts/build_wrong_language_backlog.py \
  --window 28d \
  --min-count 1
```

backlog script의 기본 section:

- `Detector Fix Candidates`: `actionability=fix_detector`인 detector 수정 후보
- `Likely Wrong Thread Target`: detector 수정 전 thread 대상 확인이 필요한 후보
- `Policy Or Fixture Candidates`: policy 또는 fixture expectation 정리가 우선인 후보
- `Synthetic Smoke Events`: telemetry loop 검증용 이벤트

필요한 경우:

```bash
python3 /home/et16/work/review_system/ops/scripts/build_wrong_language_backlog.py \
  --window 28d \
  --min-count 1 \
  --show-needs-inspection
```

## 7. 로컬 GitLab E2E 검증

### 1. GitLab과 테스트 MR 준비

```bash
python3 ops/scripts/bootstrap_local_gitlab_tde_review.py
```

이 스크립트는 로컬 GitLab을 올리고, 프로젝트와 `tde_first -> tde_base` MR을 준비한다.

### 2. Bot 부착

```bash
python3 ops/scripts/attach_local_gitlab_bot.py \
  --project-ref root/review-system-smoke \
  --mr-iid 1
```

이 스크립트는 아래를 자동으로 수행한다.

- review-bot 전용 GitLab 사용자와 token 준비
- webhook 등록
- bot DB 초기화
- 필요 시 초기 `@review-bot` mention comment 게시
- `GET /internal/review/requests/gitlab/{project_ref}/{mr_iid}` polling

### 2-a. clean replay reset/reseed

기존 검증 이력 때문에 MR discussion 상태가 섞였으면 아래 스크립트로
baseline MR과 bot 상태를 다시 고정한다.

```bash
python3 ops/scripts/replay_local_gitlab_tde_review.py
```

baseline과 bot 초기 리뷰를 다시 세팅한 뒤,
내장된 incremental 검증 시퀀스까지 재생하려면:

```bash
python3 ops/scripts/replay_local_gitlab_tde_review.py \
  --replay-default-updates
```

표준 smoke 검증 명령은 아래 wrapper를 사용한다.

```bash
bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

이 명령은 baseline reset/reseed, 각 단계의 `@review-bot` mention 요청, default incremental replay,
human reply + resolve, `/sync` 호출, smoke invariant 검증까지 한 번에 수행한다.
기존 `smoke_local_gitlab_tde_review.sh`는 compatibility wrapper로 남긴다.

권장 사용 시점:

- bot/refactor merge 전 smoke
- GitLab adapter, scoring, sync, feedback collector 변경 직후 smoke
- 야간 또는 수동 pre-release smoke

비권장:

- 모든 PR마다 기본 CI로 실행

이유:

- local GitLab bootstrap과 bot rebuild 비용이 커서 일반 PR CI에는 무겁다.

JSON artifact를 남기고 싶으면:

```bash
bash ops/scripts/smoke_local_gitlab_lifecycle_review.sh \
  --json-output /tmp/review-bot-smoke.json
```

framework/product/config 축까지 함께 검증하는 mixed-language smoke는 아래 wrapper를 사용한다.

```bash
bash ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture synthetic-mixed-language \
  --json-output /tmp/review-bot-multilang-smoke.json
```

이 시나리오는 아래를 한 번에 검증한다.

- `markdown + yaml + sql + FastAPI` 조합 MR 생성
- compact language tag(`[봇 리뷰][yaml]`, `[봇 리뷰][sql]`, `[봇 리뷰][python]`) 확인
- markdown 파일에 대해 엉뚱한 `cpp` 태그가 붙지 않는지 확인
- `@review-bot wrong-language markdown` reply 후 telemetry 집계 확인

CUDA targeted profile까지 검증하려면:

```bash
bash ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture cuda-targeted \
  --project-ref root/review-system-cuda-smoke \
  --json-output /tmp/review-bot-cuda-smoke.json
```

Go/Dockerfile/Kubernetes 조합의 curated polyglot profile을 검증하려면:

```bash
bash ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture curated-polyglot \
  --project-ref root/review-system-curated-polyglot-smoke \
  --json-output /tmp/review-bot-curated-polyglot-smoke.json
```

운영 노트:

- mixed-language smoke는 comment/tag/routing 검증을 안정적으로 하기 위해 실행 중에 provider를 일시적으로 `stub/stub`로 전환한다.
- 기본 경로는 smoke 종료 시 원래 provider env로 복구한다.
- 디버깅 중에는 `--skip-provider-restore`를 써서 반복 rebuild 비용을 줄일 수 있다.
- fixture의 `density_contract`는 bot comment 총량, 최소 distinct file path 수, path별 최대 comment 수를 검증한다.
- fixture의 `wrong_language_feedback`은 의도적으로 human reply를 추가해 analytics loop를 검증한다. 이 결과를 운영 detector miss로 바로 분류하지 않는다.

provider quality gate:

```bash
cd /home/et16/work/review_system/review-bot
uv run python -m review_bot.cli.evaluate_provider_quality \
  --provider stub
```

provider/ranking/density baseline을 남길 때는 provider quality gate 결과와 smoke fixture density
contract 검증 결과를 함께 기록한다.

```bash
cd /home/et16/work/review_system/review-bot
uv run pytest tests/test_multilang_smoke_fixture.py tests/test_provider_quality.py -q
uv run python -m review_bot.cli.evaluate_provider_quality \
  --provider stub \
  --output ../docs/baselines/review_bot/provider_quality_stub_$(date -u +%F).md
cd /home/et16/work/review_system
bash ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture synthetic-mixed-language \
  --json-output /tmp/review-bot-multilang-smoke.json
```

OpenAI provider 비교 artifact가 필요하면 API key가 있는 환경에서만 실행한다.
`OPENAI_API_KEY`가 없으면 명령은 `skipped` report를 출력하고 성공 종료한다.

```bash
cd /home/et16/work/review_system/review-bot
OPENAI_API_KEY=... uv run python -m review_bot.cli.evaluate_provider_quality \
  --provider openai \
  --output ../docs/baselines/review_bot/provider_quality_openai_$(date -u +%F).md
```

선택적으로 첫 open bot thread에 human reply / resolve / sync까지 포함할 수 있다.

```bash
python3 ops/scripts/replay_local_gitlab_tde_review.py \
  --replay-default-updates \
  --reply-first-open-thread \
  --resolve-first-open-thread \
  --trigger-sync-after-thread-actions
```

### 3. 상태 확인

```bash
curl http://127.0.0.1:18081/health
docker compose logs -f review-bot-api
docker compose logs -f review-bot-worker
```

structured log 핵심 필드:

- `review_request_key`
- `review_run_id`
- `mode`
- `trigger`
- `head_sha`
- `error_category`
- `retryable`

설정 확인:

```bash
docker compose exec review-bot-api python - <<'PY'
from review_bot.config import get_settings
s = get_settings()
print({
    "adapter": s.review_system_adapter_name,
    "base_url": s.review_system_base_url,
    "detect_queue": s.queue_detect_name,
    "publish_queue": s.queue_publish_name,
    "sync_queue": s.queue_sync_name,
    "provider": s.provider_name,
    "fallback": s.fallback_provider_name,
    "bot_author_name": s.bot_author_name,
})
PY
```

## 8. 내부 API 사용 예시

### detect run 생성

```bash
curl -X POST http://127.0.0.1:18081/internal/review/runs \
  -H "Content-Type: application/json" \
  -d '{
    "key": {
      "review_system": "gitlab",
      "project_ref": "root/review-system-smoke",
      "review_request_id": "1"
    },
    "trigger": "manual",
    "mode": "full"
  }'
```

### review request 상태 조회

```bash
curl http://127.0.0.1:18081/internal/review/requests/gitlab/root%2Freview-system-smoke/1
```

## 9. 현재 주의사항

1. 현재 구조의 publish 단위는 inline discussion 중심이며, weak anchor는 general note로 fallback하지 않고 suppress 한다.
2. feedback collector는 GitLab discussion 기준 `resolved`, `unresolved`, `reply`만 수집한다.
3. `review-platform`은 운영 필수 구성요소가 아니다.
4. current-state의 canonical identity는 `ReviewRequestKey`이며, legacy `pr_id` endpoint는 제거되었다.
5. wrong-language analytics는 repeated reply event를 count에 포함할 수 있으므로 `distinct_threads`와 `distinct_findings`를 함께 봐야 한다.

## 10. Dead Letter / 복구

재시도로도 해결되지 않은 외부 오류나 enqueue 실패는 `dead_letter_records`에 남는다.

주요 category:

- `engine_timeout`
- `engine_api`
- `engine_transport`
- `gitlab_timeout`
- `gitlab_api`
- `gitlab_transport`
- `inline_anchor`
- `queue`
- `unexpected`

예시 조회:

```bash
docker compose exec postgres psql -U review -d review -c \
  "select stage, error_category, replayable, review_request_id, created_at from dead_letter_records order by created_at desc limit 20;"
```

운영 복구 원칙:

1. `replayable=true`이고 원인이 일시적 장애면 `POST /internal/review/runs/{run_id}/publish` 또는 `/sync`로 재실행한다.
2. `inline_anchor`면 diff anchor 또는 publish scope 문제로 보고 규칙/anchor를 수정한다.
3. detect 단계의 engine 오류면 `review-engine` 상태와 모델 입력을 먼저 확인한다.
