Altibase 사내 코딩 컨벤션과 공식 C++ Core Guidelines를 결합하는 C++ 가이드라인
검색 시스템의 Python MVP를 구축한다.

기본 정책
- Altibase 사내 코딩 컨벤션을 최우선 기준으로 사용한다.
- 공식 C++ Core Guideline이 Altibase 컨벤션과 충돌하면 Altibase 규칙이 우선한다.
- 충돌하는 C++ Core Guideline 항목은 활성 리뷰 데이터셋에서 제외해야 하며,
  리뷰 결과로 반환되어서는 안 된다.
- Altibase 컨벤션 항목도 파싱, 정규화한 뒤 호환 가능한 C++ Core Guideline
  항목과 함께 벡터 데이터베이스에 저장해야 한다.

상위 목표
- 로컬 Altibase 코딩 컨벤션 문서를 적재한다:
  `CODING_CONVENTION.md`
- 공식 C++ Core Guidelines 페이지를 내려받는다.
- 일반 텍스트 청크가 아니라 규칙 항목 단위로 두 소스를 파싱한다.
- 두 소스를 하나의 공통 스키마로 정규화한다.
- Altibase 컨벤션을 위반하거나 충돌하는 C++ Core Guideline 항목을 필터링한다.
- Altibase 규칙과 호환 가능한 C++ Core Guideline 항목만 ChromaDB에 저장한다.
- C++ 코드 또는 diff를 자연어 질의로 바꾸는 변환기를 구현한다.
- 주어진 코드 조각이나 diff에 대해 가장 관련성 높은 규칙 항목을 검색한다.
- 검색 결과를 소스 권한 정책을 반영해 재랭킹한다.
- CLI와 간단한 FastAPI 서버를 제공한다.

프로젝트 요구사항
- 언어: Python 3.11+
- 패키지 관리자: `uv` 또는 `pip`
- 벡터 DB: ChromaDB
- 웹 프레임워크: FastAPI
- 테스트: pytest
- 포맷팅/린팅: ruff
- 타입 힌트 필수
- 모듈 구조는 깔끔하게 유지
- 로컬 개발용 `Dockerfile`과 `docker-compose.yml` 추가
- 소스 우선순위와 충돌 정책은 YAML 또는 JSON으로 설정 가능해야 함

핵심 제품 동작
1. 두 개의 가이드라인 소스를 적재한다.
   - 내부 소스:
     `CODING_CONVENTION.md`
   - 외부 소스:
     `https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines`

2. 두 문서를 규칙 항목 단위로 파싱한다.
   - 각 규칙 항목은 하나의 레코드가 되어야 한다.
   - 다음과 같은 Altibase 규칙 ID를 탐지한다.
     - `ALTI-NAE-001`
     - `ALTI-FOR-004`
     - `ALTI-MEM-007`
     - `ALTI-PCM-002`
     - `Rule-R1`
   - 다음과 같은 C++ Core Guideline 규칙 ID를 탐지한다.
     - `R.1`, `R.2`, `R.3`
     - `F.1`, `F.2`
     - `C.1`, `C.2`
     - `ES.1`, `ES.2`
     - `CP.1`, `CP.2`
   - 각 레코드에는 다음 필드를 보존한다.
     - `id`
     - `rule_no`
     - `source`
     - `source_family`
     - `authority`
     - `section`
     - `title`
     - `text`
     - `summary`
     - `keywords`
     - `priority`
     - `severity_default`
     - `conflict_policy`
     - `embedding_text`

3. 소스 우선순위와 충돌 해소를 구현한다.
   - Altibase는 공식 C++ Core Guidelines보다 항상 높은 우선순위를 가진다.
   - C++ Core Guideline 하나가 하나 이상의 Altibase 규칙과 충돌하면 해당 C++
     항목을 활성 리뷰 컬렉션에서 제외한다.
   - 다음 항목에 대한 명시적 설정 파일을 유지한다.
     - 소스 우선순위
     - 충돌 매핑
     - 비활성화 또는 제외된 외부 규칙
   - 다음과 같은 상태를 지원한다.
     - `authoritative`
     - `compatible`
     - `overridden`
     - `excluded`
   - 활성 리뷰 시스템은 다음 항목만 사용해야 한다.
     - 모든 Altibase 규칙
     - `compatible`로 표시된 C++ Core Guideline 규칙
   - 정책에서 지원해야 하는 대표 충돌 영역:
     - 이름 규칙 및 prefix 규칙
     - 주석 스타일 규칙
     - include 및 이식성 wrapper 규칙
     - Altibase 타입 사용 규칙
     - Altibase 에러 처리 매크로 규칙
     - 단일 종료점 또는 제어 흐름 제한
     - Altibase 특화 메모리 관리 컨벤션

4. 레코드를 ChromaDB에 저장한다.
   - 임베딩을 위한 기본 문서 텍스트로 `embedding_text`를 사용한다.
   - Altibase와 호환 가능한 C++ 규칙을 활성 컬렉션에 저장한다.
   - 선택적으로 감사/디버깅용 원본 파싱 결과를 정규화된 JSON 파일로 유지한다.
   - 메타데이터에는 다음 필드를 포함한다.
     - `rule_no`
     - `source`
     - `source_family`
     - `authority`
     - `section`
     - `title`
     - `priority`
     - `severity_default`
     - `conflict_policy`

5. 코드-쿼리 변환을 구현한다.
   - 입력은 다음 중 하나다.
     - 원본 C++ 코드
     - git diff
   - 코드에서 예상되는 리뷰 이슈를 중심으로 자연어 검색 텍스트를 생성한다.
   - 최소한 다음 C++ Core Guideline 지향 패턴을 탐지한다.
     - `new`를 사용하는 raw pointer 할당
     - `malloc`/`free` 사용
     - 수동 `delete`/`delete[]`
     - RAII 패턴 누락
     - 수동 lock/unlock
     - 소유권 모호성 가능성
     - 불필요한 복사 후보
     - const 정확성 힌트
     - move 오용 힌트
   - 최소한 다음 Altibase 컨벤션 지향 패턴을 탐지한다.
     - Altibase 이름 prefix 위반
     - 변수 또는 사용자 정의 타입 이름에서의 `_` 사용
     - Altibase typedef가 기대되는 위치에서 primitive type 사용
     - 직접 시스템 헤더 include
     - wrapper 대신 직접 시스템 라이브러리 호출
     - `//` 주석 사용
     - `switch`에서 `default` 누락
     - `continue` 사용
     - `for` 초기화절에서 변수 선언
     - `ID_*_FMT` 대신 직접 primitive 포맷 지정자 사용
     - `free()` 직후 즉시 `NULL` 재설정 누락
     - `IDE_RC` / `IDE_TEST` / `IDE_EXCEPTION` 패턴의 누락 또는 불일치
   - 변환기 출력은 단순한 원시 코드가 아니라 이슈 중심 자연어여야 한다.

6. 검색을 구현한다.
   - 생성된 자연어 질의로 ChromaDB를 조회한다.
   - 먼저 상위 30개 후보를 가져온다.
   - `conflict_policy`가 `excluded` 또는 `overridden`인 후보는 제거한다.
   - 다음 최종 점수로 재랭킹한다.
     `final_score =`
     `  similarity_score * 0.45 +`
     `  authority_score  * 0.20 +`
     `  priority_score   * 0.20 +`
     `  severity_score   * 0.10 +`
     `  pattern_boost    * 0.05`
   - 재랭킹 후 상위 10개를 반환한다.
   - `rule_no` 기준으로 중복을 제거한다.
   - Altibase 규칙과 C++ 규칙이 같은 이슈에 함께 매치되면 기본적으로 Altibase
     규칙을 더 높게 랭크한다.

7. 우선순위 정책을 구현한다.
   - 소스 권한, 섹션, 가이드라인 유형에 따라 기본 priority 점수를 부여한다.
   - 1차 휴리스틱은 다음 기준을 사용한다.
     - 매우 높은 우선순위:
       Altibase 에러 처리, 이식성 wrapper, 메모리 수명, 누수, 댕글링 포인터,
       null 역참조, 동시성 위험
     - 높은 우선순위:
       소유권, RAII, unsafe cast, include 정책, 직접 시스템 호출 사용,
       유지보수성 또는 도구 체계와 연결된 이름 규칙 위반
     - 중간 우선순위:
       불필요한 복사, move 오용, const 정확성, 사내 표준에서 요구하는 포맷 또는
       레이아웃 규칙
     - 낮은 우선순위:
       Altibase 환경에서는 중요도가 낮지만 호환 가능한 스타일 중심 외부 제안
   - Altibase 규칙은 외부 규칙보다 더 강한 기본 authority 점수를 가져야 한다.
   - 이 정책은 YAML 또는 JSON으로 설정 가능해야 한다.

8. CLI 도구
   다음 도구를 구현한다.
   - `ingest_guidelines.py`
     - `CODING_CONVENTION.md` 적재
     - 공식 C++ Core Guidelines 적재
     - 충돌 필터링 적용
     - 활성 ChromaDB 컬렉션 생성
   - `review_cpp_code.py --file path/to/file.cpp`
   - `review_cpp_diff.py --diff path/to/sample.diff`
   - `inspect_rule.py --rule ALTI-MEM-007`
   - `inspect_rule.py --rule R.3`

9. FastAPI 서버
   다음 엔드포인트를 구현한다.
   - `POST /ingest`
   - `POST /review/code`
   - `POST /review/diff`
   - `GET /rule/{rule_no}`
   - `GET /health`

10. 리뷰 엔드포인트 출력 형식
    다음과 같은 JSON을 반환한다.
    {
      "query_text": "...",
      "results": [
        {
          "rule_no": "ALTI-MEM-007",
          "source_family": "altibase",
          "authority": "internal",
          "conflict_policy": "authoritative",
          "title": "Assign NULL immediately after free()",
          "section": "ALTI-MEM",
          "priority": 0.98,
          "score": 0.94,
          "summary": "...",
          "text": "..."
        },
        {
          "rule_no": "R.11",
          "source_family": "cpp_core",
          "authority": "external",
          "conflict_policy": "compatible",
          "title": "Avoid calling new and delete explicitly",
          "section": "R",
          "priority": 0.82,
          "score": 0.79,
          "summary": "...",
          "text": "..."
        }
      ]
    }

11. 테스트
    다음 항목에 대한 단위 테스트를 추가한다.
    - Altibase Markdown 규칙 파싱
    - C++ Core Guideline HTML 규칙 파싱
    - 메타데이터 추출
    - 충돌 필터링
    - 코드-쿼리 변환
    - 소스 인지형 랭킹
    - API 응답 형식

12. 샘플 데이터와 예제
    다음을 포함한다.
    - 최소 3개의 샘플 C++ 코드 파일
    - 최소 3개의 샘플 diff
    - 기대 검색 결과 예제
    - Altibase 전용 규칙을 유발하는 예제
    - Altibase 규칙과 호환 가능한 C++ 규칙이 함께 매치되는 예제

권장 모듈 구조
- `app/`
  - `config.py`
  - `models.py`
  - `parser/`
    - `guidelines_fetcher.py`
    - `guidelines_parser.py`
    - `internal_convention_parser.py`
  - `ingest/`
    - `build_records.py`
    - `conflict_resolver.py`
    - `chroma_store.py`
  - `query/`
    - `cpp_feature_extractor.py`
    - `code_to_query.py`
  - `retrieve/`
    - `search.py`
    - `rerank.py`
  - `api/`
    - `main.py`
  - `cli/`
    - `ingest_guidelines.py`
    - `review_cpp_code.py`
    - `review_cpp_diff.py`
    - `inspect_rule.py`
- `tests/`
- `examples/`
- `data/`
  - `source_priority.json`
  - `conflict_rules.json`
  - `disabled_cpp_core_rules.json`
  - `altibase_coding_convention_rules.json`
  - `cpp_core_guidelines_rules.json`
  - `active_guideline_records.json`

구현 세부사항
- C++ Core Guidelines 파서는 HTML 구조 변경에 견고해야 한다.
- `CODING_CONVENTION.md`는 heading과 규칙 bullet 항목 기준으로 파싱한다.
- Altibase와 C++ 규칙을 하나의 공통 레코드 모델로 정규화한다.
- 자동으로 알 수 없는 충돌은 숨겨진 휴리스틱이 아니라 명시적 설정으로 해결한다.
- 로깅과 에러 처리를 포함한다.
- 로컬 설치 및 사용 예제가 있는 README를 추가한다.
- 내부 소스 경로는 설정 가능하게 하되, 기본값은 저장소 로컬의
  `CODING_CONVENTION.md`로 둔다.

산출물
- 두 소스에 대한 로컬 ingest가 정상 동작할 것
- 충돌 필터링된 활성 가이드라인 데이터셋
- 다음을 포함해 채워진 ChromaDB
  - 모든 Altibase 규칙
  - 호환 가능한 C++ Core Guideline 규칙만
- 검색 가능한 CLI
- FastAPI 서버
- 테스트 통과
- 실행 명령이 정확히 적힌 README
