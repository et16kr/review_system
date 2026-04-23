# Review Engine Multi-Language Support Requirements

## 목적

이 문서는 `review-engine` / `review-bot`이
C++ 중심 구조를 넘어 다양한 언어와 reviewable artifact를 지원하기 위해 필요한
요구사항을 정의한다.

이 문서의 목적은 구현을 바로 지시하는 것이 아니라,
다국어 지원 설계가 만족해야 할 기준을 고정하는 것이다.

## 배경

현재 시스템은 사실상 다음 전제를 갖는다.

- C/C++ 중심 file filtering
- C++ 전용 query pattern extraction
- C++ 중심 prompt phrasing
- 규칙 데이터 모델도 언어 일반화가 충분하지 않음

하지만 실제 공개용 제품은 아래 대상을 다룰 수 있어야 한다.

- `cpp`
- `c`
- `cuda`
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

여기서 `yaml`, `dockerfile`은 일반 언어라기보다
구성 파일과 build artifact로 취급한다.

## 문제 정의

현재 구조 위에 언어를 계속 추가하면 다음 문제가 생긴다.

- `if language == ...`가 코드 전반에 늘어난다
- query detector와 prompt가 언어별로 얽힌다
- rule pack 관리가 언어별로 독립되지 못한다
- 특정 artifact 유형을 억지로 일반 프로그래밍 언어처럼 다루게 된다

## 목표

### Goal 1. 언어 일반화

- 엔진이 여러 언어를 일관된 모델로 표현할 수 있어야 한다.

### Goal 2. 언어별 독립성

- 새 언어를 추가할 때 기존 언어 구현을 크게 건드리지 않아야 한다.

### Goal 3. artifact 다양성 수용

- `sql`, `yaml`, `dockerfile` 같은 구성/배포 파일도
  별도 맥락을 가진 review 대상로 수용할 수 있어야 한다.

## 범위

범위에 포함:

- language registry
- file classification
- language-specific query plugin
- language-aware rule pack selection
- language-aware prompt hinting
- test corpus structure

범위에 포함하지 않음:

- 각 언어 규칙의 실제 작성 완료
- AST 기반 deep semantic analyzer 전면 도입
- 언어별 autofix 엔진 구현

## 지원 대상

최소한 아래 대상을 고려한 구조여야 한다.

- `cpp`
- `c`
- `cuda`
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

## 핵심 개념

### 1. language_id

엔진이 이해하는 1차 언어 식별자다.

### 2. profile_id

같은 언어 안에서도 맥락별 규칙 조합을 결정하는 단위다.

예시:

- `default`
- `typed_python`
- `frontend_strict`
- `analytics_warehouse`
- `github_actions`

### 3. context_id / dialect_id

일부 대상은 언어만으로 충분하지 않다.

예시:

- `sql + postgresql`
- `sql + bigquery`
- `yaml + kubernetes`
- `yaml + github_actions`

## 기능 요구사항

### FR-1. 언어 식별 모델

- 엔진은 각 리뷰 요청에 대해 `language_id`를 표현할 수 있어야 한다.
- 필요 시 `profile_id`, `context_id`, `dialect_id`를 함께 표현할 수 있어야 한다.

### FR-2. 파일 분류

- 파일 경로, 확장자, shebang, 디렉터리 패턴 등을 바탕으로 리뷰 대상을 분류할 수 있어야 한다.
- `.h`처럼 ambiguity가 있는 파일은 정책 기반으로 처리할 수 있어야 한다.
- `Dockerfile`, `.gitlab-ci.yml`, `.github/workflows/*.yml` 같은 특수 경로도 다룰 수 있어야 한다.

### FR-3. language registry

- 언어별 메타데이터를 중앙 registry로 관리할 수 있어야 한다.
- registry는 최소한 아래를 제공해야 한다.
  - reviewable 여부
  - file pattern
  - query plugin 연결
  - 기본 profile

### FR-4. language-specific query plugin

- 각 언어는 독립적인 query detector / query text builder를 가질 수 있어야 한다.
- 한 언어의 detector를 수정해도 다른 언어 detector가 직접 영향을 받지 않아야 한다.

### FR-5. rule pack selection

- 언어별로 기본 rule pack과 shared rule pack을 함께 선택할 수 있어야 한다.
- 필요 시 context 또는 dialect에 따라 추가 pack을 결합할 수 있어야 한다.

### FR-6. prompt specialization

- provider prompt는 언어별 관점을 반영할 수 있어야 한다.
- 단, 특정 언어 하드코딩이 전역 prompt에 섞이지 않도록 구조화되어야 한다.

### FR-7. review-bot 연동

- `review-bot`은 더 이상 C++ 전용 file filter에 의존하면 안 된다.
- detect phase에서 각 file의 `language_id`를 판별해 `review-engine`으로 전달할 수 있어야 한다.

### FR-8. YAML / SQL / Dockerfile 특수성 지원

- `yaml`은 `kubernetes`, `github_actions`, `gitlab_ci`, `helm_values` 같은 맥락을 구분할 수 있어야 한다.
- `sql`은 dialect를 반영할 수 있어야 한다.
- `dockerfile`은 언어라기보다 build/runtime policy 대상으로 다뤄질 수 있어야 한다.

### FR-9. 언어 추가 절차의 반복 가능성

- 새 언어를 추가할 때 필요한 작업 단위가 명확해야 한다.
- 최소 작업 단위 예시:
  - language manifest
  - rule pack
  - query plugin
  - test examples
  - prompt overlay

## 비기능 요구사항

### NFR-1. 확장성

- 새 언어 추가가 기존 언어 구현을 대규모 수정하지 않아야 한다.

### NFR-2. 격리성

- 언어별 retrieval 오염이 최소화되어야 한다.

### NFR-3. 운영 가능성

- 언어별 collection rebuild, golden test, smoke test를 분리해서 수행할 수 있어야 한다.

## 비목표

- 모든 언어를 한 번에 구현
- 완전 자동 언어 판별 100% 정확도
- 모든 언어에 대해 AST/LSP 통합
- 모든 언어의 autofix 지원

## 완료 조건

아래 조건을 만족하면 이 요구사항이 충족된 것으로 본다.

1. 언어 식별 모델이 데이터 구조와 API에 반영된다.
2. C++ 전용 filter와 query 하드코딩이 언어 plugin 구조로 일반화된다.
3. 최소 하나 이상의 비-C++ 언어가 같은 구조 위에서 동작한다.
4. `yaml`, `sql`, `dockerfile`처럼 특수 artifact도 언어/맥락 모델로 표현 가능하다.
5. 언어별 테스트 구조가 정립된다.

## 설계 문서에 반드시 포함되어야 할 항목

후속 설계 문서는 최소한 아래를 다뤄야 한다.

1. language registry schema
2. file classification 규칙
3. query plugin 인터페이스
4. rule pack / profile / dialect 결합 방식
5. review-bot detect flow 연동 방식
6. vector store / collection 분리 전략
7. 언어별 테스트 전략
8. 단계별 언어 도입 순서
