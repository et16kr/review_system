# Review Engine Multi-Language Rule Architecture Design

## 목적

이 문서는 현재 C++ 중심으로 구현된 `review-engine` / `review-bot` 구조를
다중 언어 리뷰 엔진으로 확장하기 위한 설계 기준을 고정한다.

목표 언어 예시:

- `cpp`
- `c`
- `python`
- `typescript`
- `javascript`
- `java`
- `go`
- `rust`
- `bash`
- `sql`
- `yaml`
- `dockerfile`

여기서 `yaml`, `dockerfile`은 전통적인 의미의 프로그래밍 언어라기보다
리뷰 대상이 되는 declarative configuration / build artifact로 취급한다.

핵심 요구는 다음 세 가지다.

1. 언어별 규칙을 독립적으로 추가/수정할 수 있어야 한다.
2. 사람이 수정하는 canonical rule 문서를 기준으로 엔진 산출물을 재생성할 수 있어야 한다.
3. 나중에 웹 UI를 붙여도 저장 구조를 다시 뒤엎지 않도록 해야 한다.

## 현재 상태 요약

현재 구현은 사실상 C++ 전용 구조다.

대표적인 고정 지점:

- [review-engine/review_engine/models.py](/home/et16/work/review_system/review-engine/review_engine/models.py:1)
  - `source_family`가 C++ 중심 family 값에 과하게 기대고 있다.
- [review-engine/review_engine/query/code_to_query.py](/home/et16/work/review_system/review-engine/review_engine/query/code_to_query.py:1)
  - query 문장이 `"Review this C++ ..."`로 고정되어 있다.
- [review-engine/review_engine/query/cpp_feature_extractor.py](/home/et16/work/review_system/review-engine/review_engine/query/cpp_feature_extractor.py:1)
  - 패턴 추출기가 C++/조직 메모리 규칙 중심이다.
- [review-engine/review_engine/config.py](/home/et16/work/review_system/review-engine/review_engine/config.py:1)
  - 여전히 `cpp_core_guidelines.html` 같은 C++ 전용 cache filename을 직접 가진다.
- [review-bot/review_bot/bot/review_runner.py](/home/et16/work/review_system/review-bot/review_bot/bot/review_runner.py:1)
  - `CPP_EXTENSIONS`와 `self._is_cpp_path()` 전제를 가진다.

즉 현재 구조는 다음을 전제로 한다.

- 입력 언어는 사실상 C++ 하나다.
- 내부 규칙과 외부 규칙도 모두 C++ 전용이다.
- retrieval, prompt, pattern extraction, file filtering이 모두 C++로 결합되어 있다.

이 구조 위에 언어를 하나씩 얹는 것은 가능하지만,
`if language == ...`를 여러 군데에 늘리는 방식은 곧 유지보수가 어려워진다.

## 설계 원칙

1. 언어와 규칙 출처를 분리한다.
2. 사람이 수정하는 canonical rule 문서는 구조화 포맷으로 둔다.
3. 원천 문서 파싱 결과와 canonical rule 문서를 분리한다.
4. retrieval은 언어별로 격리하되, 필요하면 shared 규칙을 함께 조회할 수 있게 한다.
5. `review-bot`은 파일 경로 기반 C++ 필터가 아니라 language registry를 사용한다.
6. 웹 UI는 “새로운 저장소”가 아니라 canonical rule 문서를 편집하는 frontend여야 한다.

## 비목표

이번 설계 문서는 아래를 즉시 구현 범위로 잡지 않는다.

- 모든 언어 규칙을 한 번에 작성
- 완전 자동 언어 판별의 100% 정확성 보장
- LSP 수준의 deep semantic analysis
- 언어별 formatter/linter/AST 실행 엔진 통합

우선순위는 “규칙 구조와 편집 구조를 바로잡는 것”이다.

## 핵심 개념

### 1. `language_id`

엔진이 이해하는 1차 언어 식별자다.

예시:

- `cpp`
- `c`
- `python`
- `typescript`
- `javascript`
- `java`
- `go`
- `rust`
- `bash`
- `sql`
- `yaml`
- `dockerfile`
- `shared`

`shared`는 언어 불문 공통 규칙을 위해 둔다.

예시:

- secrets
- shell injection
- sql injection
- generated file policy
- review process policy

### 2. `rule_pack`

규칙의 묶음 단위다.

예시:

- `project_cpp`
- `cpp_core`
- `posix_c`
- `pep8_python`
- `project_python`
- `project_typescript`
- `project_javascript`
- `effective_java`
- `project_java`
- `project_go`
- `project_rust`
- `project_bash`
- `ansi_sql`
- `project_sql`
- `kubernetes_yaml`
- `ci_yaml`
- `dockerfile_best_practices`
- `shared_security`

현재의 `source_family`는 사실상 `rule_pack`와 비슷한 역할을 하지만 너무 좁다.
앞으로는 아래처럼 나누는 것이 좋다.

- `language_id`
- `rule_pack`
- `authority`
- `source_kind`

### 3. `canonical rule document`

사람과 UI가 수정하는 진짜 기준 문서다.

중요:

- raw HTML/Markdown 파싱 결과가 canonical source가 아니다
- 사람이 검토하고 편집하는 `rules/**/*.yaml`이 runtime canonical source다
- `rule_sources/`와 raw import 결과는 provenance, bootstrap, import draft 생성용이다

## 제안 구조

루트에 언어별 rule workspace를 둔다.

```text
rules/
  shared/
    manifest.yaml
    packs/
      shared_security.yaml
      review_process.yaml
    profiles/
      default.yaml
  cpp/
    manifest.yaml
    packs/
      project_cpp.yaml
      cpp_core.yaml
      native_memory_shared.yaml
    profiles/
      default.yaml
      service_backend_cpp.yaml
    imports/
      cpp_core_import.yaml
  c/
    manifest.yaml
    packs/
      project_c.yaml
      posix_c.yaml
      native_memory_shared.yaml
    profiles/
      default.yaml
  python/
    manifest.yaml
    packs/
      pep8_python.yaml
      pep257_docstrings.yaml
      project_python.yaml
    profiles/
      default.yaml
      typed_python.yaml
  typescript/
    manifest.yaml
    packs/
      project_typescript.yaml
      ts_api_design.yaml
    profiles/
      default.yaml
      frontend_strict.yaml
  javascript/
    manifest.yaml
    packs/
      project_javascript.yaml
      node_javascript.yaml
    profiles/
      default.yaml
  java/
    manifest.yaml
    packs/
      project_java.yaml
      effective_java.yaml
    profiles/
      default.yaml
  go/
    manifest.yaml
    packs/
      project_go.yaml
    profiles/
      default.yaml
  rust/
    manifest.yaml
    packs/
      project_rust.yaml
    profiles/
      default.yaml
  bash/
    manifest.yaml
    packs/
      project_bash.yaml
      shell_safety.yaml
    profiles/
      default.yaml
  sql/
    manifest.yaml
    packs/
      ansi_sql.yaml
      postgres_sql.yaml
      project_sql.yaml
    profiles/
      default.yaml
      analytics_warehouse.yaml
  yaml/
    manifest.yaml
    packs/
      generic_yaml.yaml
      kubernetes_yaml.yaml
      ci_yaml.yaml
      helm_values.yaml
    profiles/
      default.yaml
      kubernetes_manifests.yaml
      github_actions.yaml
      gitlab_ci.yaml
  dockerfile/
    manifest.yaml
    packs/
      dockerfile_best_practices.yaml
      container_security.yaml
    profiles/
      default.yaml
      production_runtime.yaml
```

의도는 단순하다.

- `manifest.yaml`
  - 그 언어의 기본 메타데이터
- `packs/*.yaml`
  - 규칙 정의 문서
- `profiles/*.yaml`
  - 어떤 pack을 어떤 우선순위로 사용할지 정의
- `imports/*.yaml`
  - 외부 문서를 끌어올 때 provenance와 import 규칙을 정의

중요:

- 위 예시는 public canonical root 기준이다
- organization-specific pack, profile, detector, prompt overlay는 public `rules/` 아래에 두지 않고 requirement 1의 extension root/package로 분리한다
- project 성격의 일반 예시 pack은 이 문서에서 `project_<language>` 이름 규칙을 따른다

## Rule Document 포맷

권장 포맷은 YAML이다.

이유:

- 사람이 읽기 쉽다
- Git diff가 보기 쉽다
- 웹 UI에서 수정한 뒤 파일로 되돌리기 쉽다
- JSON보다 주석/메타 설명을 넣기 쉽다

예시:

```yaml
pack_id: cpp_core
language_id: cpp
display_name: C++ Core Guidelines
authority: external
source_kind: imported
default_conflict_policy: compatible
rules:
  - rule_uid: cpp:cpp_core:R.1
    rule_no: R.1
    section: R
    title: Manage resources automatically using RAII
    summary: Avoid manual lifetime management.
    text: |
      ...
    category: memory
    reviewability: auto_review
    false_positive_risk: medium
    applies_to: [code, diff]
    trigger_patterns: [raw_new, malloc_free, manual_delete]
    fix_guidance: Prefer RAII and explicit ownership models.
    tags: [ownership, lifetime, raii]
    enabled: true
```

## Raw Rule Source Document Bundle

위의 canonical pack YAML과 별개로,
새 환경에서 이 branch를 받아 바로 규칙 seed를 재구성할 수 있게 하려면
`vector DB ingest`와 `import draft 생성`에 공통으로 쓸 raw rule source 문서 묶음이 필요하다.

중요:

- 이번 단계에서 각 언어별 raw rule source 문서를 실제로 작성하는 것은 실행 범위가 아니다
- 이번 단계의 목표는 "어떤 구조로 둘 것인가"를 설계 문서에 고정하는 것이다
- 실제 문서 작성과 pack 반영은 후속 execution phase에서 수행한다

권장 구조:

```text
rule_sources/
  manifest.yaml
  shared/
    shared_security_baseline.md
    shared_review_process.md
  cpp/
    cpp_core_guidelines.md
    native_memory_shared.md
  c/
    posix_c_safety.md
    native_memory_shared.md
  python/
    pep8_style.md
    pep257_docstrings.md
    typing_guidance.md
  typescript/
    typescript_handbook.md
    google_typescript_style.md
  javascript/
    mdn_javascript_guide.md
    google_javascript_style.md
  java/
    effective_java_notes.md
    project_java_api_design.md
  go/
    go_project_practices.md
  rust/
    rust_project_practices.md
  bash/
    shell_safety.md
  sql/
    sql_shared_style.md
    postgresql_notes.md
    analytics_sql_notes.md
  yaml/
    yaml_spec.md
    github_actions_workflows.md
    gitlab_ci_yaml.md
    helm_values_best_practices.md
    kubernetes_api_conventions.md
    kubernetes_api_concepts.md
  dockerfile/
    dockerfile_reference.md
    docker_image_best_practices.md
```

여기서 `rule_sources/`는 runtime pack과 역할이 다르다.

- `rule_sources/*.md`
  - 벡터 DB 적재, import seed, 사람 검토용 원천 규칙 문서
  - canonical pack을 직접 대체하지 않는다
- `rules/*/packs/*.yaml`
  - 엔진 runtime이 직접 읽는 canonical normalized pack
  - 유일한 runtime canonical source다

즉, branch를 새로 clone한 환경에서도
`rules/`만 있으면 runtime ingest를 다시 수행할 수 있어야 하고,
`rule_sources/`가 있으면 raw chunking, vector ingest, import draft regeneration을 다시 수행할 수 있어야 한다.

## Raw Rule Source 문서 메타데이터

각 raw rule source 문서는 Markdown 본문 앞에 YAML front matter를 두는 방식을 권장한다.

예시:

```md
---
rule_source_id: python.pep8_style
language_id: python
dialect_id: null
profile_hints: [default, service_backend_python]
pack_targets: [pep8_python]
source_type: public_guideline_summary
source_ref:
  title: PEP 8
  url: https://peps.python.org/pep-0008/
chunking:
  strategy: heading_sections
  max_chars: 2200
vector_ingest_tags: [style, naming, imports, formatting]
status: planned
---

# PEP 8 Style Seed
...
```

권장 필드:

- `rule_source_id`
- `language_id`
- `dialect_id`
- `context_id`
- `profile_hints`
- `pack_targets`
- `source_type`
  - `public_guideline_summary | project_policy_summary | dialect_reference_summary`
- `source_ref.title`
- `source_ref.url`
- `chunking.strategy`
- `chunking.max_chars`
- `vector_ingest_tags`
- `status`
  - `planned | drafted | validated | imported`

이 메타데이터를 두면
raw rule source를 바로 vector DB에 적재할 때도 쓰기 쉽고,
나중에 import draft나 pack update proposal을 만들 때도 provenance를 잃지 않는다.

## `rule_sources/manifest.yaml` 설계

raw rule source 문서는 개별 Markdown 파일만 두는 것으로 끝내지 말고,
최상단 manifest로 전체 bundle을 설명하는 것이 좋다.

예시:

```yaml
schema_version: 1
bundle_id: review_engine_multilanguage_seed_sources
default_chunking:
  strategy: heading_sections
  max_chars: 2200
languages:
  - language_id: python
    sources:
      - rule_source_id: python.pep8_style
        path: python/pep8_style.md
        pack_targets: [pep8_python]
      - rule_source_id: python.pep257_docstrings
        path: python/pep257_docstrings.md
        pack_targets: [pep257_docstrings]
  - language_id: yaml
    sources:
      - rule_source_id: yaml.github_actions
        path: yaml/github_actions_workflows.md
        context_id: github_actions
        pack_targets: [ci_yaml]
```

manifest가 담당할 역할:

- branch를 새로 받은 환경에서 어떤 source 문서를 읽어야 하는지 안내
- vector ingest 대상 목록 제공
- source 문서와 canonical pack target의 연결 유지
- language/profile/context/dialect 매핑을 한곳에서 확인

## Branch 재구성 계약

이 설계에서 branch 재구성이 가능하다는 뜻은 아래를 의미한다.

1. 저장소 clone만으로 runtime canonical source와 raw bootstrap source를 모두 확인할 수 있다.
2. 외부 hidden state 없이 `rules/`만으로 runtime ingest 준비가 가능하다.
3. `rule_sources/manifest.yaml`이 있으면 bootstrap/import workflow도 같은 branch에서 재현할 수 있다.
4. vector DB는 generated artifact이므로 커밋 대상이 아니다.
5. 새 환경에서는 아래 두 흐름 중 필요한 경로를 재구성한다.

```text
runtime rebuild
  -> read rules/**/manifest.yaml + packs + profiles
  -> ingest runtime packs
  -> rebuild language-specific collections

bootstrap / import refresh
  -> read rule_sources/manifest.yaml
  -> chunk raw rule source documents
  -> optional vector ingest for exploration / draft retrieval
  -> generate import candidates / pack update proposals
  -> human review
  -> update rules/**/*.yaml
```

즉 source of truth는 vector DB가 아니라 `rules/`이고,
`rule_sources/`는 reproducible bootstrap input이다.

## Canonical Pack 과 Raw Source 분리 원칙

두 저장 구조를 섞으면 운영이 다시 복잡해진다.

분리 원칙은 아래와 같다.

- `rule_sources/`
  - 공개 guideline 요약, vendor reference 요약, 프로젝트 정책 요약
  - vector ingest와 import 후보 생성용
  - runtime canonical source가 아니다
- `rules/`
  - 사람이 검토한 normalized runtime pack
  - profile/policy와 함께 실제 엔진이 읽는 데이터
  - runtime의 유일한 canonical source다
- `data/*.json`, vector collection, cache
  - generated artifact
  - canonical source가 아니다

이 구조를 고정하면
"새 branch를 받은 환경에서 raw source를 다시 적재"와
"현재 runtime이 읽는 canonical pack과 dataset을 다시 구축"을 분리해서 다룰 수 있다.

## Rule Schema 제안

현재 `GuidelineRecord`를 바로 버리기보다, 아래처럼 일반화한다.

### 필수 필드

- `rule_uid`
  - 전역 유일 ID
  - 형식 예: `cpp:cpp_core:R.1`, `java:effective_java:EJ-001`
- `language_id`
  - `cpp`, `python`, `typescript`, `javascript`, `java`, `go`, `rust`, `bash`, `sql`, `yaml`, `dockerfile`, `shared`
- `rule_pack`
  - `cpp_core`, `project_cpp`, `shared_security`
- `rule_no`
  - 사람이 보는 원래 번호
- `title`
- `summary`
- `text`

### 운영 필드

- `authority`
  - `internal | external | imported | generated`
- `priority`
- `conflict_policy`
  - `authoritative | compatible | overridden | excluded`
- `reviewability`
  - `auto_review | manual_only | reference_only`
- `applies_to`
  - `code | diff | comment | docs`
- `category`
- `false_positive_risk`
- `review_rank_default`
- `fix_guidance`
- `tags`
- `trigger_patterns`
- `enabled`

### provenance 필드

- `source_kind`
  - `manual_yaml | markdown_import | html_import | generated`
- `source_ref`
  - 원문 문서 또는 URL
- `imported_from`
  - import job 이름 또는 source id
- `last_synced_at`

### language-specific 필드

- `dialects`
  - 예: `gnu++17`, `c11`, `python3.12`, `typescript5`, `ecmascript2023`, `bash`, `posix-sh`, `postgresql`, `mysql`, `sqlite`, `bigquery`, `snowflake`, `kubernetes_manifest`, `github_actions`, `gitlab_ci`, `dockerfile_v1`
- `file_globs`
  - pack가 적용될 파일 패턴
- `symbol_hints`
  - 패턴 추출기 힌트

## 언어별 공통 규칙 처리

언어를 늘리면 “공통 규칙을 어디에 두는가”가 중요해진다.

예를 들면:

- shell command injection
- hardcoded secret
- unsafe temp file
- generated file 수정 금지

이런 규칙은 특정 언어에만 묶지 말고 `shared` pack로 둔다.

추천 방식:

- 언어별 query는 `language active collection + shared active collection`을 같이 조회한다
- 결과는 `language-specific > shared` 우선으로 rerank한다

## Retrieval / Vector Store 구조

현재는 `active/reference/excluded` 3종 collection 중심이다.
다중 언어에서는 아래 두 가지 방식이 있다.

### 옵션 A. 단일 collection + metadata filter

장점:

- 구현 단순
- 관리 collection 수 적음

단점:

- 언어별 isolation이 약함
- 잘못된 language filter가 retrieval 오염으로 이어지기 쉬움

### 옵션 B. 언어별 collection 분리

예시:

- `guideline_rules_active_cpp`
- `guideline_rules_active_python`
- `guideline_rules_active_typescript`
- `guideline_rules_active_javascript`
- `guideline_rules_active_java`
- `guideline_rules_active_go`
- `guideline_rules_active_rust`
- `guideline_rules_active_bash`
- `guideline_rules_active_sql`
- `guideline_rules_active_yaml`
- `guideline_rules_active_dockerfile`
- `guideline_rules_active_shared`

장점:

- 언어 오염 방지
- 운영과 디버깅이 쉬움
- 인덱스 rebuild 범위를 언어별로 제한 가능

단점:

- collection 수가 늘어남

권장안:

- `dataset_kind(active/reference/excluded) x language_id` 조합으로 분리
- `shared`는 별도 collection 유지

## Query Analysis 구조

현재는 `cpp_feature_extractor.py`와 C++ 전용 query 문장이 고정되어 있다.
이를 plugin 구조로 바꾼다.

```text
review_engine/query/languages/
  base.py
  cpp.py
  c.py
  python.py
  typescript.py
  javascript.py
  java.py
  go.py
  rust.py
  bash.py
  sql.py
  yaml.py
  dockerfile.py
  shared.py
```

공통 인터페이스:

- `detect_patterns(source_text, input_kind, file_path=None) -> list[QueryPattern]`
- `build_query_text(input_kind, patterns, language_profile) -> str`
- `is_reviewable_file(file_path) -> bool`
- `guess_language(file_path, source_text=None) -> LanguageMatch`

이 구조의 장점:

- C++ 전용 힌트와 query wording을 다른 언어에서 재사용하지 않아도 된다
- 언어별 AST/regex/linter integration을 독립적으로 추가할 수 있다

## Language Registry 구조

`LanguageRegistry`를 도입한다.

예시 역할:

- file extension 기반 language 추론
- shebang 기반 `bash` 판별
- SQL file glob 기반 `sql` 판별
- YAML path / directory convention 기반 subtype 판별
- `Dockerfile`, `Dockerfile.*`, `*.dockerfile` 패턴 판별
- `.h` 파일의 `c`/`cpp` ambiguity 정책
- query plugin 매핑
- rule pack 기본 profile 결정

예시:

```yaml
language_id: bash
display_name: Bash
file_extensions: [.sh]
filenames: [".bashrc", ".bash_profile"]
shebangs: ["#!/bin/bash", "#!/usr/bin/env bash", "#!/bin/sh"]
default_profile: default
query_plugin: bash
reviewable: true
```

## `review-bot` 변경 방향

다중 언어를 실제 PR/MR 리뷰로 연결하려면 `review-bot`도 구조를 바꿔야 한다.

### 현재 문제

- `CPP_EXTENSIONS`
- `_is_cpp_path()`
- provider prompt가 특정 조직의 C++ 맥락에 최적화

### 변경 방향

1. `CPP_EXTENSIONS` 제거
2. `LanguageRegistry.is_reviewable_file(file_path)` 사용
3. detect phase에서 각 file마다 `language_id` 판별
4. `review-engine` API 호출에 `language_id`, `profile_id`를 같이 넘김
5. provider prompt도 `language_id`와 `profile_id`에 따라 base + language + profile + optional extension overlay 조합으로 바꿈

조직 특화 overlay는 requirement 1에서 정의한 extension prompt root/package 경로를 사용한다.

예시:

- `cpp`
  - RAII, resource ownership, wrapper usage, manual lifetime boundary
- `python`
  - exception taxonomy, context manager, mutable default, typing discipline
- `typescript`
  - strict null safety, unsafe `any`, narrowing 실패, public API typing
- `javascript`
  - async error handling, mutation discipline, module boundary, runtime type assumptions
- `java`
  - null handling, resource closing, stream misuse, thread safety
- `go`
  - `defer`, error handling, goroutine leak, context propagation
- `rust`
  - ownership, `unsafe`, panic boundary, error propagation
- `bash`
  - quoting, `set -euo pipefail`, globbing, command substitution safety
- `sql`
  - `SELECT *`, implicit join, nullable join key misuse, dialect-specific anti-pattern, unsafe dynamic SQL
- `yaml`
  - schema mismatch, duplicated key risk, insecure default, K8s/CI semantic misuse
- `dockerfile`
  - base image pinning, layer ordering, root user, secret leakage, cache misuse

## Engine API 변경 제안

현재 `ReviewCodeRequest`, `ReviewDiffRequest`는 언어 개념이 약하다.
다음 필드를 추가하는 방향이 좋다.

### `ReviewDiffRequest`

- `language_id: str | null`
- `profile_id: str | null`
- `context_id: str | null`
- `dialect_id: str | null`
- `file_path: str | null`
- `file_context: str | null`

정책:

- `language_id`가 오면 우선 사용
- `profile_id`, `context_id`, `dialect_id`가 오면 강한 힌트로 사용
- 없으면 `file_path`, 내용, language registry 규칙 기반으로 추론
- 둘 다 없으면 `shared` 또는 `unknown` fallback

주의:

- 현재 `review-bot` 흐름은 changed file 단위 호출을 기본으로 하므로 위 필드는 "현재 리뷰 중인 file"의 분류 결과를 뜻한다
- mixed-language PR/MR도 엔진 호출은 file 단위 분류를 기본으로 한다

### `ReviewResult`

- `language_id`
- `profile_id`
- `context_id`
- `dialect_id`
- `rule_pack`
- `rule_uid`

현재 `source_family`는 유지하더라도,
장기적으로는 `rule_pack` 또는 `rule_origin`으로 대체하는 것이 좋다.

## Canonical Editing Workflow

사람이나 AI가 규칙을 바꾸는 표준 흐름은 아래와 같다.

1. `rules/<language>/packs/*.yaml` 수정
2. ingest 명령 실행
3. normalized dataset 재생성
4. Chroma collection rebuild
5. golden examples / regression tests 실행

이 흐름이면 웹 UI가 없어도 충분히 운영 가능하다.

## 웹 UI 설계 방향

웹 UI는 별도 저장소를 만들면 안 된다.
UI는 canonical YAML 문서를 편집하는 frontend여야 한다.

### 최소 기능

- 언어 목록
- pack 목록
- rule 검색
- rule 상세 보기
- rule 수정
- enabled on/off
- fix guidance / category / reviewability 수정
- 저장 후 preview
- ingest / reindex 실행

### 권장 API

- `GET /admin/languages`
- `GET /admin/rule-packs?language_id=cpp`
- `GET /admin/rules/{rule_uid}`
- `PUT /admin/rules/{rule_uid}`
- `POST /admin/ingest`
- `POST /admin/reindex`
- `POST /admin/preview`

### 권한 모델

- read-only viewer
- editor
- admin/reindex 권한

## Import 구조

외부 규칙 문서를 그대로 사람이 편집하는 것은 좋지 않다.

따라서 import는 아래처럼 나눈다.

1. raw source fetch
2. parser output 생성
3. import draft 또는 canonical patch proposal 생성
4. 사람 검토 후 `rules/**/*.yaml` 반영
5. pack/profile 정책 적용
6. active/reference/excluded 생성

즉, 외부 문서 변경과 내부 운영 rule 수정은 분리한다.

여기서 raw rule source 문서의 위치는 아래처럼 잡는 것이 좋다.

1. 외부 원문
   - 공식 guideline, vendor reference, project policy
2. raw rule source Markdown
   - `rule_sources/**/*.md`
3. canonical normalized pack
   - `rules/*/packs/*.yaml`
4. generated dataset / vector collections
   - `data/*.json`, Chroma, 기타 캐시

즉, requirement 2에서는
"각 언어별 규칙 문서를 지금 바로 작성"하는 것이 아니라
"나중에 어떤 단계로 raw source -> import draft -> canonical pack -> vector store로 갈지"를 설계 문서에 먼저 고정한다.

예를 들면:

- C++ Core Guidelines HTML 업데이트
- parser 재실행
- canonical `cpp_core.yaml` 갱신 후보 생성
- 사람이 diff 검토 후 반영

## C와 C++ 관계

`c`와 `cpp`는 일부 규칙을 공유하지만 완전히 같은 언어로 취급하면 안 된다.

권장 구조:

- `native_memory_shared` pack
  - `c`, `cpp` 모두에 적용 가능한 메모리/자원 규칙
- `cpp_core` pack
  - RAII, smart pointer, move semantics
- `posix_c` 혹은 `c_project` pack
  - `goto cleanup`, ownership discipline, `malloc/free`, C API wrapper

즉 “C++ 규칙을 C에 억지 적용”하지 않고,
“공유 규칙 + 언어별 규칙” 조합으로 운영한다.

## Bash / Shell 주의사항

`bash`는 일반 프로그래밍 언어와 다르게 파일 경로만으로 language 추론이 부족할 수 있다.

따라서 아래를 같이 본다.

- file extension `.sh`
- shebang
- executable text file heuristic

대표 규칙 예시:

- quoting 누락
- unbound variable
- unsafe glob expansion
- `rm -rf "$var"` 보호
- `set -euo pipefail` 정책
- command substitution / pipeline error handling

## Python 주의사항

`python`은 문법 스타일뿐 아니라
타입 힌트, 예외 처리, context manager 사용 습관이 리뷰 품질에 직접 영향을 준다.

대표 규칙 예시:

- mutable default argument 금지
- broad `except` 지양
- `with`로 자원 수명 관리
- public API type hint 일관성
- sentinel / `None` 처리 명확화
- docstring과 실제 시그니처 불일치 방지

추천 profile 예시:

- `default`
- `typed_python`
- `data_pipeline_python`
- `service_backend_python`

## JavaScript / TypeScript 주의사항

`typescript`와 `javascript`는 생태계가 매우 가깝지만,
같은 규칙 세트로 완전히 합치면 타입 관련 판단이 흐려진다.

권장 구조:

- `javascript`
  - 런타임 동작, async 흐름, module boundary, Node/browser 차이
- `typescript`
  - `any` 남용, unsafe cast, narrowing, declaration/interface 품질
- `shared_web_javascript`
  - promise handling, event lifecycle, naming, API boundary

대표 규칙 예시:

- promise 반환값 누락
- floating promise
- `any` / `unknown` / assertion 남용
- optional field 접근 시 null safety 누락
- public exported type와 구현 불일치

## SQL 주의사항

`sql`은 다른 언어보다 dialect 차이가 크므로,
`language_id=sql`만으로 끝내지 말고 `dialect_id` 개념을 함께 두는 것이 좋다.

권장 예시:

- `language_id = sql`
- `dialect_id = ansi | postgresql | mysql | sqlite | bigquery | snowflake | oracle | t_sql`

SQL은 다른 언어와 달리 무료로 공개된 단일 authoritative style guide가 약하다.
따라서 아래 3층 구조로 운영하는 것이 현실적이다.

1. 공통 SQL 규칙
   - 명시적 `JOIN`
   - `SELECT *` 제한
   - alias naming 일관성
   - nullable comparison / aggregation 주의
2. dialect 규칙
   - PostgreSQL, MySQL, SQLite, BigQuery, Snowflake, Oracle, T-SQL 차이 반영
3. 프로젝트 규칙
   - migration SQL, OLTP SQL, analytics SQL, dbt SQL 같은 맥락별 제약 반영

문서 소스도 분리해서 보는 편이 좋다.

- style source
  - 공개 SQL style guide 문서 또는 SQLFluff rule set
- syntax/reference source
  - 각 DB vendor 공식 문서
- project source
  - 사내 naming, schema, migration, warehouse 규칙

파일 판별 예시:

- `*.sql`
- `migrations/**/*.sql`
- `db/**/*.sql`
- `models/**/*.sql`
- `seeds/**/*.sql`

필요하면 후속 단계에서 `context_kind`도 추가한다.

- `ddl`
- `dml`
- `migration`
- `analytics`
- `dbt_model`

이렇게 해야 같은 SQL이라도
OLTP query review와 warehouse/dbt review를 서로 다른 규칙 세트로 다룰 수 있다.

## YAML / K8s / CI 주의사항

`yaml`은 언어라기보다 serialization syntax이므로
실제 리뷰는 `context_id` 또는 `schema_family`를 함께 봐야 한다.

권장 예시:

- `language_id = yaml`
- `context_id = generic | kubernetes | github_actions | gitlab_ci | helm_values | docker_compose`

중요한 점:

- 같은 YAML이라도 Kubernetes manifest, Helm values, GitHub Actions, GitLab CI는 규칙이 전혀 다르다
- indentation/anchor 같은 문법 문제보다 schema 의미와 운영 안전성이 더 중요하다

파일 판별 예시:

- `*.yaml`
- `*.yml`
- `.github/workflows/*.yml`
- `.gitlab-ci.yml`
- `k8s/**/*.yaml`
- `charts/**/values.yaml`

대표 규칙 예시:

- duplicate key 위험
- string/boolean 혼동
- Kubernetes probe/resource/securityContext 누락
- GitHub Actions 권한 과다 부여
- GitLab CI stage/rules/include 복잡도 과다
- Helm values key typo와 schema 부재

## Dockerfile 주의사항

`dockerfile`은 일반 언어와 달리
build reproducibility, image size, runtime security를 함께 본다.

파일 판별 예시:

- `Dockerfile`
- `Dockerfile.*`
- `*.dockerfile`

대표 규칙 예시:

- mutable tag 대신 digest 또는 명시적 버전 pinning 검토
- multi-stage build 필요성
- `apt-get update` / install layer 관리
- root user 실행 지양
- build secret / token 이미지 내 유출 금지
- cache 효율을 해치는 `COPY . .` 남용

## Python / JavaScript / TypeScript / Java / Go / Rust 확장 방식

새 언어를 추가할 때는 아래 단위를 한 번에 추가한다.

1. `language_id`
2. `manifest.yaml`
3. `packs/*.yaml`
4. `profiles/*.yaml`
5. query plugin
6. examples / golden tests
7. review-bot provider hint

즉 “룰만 추가”해서 끝내지 않고,
리뷰 품질을 결정하는 query/prompt/profile까지 한 묶음으로 본다.

## 점진적 구현 순서

### Phase 1. C++ 구조 정리

목표:

- 현재 C++ 전용 구조를 language plugin 구조로 재배치
- 동작은 최대한 유지

해야 할 일:

- `source_family` 일반화
- `language_id` 도입
- `cpp_feature_extractor`를 plugin으로 이동
- `review-bot`의 C++ file filter 제거

### Phase 2. Canonical Rule Document 도입

목표:

- 사람이 수정하는 YAML 문서를 기준으로 ingest

해야 할 일:

- `rules/` 디렉터리 생성
- `pack/profile/manifest` 스키마 정의
- 기존 단일 C++ 규칙을 legacy path로 강등
- `rule_sources/` 디렉터리와 manifest 구조를 설계
- 각 언어별 raw rule source 문서는 후속 execution phase에서 작성
- raw source는 import draft 생성 경로로만 연결
- runtime canonical source는 `rules/**/*.yaml`로 고정

### Phase 3. Shared / C / Bash 도입

이유:

- 구현 난이도 대비 효과가 좋다
- C/C++/shell은 현재 운영 환경과도 연결되기 쉽다

### Phase 4. Python / JavaScript / TypeScript 추가

이유:

- 적용 가능한 저장소 범위가 넓다
- query/plugin 일반화의 효과를 빨리 확인할 수 있다

### Phase 5. SQL / YAML / Dockerfile 추가

이유:

- 코드 외 reviewable artifact까지 구조가 확장되는지 검증할 수 있다
- 운영 안전성과 CI/CD 품질에 직접 연결된다

### Phase 6. Java / Go / Rust 추가

이 단계부터 언어별 query plugin과 example corpus를 별도 강화한다.

### Phase 7. Web Admin UI

canonical YAML이 안정화된 뒤에 붙인다.

## 공개 참고 문서 추천

아래 문서들은 canonical rule pack을 만들 때 1차 참고 문서로 삼기 좋다.

- Python
  - [PEP 8](https://peps.python.org/pep-0008/)
  - [PEP 257](https://peps.python.org/pep-0257/)
  - [Python `typing` library reference](https://docs.python.org/3/library/typing.html)
  - [Static Typing with Python](https://typing.python.org/)
- TypeScript
  - [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro)
  - [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)
- JavaScript
  - [MDN JavaScript Guide](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide)
  - [Google JavaScript Style Guide](https://google.github.io/styleguide/jsguide.html)
- YAML
  - [YAML Specification Index](https://yaml.org/spec/)
  - [Workflow syntax for GitHub Actions](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions)
  - [GitLab CI/CD YAML syntax reference](https://docs.gitlab.com/ci/yaml/)
  - [Helm Chart Best Practices](https://docs.helm.sh/docs/chart_best_practices/)
- Kubernetes YAML
  - [Kubernetes API Conventions](https://github.com/kubernetes/community/blob/master/contributors/devel/sig-architecture/api-conventions.md)
  - [Kubernetes API Concepts](https://kubernetes.io/docs/reference/using-api/api-concepts)
- Dockerfile
  - [Dockerfile reference](https://docs.docker.com/reference/builder)
  - [Dockerfile overview](https://docs.docker.com/build/concepts/dockerfile/)
  - [Docker image best practices](https://docs.docker.com/build/building/best-practices/)

## 언어별 Raw Rule Source 문서 구성 원칙

아래는 실제 문서를 지금 만드는 것이 아니라,
나중에 어떤 파일 세트로 구성할지 설계상 고정하는 목록이다.

### Python

- `python/pep8_style.md`
- `python/pep257_docstrings.md`
- `python/typing_guidance.md`

### TypeScript

- `typescript/typescript_handbook.md`
- `typescript/google_typescript_style.md`

### JavaScript

- `javascript/mdn_javascript_guide.md`
- `javascript/google_javascript_style.md`

### YAML

- `yaml/yaml_spec.md`
- `yaml/github_actions_workflows.md`
- `yaml/gitlab_ci_yaml.md`
- `yaml/helm_values_best_practices.md`

### Kubernetes YAML

- `yaml/kubernetes_api_conventions.md`
- `yaml/kubernetes_api_concepts.md`

### Dockerfile

- `dockerfile/dockerfile_reference.md`
- `dockerfile/docker_image_best_practices.md`

### SQL

SQL은 단일 authoritative 공개 source가 약하므로 아래 3층으로 설계한다.

- `sql/sql_shared_style.md`
- `sql/postgresql_notes.md`
- `sql/analytics_sql_notes.md`

### Bash

- `bash/shell_safety.md`

### Java

- `java/effective_java_notes.md`
- `java/project_java_api_design.md`

설계 의도:

- 공개 best practice 요약과 프로젝트 API 설계 규칙을 분리한다
- 객체 설계, 예외 처리, 컬렉션 사용, 불변성, 경계 계층 규칙을 pack으로 normalize 한다

예상 pack target:

- `effective_java`
- `project_java`

### Go

- `go/go_project_practices.md`

후속 execution phase에서 필요하면 아래처럼 분리 확장한다.

- `go/concurrency_safety.md`
- `go/api_and_package_design.md`

설계 의도:

- 초기에는 idiomatic Go, error handling, context 전달, package 경계, goroutine/channel 안전성 규칙을 하나의 seed 문서로 시작한다
- 이후 concurrency와 API design 규칙을 독립 pack으로 분리 가능하게 둔다

예상 pack target:

- `project_go`
- 필요 시 `go_concurrency`, `go_api_design`

### Rust

- `rust/rust_project_practices.md`

후속 execution phase에서 필요하면 아래처럼 분리 확장한다.

- `rust/error_handling.md`
- `rust/unsafe_and_ffi.md`

설계 의도:

- ownership/borrowing, `Result` 처리, panic 제한, async 규칙을 기본 seed 문서에 담는다
- `unsafe`, FFI, 고급 에러 처리 규칙은 별도 pack으로 확장 가능하게 둔다

예상 pack target:

- `project_rust`
- 필요 시 `rust_error_handling`, `rust_unsafe_ffi`

### C

- `c/posix_c_safety.md`
- `c/native_memory_shared.md`

설계 의도:

- C 전용 규칙과 C/C++ 공통 자원 관리 규칙을 분리한다
- `malloc/free`, cleanup discipline, POSIX API 오류 처리, 버퍼 경계 규칙을 C 전용 문서에 둔다

예상 pack target:

- `posix_c`
- `native_memory_shared`

### C++

- `cpp/cpp_core_guidelines.md`
- `cpp/native_memory_shared.md`

설계 의도:

- C++ 전용 규칙과 C/C++ 공통 자원 관리 규칙을 분리한다
- RAII, smart pointer, move semantics, ownership modeling, exception safety 규칙을 C++ 전용 문서에 둔다

예상 pack target:

- `cpp_core`
- `native_memory_shared`

즉 requirement 2 설계 범위에서는
"파일 이름, 메타데이터, pack target 연결 방식"까지를 고정하고,
실제 문서 작성은 별도 작업으로 분리한다.

## 테스트 전략

언어별 테스트는 최소 아래 4층으로 나눈다.

1. parser / manifest validation 테스트
2. query pattern extraction 테스트
3. retrieval + rerank golden example 테스트
4. `review-bot` end-to-end per-language smoke

예시 디렉터리:

```text
review-engine/tests/languages/
  cpp/
  c/
  python/
  typescript/
  javascript/
  java/
  go/
  rust/
  bash/
  sql/
  yaml/
  dockerfile/
```

각 언어마다 최소한 아래를 가져간다.

- positive examples
- negative examples
- false-positive regression
- rule pack loading test

## 호환성 전략

초기 migration 단계에서는 기존 필드를 완전히 없애지 말고 점진적으로 옮긴다.

예시:

- `source_family`는 일단 유지
- 신규 필드 `language_id`, `rule_pack`, `rule_uid` 추가
- 내부 구현은 신규 필드를 우선 사용
- 외부 응답은 한동안 기존 필드도 함께 반환

이렇게 해야 `review-bot`과 기존 문서/analytics를 한 번에 깨지 않는다.

## 권장 결정

이 설계에서 가장 중요한 결정은 아래 두 가지다.

1. canonical rule source는 YAML 문서로 둔다
2. retrieval store는 언어별 collection으로 분리한다

이 둘을 먼저 고정하면,

- AI가 규칙 문서를 수정하고
- 사람이 Git diff로 검토하고
- CLI로 reindex 하고
- 나중에 웹 UI로 편집하는 흐름

이 자연스럽게 이어진다.

## 최종 제안

지금 당장 가장 좋은 출발점은 다음이다.

1. `rule_sources/`와 `rules/`를 분리된 source layer로 고정한다.
2. `rules/`를 runtime canonical source로 고정하고, `rule_sources/`는 bootstrap/import source로 분리한다.
3. 이번 단계에서는 각 언어별 raw rule source 문서를 실제로 만들지 않고 구조와 메타데이터만 설계 문서에 고정한다.
4. 다음 execution phase에서 언어별 raw rule source 문서를 작성하고 import draft를 거쳐 canonical pack으로 반영한다.
5. 그 뒤 `language_id`, `rule_pack`, `rule_uid` 기반 ingest/runtime을 확장한다.
6. 마지막에 웹 편집 UI를 붙인다.

이 방식이면 새 branch를 받은 환경에서도
어떤 raw source에서 규칙을 다시 만들고 vector DB를 다시 채워야 하는지 바로 알 수 있고,
실제 execution 단계에서도 범위를 안전하게 나눌 수 있다.
