# 운영 실행 가이드

## 목적

이 문서는 `review-engine`, `review-platform`, `review-bot`을 로컬 또는 내부망 환경에서
실제로 띄우는 순서와 운영 기본값을 정리한다.

## 1. Compose로 전체 실행

```bash
cd /home/et16/work/review_system/ops
cp .env.example .env
docker compose up --build
```

기본 포트:

- `review-platform`: `http://127.0.0.1:18080`
- `review-bot-api`: `http://127.0.0.1:18081`
- `review-engine`: `http://127.0.0.1:18082`
- `chroma`: `http://127.0.0.1:18083`
- `nginx`: `http://127.0.0.1:18084`

## 2. OpenAI / Codex provider 설정

기본값은 `stub` provider다. 실제 LLM 코멘트를 켜려면 `.env`에서 아래를 지정한다.

```bash
BOT_PROVIDER=openai
BOT_FALLBACK_PROVIDER=stub
BOT_OPENAI_MODEL=gpt-5.2
OPENAI_API_KEY=...
```

권장 정책:

- 운영 초기는 `BOT_PROVIDER=stub`로 UI/큐/플랫폼 연동을 먼저 검증한다.
- 그 다음 `BOT_PROVIDER=openai`, `BOT_FALLBACK_PROVIDER=stub`로 전환한다.
- OpenAI structured output이 실패하면 자동으로 stub provider로 내려간다.

## 3. 리뷰 엔진 가이드라인 적재

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

## 4. 저장소 seed와 첫 PR 생성

1. 플랫폼에서 저장소를 생성한다.
2. 저장소 경로를 확인한다.
3. 로컬에서 clone 후 `main`과 `feature/*` 브랜치를 push 한다.
4. 플랫폼 화면에서 base/head 브랜치를 선택해 PR을 생성한다.

예시:

```bash
git clone /path/to/storage/repos/sample.git
cd sample
git config user.name "Tester"
git config user.email "tester@example.com"
echo 'int main(){return 0;}' > main.cpp
git add main.cpp
git commit -m "initial"
git push origin main

git checkout -b feature/memory-fix
cat > main.cpp <<'EOF'
int main() {
    char* ptr = (char*)malloc(8);
    free(ptr);
    return 0;
}
EOF
git add main.cpp
git commit -m "memory fix"
git push origin feature/memory-fix
```

그 뒤 웹에서 PR을 생성하고 `봇 리뷰 실행` 버튼을 누르면 된다.

## 5. 작업 큐와 worker

- API는 리뷰 작업을 직접 실행하지 않고 Redis 큐에 넣는다.
- 실제 리뷰는 `review-bot-worker`가 수행한다.
- `다음 5개 게시`도 동일하게 큐 작업으로 처리된다.

상태 확인:

```bash
docker compose logs -f review-bot-worker
docker compose logs -f review-bot-api
```

## 6. Provider fallback 정책

운영 기본 정책:

1. OpenAI provider를 먼저 시도한다.
2. Structured output parsing 실패 시 stub provider로 fallback 한다.
3. finding 계산과 게시 흐름은 계속 진행한다.

이 정책 덕분에 LLM 응답 형식 불안정성이 전체 리뷰 중단으로 이어지지 않는다.

## 7. 주의 사항

- 현재 MVP는 인증/권한 모델 없이 내부망 전용을 기본 가정으로 한다.
- `review-platform`과 `review-bot`은 Postgres를 사용하지만 migration 프레임워크는 아직 없다.
- `review-engine`의 active dataset은 자동 리뷰용이고, reference dataset은 검색/설명용 보조 규칙이다.
