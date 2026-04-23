# 리뷰 엔진

공개 rule pack과 선택적 extension을 사용해 코드와 diff를 리뷰하는 검색 엔진입니다.

## 주요 기능

- canonical YAML rule root에서 pack, profile, priority policy를 로드합니다.
- active/reference/excluded 규칙셋을 계산해 ChromaDB에 적재합니다.
- CLI와 FastAPI로 코드 또는 diff를 리뷰합니다.
- extension rule root와 prompt overlay를 합성할 수 있습니다.

## 설치

```bash
uv sync --extra dev
```

## 가이드라인 적재

```bash
uv run python -m review_engine.cli.ingest_guidelines
```

이 명령은 다음 산출물을 생성합니다.

- `data/active_guideline_records.json`
- `data/reference_guideline_records.json`
- `data/excluded_guideline_records.json`
- `data/chroma/`

## CLI 예시

코드 리뷰:

```bash
uv run python -m review_engine.cli.review_cpp_code \
  --file path/to/file.cpp \
  --top-k 6
```

diff 리뷰:

```bash
uv run python -m review_engine.cli.review_cpp_diff \
  --diff path/to/change.diff \
  --top-k 6
```

규칙 조회:

```bash
uv run python -m review_engine.cli.inspect_rule --rule R.11
```

번들된 retrieval 예제 평가:

```bash
uv run python -m review_engine.cli.evaluate_examples --top-k 12
```

## API

```bash
uv run uvicorn review_engine.api.main:app --reload
```

예시:

```bash
curl -X POST http://127.0.0.1:8000/ingest
curl -X POST http://127.0.0.1:8000/review/code \
  -H "Content-Type: application/json" \
  -d '{"code":"#include <stdio.h>\nvoid bad(){ int* ptr = new int(1); free(ptr); }\n","top_k":5}'
curl http://127.0.0.1:8000/rule/R.10
```

## 코드베이스 스캔

대규모 코드베이스에서 패턴 후보를 스캔하려면 아래 명령을 사용합니다.

```bash
uv run python -m review_engine.cli.scan_codebase \
  --root /path/to/codebase \
  --include-dir src \
  --include-dir tests \
  --ignore-pattern identifier_underscore \
  --ignore-pattern ownership_ambiguity \
  --top-files 40 \
  --json-output data/repository_scan_report.json \
  --markdown-output REPOSITORY_SCAN_REPORT.md
```

## 테스트

```bash
uv run pytest -q
uv run ruff check .
```

## Docker

```bash
docker compose up --build
```
