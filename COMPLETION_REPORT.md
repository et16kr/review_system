# 완료 보고서

날짜: 2026-04-19
상태: 완료

## 요약

`review_system.md`에서 요구한 MVP를 사내 규칙 우선 가이드라인 검색 시스템으로
구현했다.

구현된 동작:

- `CODING_CONVENTION.md`를 파싱해 최우선 기준 소스로 사용한다.
- 공식 C++ Core Guidelines를 가져와 파싱하고 정규화한다.
- 충돌하거나 비활성화된 외부 규칙은 활성 적재 전에 필터링한다.
- 활성 규칙은 ChromaDB에 저장되며 CLI와 FastAPI API를 통해 검색할 수 있다.
- 코드와 diff 입력은 리뷰 이슈 중심의 자연어 질의로 변환된다.
- 패턴-규칙 힌트를 통해 중요한 사내 규칙이 상위 결과에 더 잘 노출된다.
- 실제 Altibase 코드베이스를 베이스라인 분석해 컨벤션 핫스팟을 찾는 저장소 스캐너를 제공한다.
- 실제 `altidev4` 코드 excerpt를 repo 내부 예제로 내장해 외부 경로 없이도 주요 패턴 검출과 검색 결과를 검증한다.
- Altibase-style unified diff fixture를 repo 내부에 내장해 `review_diff` 경로도 외부 의존 없이 검증한다.

## 산출물

- `pyproject.toml`의 Python 프로젝트 메타데이터
- `app/` 하위의 핵심 애플리케이션 패키지
- `data/` 하위의 설정 및 정책 파일
- `app/cli/` 하위의 CLI 엔트리포인트
- [main.py](/home/et16/work/review_system/app/api/main.py:1)의 FastAPI 애플리케이션
- `examples/` 하위의 샘플 C++ 파일과 diff
- `tests/` 하위의 테스트 스위트
- 컨테이너 자산:
  - `Dockerfile`
  - `docker-compose.yml`
- 문서:
  - `README.md`
  - `IMPLEMENTATION_PROGRESS.md`
  - `COMPLETION_REPORT.md`

## 현재 적재 스냅샷

최신 검증된 ingest 실행 기준:

- 전체 파싱 레코드 수: 608
- Altibase 레코드 수: 111
- C++ Core Guideline 레코드 수: 497
- ChromaDB에 기록된 활성 레코드 수: 529
- 제외되거나 덮어쓴 외부 규칙 수: 79

생성된 데이터 파일:

- `data/altibase_coding_convention_rules.json`
- `data/cpp_core_guidelines_rules.json`
- `data/active_guideline_records.json`
- `data/chroma/`

## 실제 Altibase 베이스라인 스캔

스캐너는 실제 Altibase 저장소 `/home/et16/work/altidev4`를 기준으로 실행했다.

생성된 산출물:

- `ALTIDEV4_BASELINE_REPORT.md`
- `data/altidev4_scan_report.json`
- `examples/altidev4/`
- `examples/altidev4_snippets.json`
- `examples/altidev4_diffs/`
- `examples/altidev4_diffs.json`

최신 스캔 스냅샷:

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

생성된 보고서에서 확인된 대표 핫스팟 파일:

- `src/ul/ulp/ulpCompl.cpp`
- `src/ul/ulp/ulpPreprocl.cpp`
- `src/sm/smx/smxTrans.cpp`
- `src/rp/rpc/rpcManager.cpp`
- `ut/iloader3/src/iloCommandLexer.cpp`

## 검증

다음 항목을 성공적으로 완료했다.

- `uv run ruff check .`
- `uv run pytest`
- `uv run python -m app.cli.ingest_guidelines`
- `uv run python -m app.cli.review_cpp_code --file examples/altidev4/queue_perf_memory_and_rc.cpp --top-k 6`
- `uv run python -m app.cli.review_cpp_code --file examples/altidev4/sdpjl_portability_headers.cpp --top-k 6`
- `uv run python -m app.cli.review_cpp_diff --diff examples/altidev4_diffs/queue_perf_memory_and_rc.diff --top-k 6`
- `uv run python -m app.cli.evaluate_examples --spec examples/expected_retrieval_examples.json --top-k 12`
- `uv run python -m app.cli.scan_codebase --root /home/et16/work/altidev4 --include-dir src --include-dir tsrc --include-dir ut --exclude-fragment /src/core/acp/ArmAtomic/ARM64 --exclude-fragment /src/core/acl/externalLib --exclude-fragment /ut/libedit --exclude-fragment /ut/altiMon/com.altibase.picl --exclude-fragment /src/pd/port/vxworks/pentium/sample1 --ignore-pattern identifier_underscore --ignore-pattern ownership_ambiguity --ignore-pattern line_comment --ignore-pattern primitive_types --top-files 40 --json-output data/altidev4_scan_report.json --markdown-output ALTIDEV4_BASELINE_REPORT.md`

테스트 결과:

- 테스트 43개 통과

예제 평가 결과:

- 번들된 검색 예제 15건 모두 통과

## 알려진 한계

- 현재 충돌 해소는 명시적 규칙 매핑과 키워드 기반 override를 함께 사용한다.
  실용적으로 동작하지만, 사내 정책 매핑이 늘어날수록 더 정교하게 다듬을 수 있다.
- Altibase 규칙 소스는 원본 PDF가 아니라 Markdown 요약본이다. 원문 전체를 규칙 단위로
  더 풍부하게 정규화하면 검색 품질을 추가로 개선할 수 있다.
- 임베딩 방식은 단순한 설정과 재현성을 위해 결정론적 로컬 방식으로 설계했다. 따라서
  전용 임베딩 모델보다 의미적 표현력은 낮다.

## 권장 다음 단계

1. `data/conflict_rules.json`에 Altibase와 C++ Core Guideline 충돌 매핑을 더 확장한다.
2. 검색 정밀도가 더 필요하면 현재 해시 기반 로컬 임베더를 더 강한 오프라인 또는 승인된 임베딩 모델로 대체하거나 보완한다.
3. 실제 Altibase 저장소에서 많이 나온 패턴을 추가 검색 fixture로 승격해 기대 결과 커버리지를 높인다.
