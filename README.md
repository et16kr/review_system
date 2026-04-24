# Review System

기존 Git PR/MR 시스템에 rule-backed AI 리뷰를 붙이는 워크스페이스입니다.
목표는 새 코드 리뷰 UI를 만드는 것이 아니라, GitLab 같은 기존 리뷰 화면 안에서
근거 있는 inline comment, backlog, feedback loop, 운영 analytics를 제공하는 것입니다.

현재 기본 운영 모델은 GitLab Merge Request에 `@review-bot review` 또는
`/review-bot review`를 남기면 bot이 diff를 분석하고 inline discussion을 게시하는 방식입니다.
MR open/update만으로는 자동 리뷰를 게시하지 않습니다.

## What It Can Do

- GitLab MR diff를 읽고 rule/retrieval 기반 finding 후보를 만든다.
- 변경 파일별로 language/profile/context/dialect를 판별한다.
- 중요한 finding만 batch cap 안에서 inline discussion으로 게시한다.
- 기존 thread를 update/reopen/resolve하면서 중복 게시를 줄인다.
- `summarize`, `walkthrough`, `full-report`, `backlog`, `help` 명령으로 현재 상태나 전체 현황을 general note로 보여 준다.
- `ignore`, `false-positive`, `later`, `allow`, `wrong-language <lang>` feedback을 수집한다.
- distinct fingerprint 기반 analytics와 immutable lifecycle event로 품질 KPI를 계산한다.
- local GitLab smoke와 fixture 기반 mixed-language smoke로 회귀를 검증한다.
- OpenAI provider 또는 deterministic stub provider를 선택해 draft comment를 생성한다.

## Supported Review Targets

현재 review-engine은 아래 언어와 reviewable artifact를 지원합니다.

- Programming languages: `cpp`, `c`, `cuda`, `python`, `typescript`, `javascript`, `java`, `go`, `rust`, `bash`
- Data/config/build artifacts: `sql`, `yaml`, `dockerfile`
- YAML contexts: GitLab CI, GitHub Actions, Kubernetes, Helm, product config, schema config
- SQL contexts: warehouse/report SQL, dbt, migration SQL, PostgreSQL-oriented dialect hints
- Python/framework profiles: Django, FastAPI
- TypeScript/JavaScript profiles: React, Next.js app/router patterns
- Java/Rust profiles: Spring, Tokio async
- CUDA profiles: default, async runtime, multigpu, tensor core, cooperative groups, pipeline async, thread block cluster, TMA, WGMMA

Markdown 문서는 reviewable source가 아니라 명시적인 unreviewable `markdown`으로 분류합니다.

## Workspace Map

- `review-engine/`: canonical rule pack/profile/policy 적재, retrieval, diff/code review 후보 생성
- `review-bot/`: webhook/API, queue worker, `detect -> publish -> sync` lifecycle
- `review-platform/`: 운영 표준이 아닌 로컬 데모와 통합 테스트용 harness
- `ops/`: compose, local GitLab, smoke/replay/baseline/telemetry 스크립트
- `docs/`: 현재 구조, API 계약, 운영 절차, roadmap

루트 legacy `app/` 경로는 retire 되었고, 실행/개발 명령은 각 서브프로젝트 기준으로 사용합니다.

## Architecture

```text
GitLab MR note
  -> review-bot webhook/API
  -> detect queue
  -> review-engine retrieval/rule evaluation
  -> publish queue
  -> GitLab inline discussions + summary/check
  -> sync queue
  -> feedback/lifecycle analytics
```

Canonical business identity는 `ReviewRequestKey(review_system, project_ref, review_request_id)`입니다.
GitLab에서는 `project_ref`를 webhook payload의 `project.path_with_namespace`에서 가져옵니다.

현재 adapter 구현:

- `gitlab`: GitLab MR discussion/status/general note adapter
- `local_platform`: local harness adapter

GitHub/Gerrit adapter는 roadmap에 있는 확장 후보입니다.

## Quick Start

`review-engine` 적재와 로컬 API:

```bash
cd review-engine
uv sync --extra dev
uv run python -m review_engine.cli.ingest_guidelines
uv run uvicorn review_engine.api.main:app --reload --port 18082
```

`review-bot` 개발 서버:

```bash
cd review-bot
uv sync --extra dev
uv run uvicorn review_bot.api.main:app --reload --port 18081
```

`review-platform` 로컬 harness:

```bash
cd review-platform
uv sync --extra dev
uv run uvicorn app.api.main:app --reload --port 18080
```

## Docker

루트 `docker-compose.yml`은 엔진 단독 실행용 thin entrypoint입니다.

```bash
docker compose up --build
```

통합 스택은 `ops/docker-compose.yml`을 기준으로 사용합니다.

```bash
cd ops
cp .env.example .env
docker compose up --build
```

기본 포트:

- `review-platform`: `18080`
- `review-bot`: `18081`
- `review-engine`: `18082`
- local GitLab HTTP: `18929`

## Common Validation

빠른 단위/통합 회귀:

```bash
cd review-bot && uv run pytest tests/test_multilang_smoke_fixture.py -q
cd review-bot && uv run pytest tests/test_gitlab_adapter.py tests/test_review_runner.py -q
cd review-platform && uv run pytest tests/test_pr_flow.py -q
```

engine rule/retrieval 변경:

```bash
cd review-engine
uv run python -m review_engine.cli.ingest_guidelines
uv run pytest -q
```

local GitLab lifecycle smoke:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_lifecycle_review.sh
```

mixed-language smoke:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture synthetic-mixed-language
```

CUDA targeted smoke:

```bash
bash /home/et16/work/review_system/ops/scripts/smoke_local_gitlab_multilang_review.sh \
  --fixture cuda-targeted \
  --project-ref root/review-system-cuda-smoke
```

## Canonical Docs

- [docs/README.md](/home/et16/work/review_system/docs/README.md:1)
- [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)
- [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:1)
- [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)
- [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)
- [AGENTS.md](/home/et16/work/review_system/AGENTS.md:1)
