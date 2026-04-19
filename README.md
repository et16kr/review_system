# 리뷰 시스템

Altibase 사내 코딩 컨벤션과 호환 가능한 C++ Core Guidelines를 함께 사용하는
사내 우선 C++ 리뷰 엔진과 리뷰 봇 워크스페이스입니다.

운영 목표는 **별도 PR UI를 만드는 것**이 아니라,
**기존 Git PR/MR 리뷰 시스템에 bot을 붙이는 것**입니다.

현재 워크스페이스는 다음 역할로 나뉩니다.

- `review-engine/`: Altibase 우선 규칙셋, 벡터DB, 검색 엔진
- `review-bot/`: 기존 Git 리뷰 시스템 webhook/API에 붙는 자동 리뷰 봇
- `review-platform/`: 로컬 데모와 통합 테스트용 bare Git 기반 harness
- `ops/`: compose 및 배포 자산
- `docs/`: 분리 구조와 API 계약 문서

## 주요 기능

- `CODING_CONVENTION.md`를 규칙 레코드로 파싱합니다.
- 공식 C++ Core Guidelines를 가져와 규칙 레코드로 파싱합니다.
- 사내 정책에 의해 덮어쓰이거나 충돌하는 외부 규칙을 제외합니다.
- active/reference/excluded 규칙셋을 분리해 ChromaDB 컬렉션으로 저장합니다.
- CLI와 FastAPI 서비스로 C++ 코드 또는 diff를 리뷰합니다.

## 설치

```bash
uv sync --extra dev
```

## 가이드라인 적재

```bash
uv run python -m app.cli.ingest_guidelines
```

이 명령은 다음 정규화 산출물을 생성합니다.

- `data/altibase_coding_convention_rules.json`
- `data/cpp_core_guidelines_rules.json`
- `data/active_guideline_records.json`
- `data/reference_guideline_records.json`
- `data/excluded_guideline_records.json`
- `data/chroma/`

## CLI 사용법

C++ 소스 파일 리뷰:

```bash
uv run python -m app.cli.review_cpp_code \
  --file examples/altidev4/queue_perf_memory_and_rc.cpp \
  --top-k 6
```

diff 리뷰:

```bash
uv run python -m app.cli.review_cpp_diff \
  --diff examples/altidev4_diffs/queue_perf_memory_and_rc.diff \
  --top-k 6
```

단일 규칙 조회:

```bash
uv run python -m app.cli.inspect_rule --rule ALTI-MEM-007
uv run python -m app.cli.inspect_rule --rule R.11
```

번들된 예제 기대 결과 평가:

```bash
uv run python -m app.cli.evaluate_examples --top-k 12
```

저장소 내부 실코드 excerpt 메타데이터 확인:

```bash
sed -n '1,200p' examples/altidev4_snippets.json
```

실코드 excerpt 예제는 `examples/altidev4/` 아래에 들어 있으며, 각 파일 상단 주석과
`examples/altidev4_snippets.json`에서 원본 경로와 라인 범위를 확인할 수 있습니다.

## API 사용법

API 서버 시작:

```bash
uv run uvicorn app.api.main:app --reload
```

요청 예시:

```bash
curl -X POST http://127.0.0.1:8000/ingest
curl -X POST http://127.0.0.1:8000/review/code \
  -H "Content-Type: application/json" \
  -d '{"code":"#include <stdio.h>\nvoid bad(){ int* ptr = new int(1); free(ptr); }\n","top_k":5}'
curl http://127.0.0.1:8000/rule/ALTI-MEM-007
```

## 테스트

```bash
uv run pytest
uv run ruff check .
```

테스트는 저장소 내부의 실코드 excerpt와 repo 내 cached guideline 문서만 사용하므로,
외부 `/home/et16/work/altidev4` 경로가 없어도 통과해야 합니다.

## 확장 분석

실제 외부 Altibase 코드베이스 전체를 대상으로 컨벤션 패턴 후보를 스캔하려면 아래
명령을 사용할 수 있습니다.

```bash
uv run python -m app.cli.scan_codebase \
  --root /home/et16/work/altidev4 \
  --include-dir src \
  --include-dir tsrc \
  --include-dir ut \
  --exclude-fragment /src/core/acp/ArmAtomic/ARM64 \
  --exclude-fragment /src/core/acl/externalLib \
  --exclude-fragment /ut/libedit \
  --exclude-fragment /ut/altiMon/com.altibase.picl \
  --exclude-fragment /src/pd/port/vxworks/pentium/sample1 \
  --ignore-pattern identifier_underscore \
  --ignore-pattern ownership_ambiguity \
  --ignore-pattern line_comment \
  --ignore-pattern primitive_types \
  --top-files 40 \
  --json-output data/altidev4_scan_report.json \
  --markdown-output ALTIDEV4_BASELINE_REPORT.md
```

이 기능은 선택 기능이며, 기본 리뷰/예제/테스트 흐름은 저장소 내부 파일만으로 재현됩니다.

## Docker

기존 루트 `docker-compose.yml`은 엔진 단독 실행용입니다.

```bash
docker compose up --build
```

## Workspace 서비스

운영 핵심은 아래 두 서비스입니다.

- `review-engine/`
- `review-bot/`

`review-platform/`은 로컬 데모와 통합 테스트를 위한 harness입니다.

개별 개발 서버 예시:

```bash
cd review-engine && uv run --extra dev uvicorn app.api.main:app --reload --port 18082
cd review-bot && uv run --extra dev uvicorn app.api.main:app --reload --port 18081
```

로컬 harness까지 함께 확인하려면:

```bash
cd review-platform && uv run --extra dev uvicorn app.api.main:app --reload --port 18080
```

통합 compose와 외부 GitLab 연동 예시는 `ops/docker-compose.yml`과
[docs/OPERATIONS_RUNBOOK.md](/home/et16/work/review_system/docs/OPERATIONS_RUNBOOK.md:1)에 정리해 두었습니다.

`altidev4`의 `tde_first -> tde_base`를 GitLab MR로 먼저 올리는 절차는
[docs/GITLAB_TDE_REVIEW_SETUP.md](/home/et16/work/review_system/docs/GITLAB_TDE_REVIEW_SETUP.md:1)에 따로 정리해 두었습니다.
