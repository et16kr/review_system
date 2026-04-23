# Review Engine Organization Rule System Requirements

## 목적

이 문서는 현재 특정 조직 전용으로 결합되어 있는 규칙 우선순위, 내부 규칙 적재,
패턴 힌트, 프롬프트 특화 구조를 제거하고,
이를 어느 조직에서나 사용할 수 있는 범용 `organization rule system`으로
대체하기 위한 요구사항을 정의한다.

핵심 목표는 두 가지다.

1. 공개 저장소에는 특정 회사 전용 코드나 데이터가 남지 않게 한다.
2. 사내 설치 시에는 조직별 private rule pack을 다시 붙일 수 있게 한다.

## 배경

legacy 구조는 다음 전제를 가졌다.

- `source_family`가 조직별 C++ family와 public C++ family로 사실상 고정되어 있었다
- 내부 규칙은 legacy internal guideline markdown에서 읽었다
- 내부 규칙은 항상 외부 규칙보다 높은 우선순위를 가졌다
- 일부 query heuristic과 provider prompt가 조직 고유 C++ 규칙을 전제로 했다

이 구조는 사내 정확도에는 유리했지만,
공개 배포 기준에서는 다음 문제가 있다.

- 특정 회사명이 코드와 문서에 직접 남는다
- 조직별 규칙 기능이 아니라 특정 조직 전용 기능처럼 보인다
- 다른 회사가 같은 구조를 재사용하기 어렵다
- 공개 코어와 private extension의 경계가 불명확하다

## 문제 정의

해결해야 할 문제는 아래와 같다.

1. 특정 회사명을 포함한 하드코딩을 제거해야 한다.
2. 내부 규칙 우선순위 로직을 일반적인 organization policy로 바꿔야 한다.
3. query heuristic, prompt overlay, rule pack 우선순위를 private extension으로 주입할 수 있어야 한다.
4. private extension이 없는 공개 설치도 완전한 제품으로 동작해야 한다.

## 목표

### Goal 1. 공개 코어에서 특정 회사 흔적 제거

- 공개 저장소 기본 코드에 특정 회사명이나 조직 전용 표현이 남지 않는다.
- 공개 테스트, fixture, 문서, 예제 데이터에도 특정 회사 전용 내용이 남지 않는다.

### Goal 2. 범용 organization rule system 제공

- 어느 조직이든 private rule pack을 주입할 수 있다.
- public guideline과 organization guideline을 같은 엔진 위에서 함께 운영할 수 있다.
- organization guideline의 우선순위와 충돌 정책을 설정 기반으로 정의할 수 있다.

### Goal 3. 사내 재설치 가능성 유지

- 공개판에서 제거된 특정 회사 규칙을,
  private package 또는 private repository를 통해 다시 붙일 수 있어야 한다.
- 이때 공개 코어 코드는 수정하지 않고 확장만으로 복원 가능해야 한다.

## 범위

이번 요구사항 문서의 범위는 아래와 같다.

- rule source classification 일반화
- authority / priority / conflict policy 일반화
- organization rule pack loading
- organization-specific query detector 확장 지점
- organization-specific prompt overlay 확장 지점
- public/private packaging 경계 정의

이번 범위에 포함하지 않는 것은 아래와 같다.

- 다국어 전체 구현
- 웹 UI 구현
- 조직별 detector를 자동 생성하는 기능
- private repository 배포 자동화 세부 구현

## 핵심 개념

### 1. public rule pack

공개 문서와 공개 표준에서 온 규칙 묶음이다.

예시:

- `cpp_core`
- `effective_java`
- `pep8_python`
- `dockerfile_best_practices`

### 2. organization rule pack

특정 조직 내부 정책에서 온 규칙 묶음이다.

예시:

- `org_cpp`
- `org_sql`
- `org_ci`

중요:

- 공개 코어는 `organization rule pack`이라는 개념만 알아야 한다
- 특정 회사명은 알아서는 안 된다

### 3. organization policy

조직 내부 규칙의 우선순위, 충돌 정책, prompt overlay, detector binding을 정의하는 설정 단위다.

## 기능 요구사항

### FR-1. 조직 전용 코드 제거

- 공개 코어 코드에서 특정 회사명 하드코딩을 제거해야 한다.
- 데이터 모델은 특정 회사명을 enum literal로 가지면 안 된다.
- 기본 prompt는 특정 회사 코드베이스를 가정하면 안 된다.

### FR-2. 규칙 출처 일반화

- 현재의 `source_family`는 더 일반적인 구조로 대체되거나 호환 가능하게 확장되어야 한다.
- 최소한 아래 개념을 표현할 수 있어야 한다.
  - `language_id`
  - `rule_pack`
  - `source_kind`
  - `authority`

### FR-3. organization rule pack 주입

- 공개 코어는 외부 디렉터리 또는 패키지에서 organization rule pack을 읽을 수 있어야 한다.
- organization rule pack이 없으면 public pack만으로 정상 동작해야 한다.
- organization rule pack은 언어별로 독립적으로 추가될 수 있어야 한다.

### FR-4. 우선순위 / 충돌 정책 일반화

- organization rule pack이 public rule pack보다 우선할지 여부를 설정으로 정의할 수 있어야 한다.
- 충돌 정책은 특정 회사명을 기준으로 하드코딩하면 안 된다.
- 최소 정책:
  - `authoritative`
  - `compatible`
  - `overridden`
  - `excluded`

### FR-5. organization-specific detector 확장 지점

- query analysis는 organization-specific detector를 추가할 수 있어야 한다.
- detector는 공개 코어와 분리된 private module로 구현 가능해야 한다.
- detector가 없더라도 공개 코어의 기본 detector는 정상 동작해야 한다.

### FR-6. organization-specific prompt overlay

- provider prompt는 기본 public prompt와 organization overlay를 분리해야 한다.
- organization overlay는 profile 또는 configuration으로 선택 가능해야 한다.
- overlay가 없으면 공개 기본 prompt를 사용해야 한다.

### FR-7. public/private packaging 분리

- 공개 저장소만으로 배포 가능한 public build가 있어야 한다.
- private package를 추가 설치하면 organization rules가 활성화되는 구조여야 한다.
- private package가 없어도 import error 없이 동작해야 한다.

### FR-8. 테스트 분리

- 공개 코어 테스트는 private pack 없이 통과해야 한다.
- organization rule tests는 private 환경에서 별도로 운영할 수 있어야 한다.
- public CI는 private fixture에 의존하면 안 된다.

## 비기능 요구사항

### NFR-1. 공개 저장소 청결성

- 공개 저장소 코드, 테스트, 문서, fixture, generated data에 특정 회사 비공개 맥락이 노출되지 않아야 한다.

### NFR-2. 역확장 가능성

- 나중에 어떤 조직이든 같은 구조로 organization rule pack을 붙일 수 있어야 한다.

### NFR-3. 기본 동작 안정성

- organization rule pack이 없는 경우에도 기존 public guideline review 품질이 크게 훼손되지 않아야 한다.

## 비목표

- 특정 회사 private pack의 실제 내용 작성
- 특정 회사 detector 구현
- 사내 전용 배포 문서 작성
- private dependency resolver 설계 세부화

## 완료 조건

아래 조건을 만족하면 이 요구사항이 충족된 것으로 본다.

1. 공개 코어 코드에서 특정 회사명과 전용 규칙 ID가 제거된다.
2. public rule pack만으로 ingest / retrieval / review가 동작한다.
3. organization rule pack을 별도 위치에서 주입할 수 있다.
4. authority / priority / conflict policy가 organization-agnostic 구조가 된다.
5. prompt overlay와 detector extension이 공개 코어 인터페이스로 분리된다.

## 설계 문서에 반드시 포함되어야 할 항목

후속 설계 문서는 최소한 아래를 다뤄야 한다.

1. public core와 private extension의 경계
2. organization rule pack loading 방식
3. authority / conflict policy schema
4. detector plugin 인터페이스
5. provider prompt overlay 구조
6. public CI와 private CI 분리 전략
7. 기존 organization-coupled 코드의 migration plan
