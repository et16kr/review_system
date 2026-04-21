# 구현 진행 현황

날짜: 2026-04-19

## 아키텍처 정정 메모

이 문서 중 `review-platform` 중심으로 보이는 항목은
초기 local harness 확장 단계의 기록이다.

현재 기준의 운영 아키텍처는 아래를 우선한다.

- 운영 핵심: `review-engine`, `review-bot`
- canonical UI: 기존 Git PR/MR 리뷰 시스템
- `review-platform`: 로컬 데모와 통합 테스트용 harness

최신 기준 문서는 아래를 우선한다.

- `INTERNAL_PR_REVIEW_SYSTEM_EXECUTION_PLAN.md`
- `docs/REVIEW_BOT_REDESIGN_DESIGN.md`
- `docs/API_CONTRACTS.md`
- `docs/OPERATIONS_RUNBOOK.md`

## 목표

`review_system.md`에 정의된 MVP를 다음 운영 원칙에 따라 구현한다.

- `CODING_CONVENTION.md`를 최우선 기준으로 사용한다.
- Altibase 정책과 충돌하는 C++ Core Guideline 규칙은 활성 리뷰 데이터셋에서 제외한다.
- Altibase 규칙과 호환 가능한 C++ 규칙만 함께 ChromaDB에 저장한다.

## 진행 절차

1. 프로젝트 메타데이터, 설정 파일, 추적 문서를 생성한다.
2. Altibase Markdown과 C++ Core Guidelines HTML 파서를 구현한다.
3. 두 소스를 하나의 공통 레코드 스키마로 정규화하고 충돌 해소를 적용한다.
4. 활성 데이터셋을 결정론적 로컬 임베딩과 함께 ChromaDB에 저장한다.
5. 코드-쿼리 변환, 검색, 재랭킹을 구현한다.
6. CLI 명령과 FastAPI 엔드포인트를 추가한다.
7. 예제, 테스트, Docker 자산, README 사용법을 추가한다.
8. 전체 워크플로를 검증하고 완료 보고서를 작성한다.

## 상태

- [x] 1단계 완료: 프로젝트 골격과 추적 문서를 생성했다.
- [x] 2단계 완료: Altibase Markdown 및 C++ Core Guidelines 파서를 구현했다.
- [x] 3단계 완료: 정규화, 소스 권한 정책, 충돌 필터링을 구현했다.
- [x] 4단계 완료: 결정론적 로컬 임베딩 기반 ChromaDB 적재를 구현했다.
- [x] 5단계 완료: 코드-쿼리 변환, 검색, 재랭킹, 패턴-규칙 힌트를 구현했다.
- [x] 6단계 완료: CLI 명령과 FastAPI 엔드포인트를 구현했다.
- [x] 7단계 완료: 샘플 입력, 테스트, Docker 자산, README 사용법을 추가했다.
- [x] 8단계 완료: 검증을 마쳤고 완료 보고서를 작성했다.

## 참고 사항

- 워크스페이스에는 이미 `review_system.md`와 `CODING_CONVENTION.md`가 존재했다.
- 구현 재개 전에 일부 빈 소스 디렉터리가 미리 생성되어 있었다.
- 추가 진행 사항:
  - workspace를 `review-engine`, `review-platform`, `review-bot`, `ops`, `docs` 기준으로
    분리하는 문서를 작성했다.
  - 현재 엔진 코드를 `review-engine/`에 독립 복제해 분리 후에도 자체 테스트와
    린트를 통과하는 상태로 정리했다.
  - `review-platform/`에 bare Git 저장소 생성, PR 생성, diff 조회, 댓글/상태 저장 API를
    구현했다.
  - `review-bot/`에 플랫폼 diff 조회, 엔진 호출, finding dedupe, 상위 5개 게시 정책을
    구현한 최소 리뷰 봇을 추가했다.
  - `review-bot/`은 기본 `stub` provider와 추후 Codex/OpenAI 연결용 provider 분기점을
    함께 추가했다.
  - `ops/docker-compose.yml`, `.env.example`, `docs/OPERATIONS_RUNBOOK.md`를 추가해
    Postgres/Redis/Chroma 기반 실행 자산을 정리했다.
  - 구현 후 self code review를 수행했고, 결과를 `SELF_CODE_REVIEW.md`로 정리했다.
  - self review 결과에 따라 `review-bot`의 게시 일관성과 finding granularity를 보완했다.
    - patch 전체 단위 리뷰를 hunk 단위 리뷰로 개선했다.
    - fingerprint에 `issue_signature`를 추가했다.
    - 댓글 게시 성공 시 publication 상태를 즉시 commit하도록 바꿨다.
    - status API 실패가 전체 리뷰 실패로 번지지 않도록 best-effort 처리로 바꿨다.
  - 추가 진행 사항:
    - `review-platform`에 server-rendered HTML UI를 추가했다.
      - 저장소 목록/상세
      - PR 목록/상세
      - unified diff 뷰
      - 댓글/상태 표시
      - 봇 리뷰 실행 / 다음 5개 게시 버튼
    - `review-platform`에 `bot` facade API를 추가했다.
    - `review-bot`을 Redis 큐 기반 API + worker 구조로 확장했다.
      - API는 `queued`만 반환
      - 실제 리뷰는 worker에서 수행
    - `review-bot`에 OpenAI structured output provider와 stub fallback을 추가했다.
    - `review-bot`의 finding lifecycle을 `open`, `published`, `resolved`,
      `suppressed`, `failed_publication` 기준으로 확장했다.
    - `review-engine`에 운영용 메타데이터를 추가했다.
      - `reviewability`
      - `category`
      - `trigger_patterns`
      - `fix_guidance`
      - `review_rank_default`
    - `review-engine`의 dataset과 Chroma 컬렉션을
      `active`, `reference`, `excluded`로 분리했다.
    - `review-engine`은 자동 리뷰 결과에서 `reference_only` 규칙을 제외하도록 보강했다.
- self review 보강 항목을 보호하는 테스트를 추가했다.
    - multi-hunk finding 분리 검증
    - partial publication persistence 검증
- 현재 실행 기준 활성 적재 결과:
  - 전체 파싱 레코드 수: 608
  - Altibase 레코드 수: 111
  - C++ Core Guideline 레코드 수: 497
  - ChromaDB에 저장된 활성 레코드 수: 529
  - 제외되거나 덮어쓴 외부 레코드 수: 79
- MVP 구현 이후 추가 고도화 사항:
  - 이름 규칙, include, 매크로, 루프, 주석 관련 외부 규칙의 명시적 충돌 매핑을 확장했다.
  - 기대한 사내 규칙이 상위 결과에 더 안정적으로 노출되도록 패턴 힌트 주입을 강화했다.
  - 번들된 검색 기대 결과를 검증하는 `app.cli.evaluate_examples`를 추가했다.
  - 실제 `altidev4` 코드 조각을 repo 내부 excerpt로 옮겨 외부 경로 없이도
    패턴 추출, 저장소 스캔, 검색 우선순위 동작을 검증하도록 보강했다.
  - Altibase-style unified diff fixture를 repo 내부에 추가해 `review_diff` 경로도
    실제 코드 변경 형태로 계약 테스트하도록 보강했다.
- 실제 Altibase 저장소 `/home/et16/work/altidev4`를 기준으로 베이스라인 스캔을 완료했고,
  그 결과를 바탕으로 대표 excerpt 7개를 `examples/altidev4/`에 내장했다.
  - 포함 디렉터리: `src`, `tsrc`, `ut`
  - 서드파티, 생성물, 플랫폼 전용 경로는 선별적으로 제외해 노이즈를 줄였다.
  - 저장소 단위에서 지나치게 넓게 잡히는 스타일 신호는 추가 ignore 패턴으로 제외했다.
    - `identifier_underscore`
    - `ownership_ambiguity`
    - `line_comment`
    - `primitive_types`
  - 생성된 산출물:
    - `ALTIDEV4_BASELINE_REPORT.md`
    - `data/altidev4_scan_report.json`
  - 최신 저장소 스캔 스냅샷:
    - 스캔 파일 수: 5297
    - 매치 파일 수: 2799
    - 주요 반복 패턴:
      - `primitive_format_specifier`: 1157
      - `ide_rc_flow`: 1006
      - `direct_system_call`: 930
      - `malloc_free`: 576
      - `raw_new`: 470
      - `continue_usage`: 347
      - `manual_delete`: 307
      - `manual_lock_unlock`: 267
- 다음 명령으로 검증을 완료했다.
  - `uv run ruff check .`
  - `uv run pytest`
  - `uv run python -m app.cli.ingest_guidelines`
  - `uv run python -m app.cli.review_cpp_code --file examples/altidev4/queue_perf_memory_and_rc.cpp --top-k 6`
  - `uv run python -m app.cli.review_cpp_code --file examples/altidev4/sdpjl_portability_headers.cpp --top-k 6`
  - `uv run python -m app.cli.review_cpp_diff --diff examples/altidev4_diffs/queue_perf_memory_and_rc.diff --top-k 6`
  - `uv run python -m app.cli.evaluate_examples --spec examples/expected_retrieval_examples.json --top-k 12`
  - `uv run python -m app.cli.scan_codebase --root /home/et16/work/altidev4 --include-dir src --include-dir tsrc --include-dir ut --exclude-fragment /src/core/acp/ArmAtomic/ARM64 --exclude-fragment /src/core/acl/externalLib --exclude-fragment /ut/libedit --exclude-fragment /ut/altiMon/com.altibase.picl --exclude-fragment /src/pd/port/vxworks/pentium/sample1 --ignore-pattern identifier_underscore --ignore-pattern ownership_ambiguity --ignore-pattern line_comment --ignore-pattern primitive_types --top-files 40 --json-output data/altidev4_scan_report.json --markdown-output ALTIDEV4_BASELINE_REPORT.md`
  - `uv run --project review-engine --extra dev python -m pytest -q`
  - `uv run --project review-engine --extra dev python -m ruff check .`
  - `uv run --extra dev python -m pytest -q` in `review-platform/`
  - `uv run --extra dev python -m ruff check .` in `review-platform/`
  - `uv run --extra dev python -m pytest -q` in `review-bot/`
  - `uv run --extra dev python -m ruff check .` in `review-bot/`
