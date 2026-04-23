# 리뷰 시스템

기존 Git PR/MR 시스템에 리뷰 엔진과 리뷰 봇을 붙여 자동 리뷰를 수행하는 워크스페이스입니다.

현재 공식 public surface는 아래 다섯 경로입니다.

- `review-engine/`: 규칙 적재, 검색, diff/code 리뷰 엔진
- `review-bot/`: webhook/API, detect/publish/sync lifecycle
- `review-platform/`: 로컬 데모와 통합 테스트용 harness
- `ops/`: compose, local GitLab, smoke/replay 운영 스크립트
- `docs/`: API 계약, 운영 절차, migration/cutover, 설계 문서

루트 legacy `app/` 경로는 retire 되었고, 실행/개발 명령은 각 서브프로젝트 기준으로 사용합니다.

## 빠른 시작

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

루트 `docker-compose.yml`은 엔진 단독 실행용 thin entrypoint 입니다.

```bash
docker compose up --build
```

이 명령은 루트 legacy `app/`가 아니라 `review-engine/` 이미지를 직접 빌드합니다.

통합 스택은 `ops/docker-compose.yml`을 기준으로 사용합니다.

## 운영 기준 문서

- [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)
- [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)
- [docs/GITLAB_TDE_REVIEW_SETUP.md](/home/et16/work/review_system/docs/GITLAB_TDE_REVIEW_SETUP.md:1)
- [AGENTS.md](/home/et16/work/review_system/AGENTS.md:1)
