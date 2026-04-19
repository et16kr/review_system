# 운영 실행 가이드

## 목적

이 문서는 `review-engine`과 `review-bot`을 기준으로,
**기존 Git 리뷰 시스템에 bot을 붙이는 운영 방식**을 설명한다.

`review-platform`은 로컬 데모와 통합 테스트용 harness다.

## 1. 실행 모드

### 로컬 harness 모드

- `REVIEW_SYSTEM_ADAPTER=local_platform`
- `review-platform` 포함 실행
- bare repo와 로컬 PR로 전체 흐름 검증

### 외부 Git 리뷰 시스템 연동 모드

- `REVIEW_SYSTEM_ADAPTER=gitlab`
- 외부 GitLab MR을 webhook/API로 사용
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
BOT_OPENAI_TIMEOUT_SECONDS=10
BOT_OPENAI_MAX_RETRIES=0
```

기본 포트:

- `review-platform`: `http://127.0.0.1:18080`
- `review-bot-api`: `http://127.0.0.1:18081`
- `review-engine`: `http://127.0.0.1:18082`
- `chroma`: `http://127.0.0.1:18083`
- `nginx`: `http://127.0.0.1:18084`

## 3. OpenAI / Codex provider 설정

실제 LLM 코멘트를 켜려면 `.env`에서 아래를 지정한다.

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
3. 리뷰 작업 전체는 중단하지 않는다.

## 4. GitLab 연동 설정

GitLab Self-Managed 또는 사내 GitLab에 붙일 때 `.env`에 아래를 넣는다.

```bash
REVIEW_SYSTEM_ADAPTER=gitlab
REVIEW_SYSTEM_BASE_URL=https://gitlab.example.com
GITLAB_TOKEN=...
GITLAB_PROJECT_ID=group%2Frepo
GITLAB_WEBHOOK_SECRET=...
```

의미:

- `REVIEW_SYSTEM_BASE_URL`
  - GitLab base URL
- `GITLAB_TOKEN`
  - MR diff 조회와 댓글 게시에 쓰는 personal access token 또는 bot token
- `GITLAB_PROJECT_ID`
  - 현재 MVP에서는 bot 인스턴스가 담당할 단일 GitLab 프로젝트
- `GITLAB_WEBHOOK_SECRET`
  - GitLab webhook 검증용 secret

### GitLab webhook 등록

GitLab 프로젝트 설정에서 merge request webhook을 아래 URL로 보낸다.

```text
http://<bot-host>:18081/webhooks/gitlab/merge-request
```

권장 이벤트:

- Merge request events

현재 지원 action:

- `open`
- `update`
- `reopen`

## 5. 리뷰 엔진 적재

`review-engine` 컨테이너가 올라간 뒤 한 번 적재를 수행한다.

```bash
docker compose exec review-engine uv run python -m app.cli.ingest_guidelines
```

산출물:

- active dataset: `review-engine/data/active_guideline_records.json`
- reference dataset: `review-engine/data/reference_guideline_records.json`
- excluded dataset: `review-engine/data/excluded_guideline_records.json`

Chroma 컬렉션:

- `guideline_rules_active`
- `guideline_rules_reference`
- `guideline_rules_excluded`

## 6. 로컬 harness 검증

로컬 데모 모드에서는 아래 흐름으로 확인한다.

1. 플랫폼에서 저장소 생성
2. bare repo에 `main`과 feature 브랜치 push
3. 로컬 PR 생성
4. `review-bot` 실행
5. 상위 5개 댓글 확인

이 모드는 외부 시스템 연동 전, engine/bot 흐름을 빠르게 확인하기 위한 용도다.

## 7. GitLab 연동 검증

### 설정 확인

```bash
docker compose exec review-bot-api python - <<'PY'
from app.config import get_settings
s = get_settings()
print({
    "adapter": s.review_system_adapter_name,
    "base_url": s.review_system_base_url,
    "project_id": s.gitlab_project_id,
    "provider": s.provider_name,
    "fallback": s.fallback_provider_name,
})
PY
```

### webhook 수신 확인

```bash
curl http://127.0.0.1:18081/health
docker compose logs -f review-bot-api
docker compose logs -f review-bot-worker
```

## 8. 주의사항

1. 현재 GitLab adapter MVP는 summary note 중심이다.
2. GitLab inline discussion과 commit status는 후속 고도화 항목이다.
3. 현재 bot DB의 `pr_id`는 멀티 프로젝트 키가 아니라 review request ID로 동작한다.
4. 여러 프로젝트를 동시에 붙이려면 bot 인스턴스를 프로젝트별로 나누거나, DB 스키마를 확장해야 한다.
5. `review-platform`은 운영 필수 구성요소가 아니다.
