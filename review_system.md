# Review System Workspace Notes

이 파일은 과거 MVP 명세 문서를 대체하는 현재 기준 메모입니다.

## Canonical 구성

- `review-engine/`
  - 규칙 pack/profile/policy를 적재하고 retrieval을 수행합니다.
- `review-bot/`
  - detect -> publish -> sync lifecycle과 GitLab/local harness adapter를 담당합니다.
- `review-platform/`
  - 운영 표준이 아니라 로컬 통합 검증용 harness입니다.
- `ops/`
  - compose, local GitLab, smoke/replay 스크립트를 제공합니다.

## 현재 공식 진입점

- 엔진 적재: `cd review-engine && uv run python -m review_engine.cli.ingest_guidelines`
- 엔진 API: `cd review-engine && uv run uvicorn review_engine.api.main:app --reload --port 18082`
- 봇 API: `cd review-bot && uv run uvicorn review_bot.api.main:app --reload --port 18081`
- 루트 compose: `docker compose up --build`
  - 엔진 단독 실행용이며 `review-engine/` 이미지를 직접 사용합니다.

## 문서 우선순위

현재 동작/운영 기준은 아래 문서를 우선합니다.

- [README.md](/home/et16/work/review_system/README.md:1)
- [docs/README.md](/home/et16/work/review_system/docs/README.md:1)
- [docs/CURRENT_SYSTEM.md](/home/et16/work/review_system/docs/CURRENT_SYSTEM.md:1)
- [docs/ROADMAP.md](/home/et16/work/review_system/docs/ROADMAP.md:1)
- [docs/API_CONTRACTS.md](/home/et16/work/review_system/docs/API_CONTRACTS.md:1)
- [docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)
- [AGENTS.md](/home/et16/work/review_system/AGENTS.md:1)

루트 legacy `app/`, 루트 `tests/`, 루트 `data/`는 더 이상 공식 public surface가 아닙니다.
