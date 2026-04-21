# Review Engine Rule Management Requirements

## 목적

이 문서는 규칙을 추가, 수정, 비활성화, 삭제하는 운영 방식을
사람과 도구 모두에게 일관되게 제공하기 위한 요구사항을 정의한다.

핵심은 다음과 같다.

1. 규칙을 수동 파일 편집만으로도 안전하게 관리할 수 있어야 한다.
2. 나중에 CLI나 웹 UI를 붙여도 같은 canonical source를 사용해야 한다.
3. rule lifecycle이 재현 가능하고 감사 가능해야 한다.

## 배경

지금까지는 규칙 데이터가 코드, JSON 산출물, 파서 결과, 설정 파일에 분산되어 있었다.
이 상태에서는 다음 문제가 발생한다.

- 규칙을 어디서 수정해야 하는지 불명확하다
- 추가/삭제 과정이 사람마다 달라질 수 있다
- generated artifact와 canonical source의 경계가 모호하다
- 다국어 확장 시 운영 복잡도가 급격히 늘어난다

따라서 구현 전에 먼저 “규칙 관리의 표준 절차”를 고정할 필요가 있다.

## 문제 정의

해결해야 할 문제는 아래와 같다.

1. canonical rule source를 명확히 해야 한다.
2. 규칙 추가/삭제 절차를 표준화해야 한다.
3. 검증, ingest, reindex를 같은 흐름으로 연결해야 한다.
4. 나중에 웹 UI를 붙여도 Git 기반 운영과 충돌하지 않아야 한다.

## 목표

### Goal 1. canonical source 확립

- 사람이 수정하는 유일한 기준 문서를 정한다.

### Goal 2. 절차 표준화

- 규칙 추가, 수정, 비활성화, 삭제, 가져오기 절차를 문서와 도구로 표준화한다.

### Goal 3. 도구 확장 가능성 확보

- 초기에는 CLI와 문서만으로 운영 가능해야 한다.
- 이후 웹 UI를 붙여도 같은 저장 구조를 재사용해야 한다.

## 범위

범위에 포함:

- canonical rule file format
- pack / profile / manifest 구조
- validate / ingest / reindex 절차
- add / disable / delete lifecycle
- rule metadata schema
- generated artifact와 canonical source의 경계

범위에 포함하지 않음:

- 웹 UI 구현
- 모든 언어 규칙의 실제 작성
- private organization rule pack distribution 문제

## 핵심 개념

### 1. canonical rule source

사람과 도구가 수정하는 진짜 기준 문서다.

### 2. generated artifact

ingest 이후 생성되는 JSON dataset, vector collection, cache 파일이다.

### 3. rule lifecycle

규칙이 생성되고, 수정되고, 비활성화되고, 제거되는 전 과정을 말한다.

## 기능 요구사항

### FR-1. canonical rule format

- canonical rule source는 구조화 포맷이어야 한다.
- 사람이 읽고 Git diff로 검토하기 쉬워야 한다.
- 주석과 메타데이터를 담기 쉬워야 한다.

권장 기본 형식:

- YAML

### FR-2. directory layout

- 규칙은 언어별 / pack별로 분리된 디렉터리 구조를 가져야 한다.
- 최소 구조:
  - `manifest`
  - `packs`
  - `profiles`
  - 필요 시 `imports`

### FR-3. 규칙 추가 절차

- 새 규칙을 추가하는 표준 절차가 문서화되어야 한다.
- 도구 없이도 수행 가능해야 하며,
  향후 CLI로 자동화 가능해야 한다.

최소 단계:

1. canonical pack 수정 또는 생성
2. schema validation
3. ingest
4. reindex
5. example / regression test

### FR-4. 규칙 비활성화 절차

- 규칙을 완전히 삭제하지 않고 비활성화할 수 있어야 한다.
- 비활성화 이유를 메타데이터로 남길 수 있어야 한다.
- 비활성화 규칙은 generated artifact에서 제외되거나 별도 상태로 표현되어야 한다.

### FR-5. 규칙 삭제 절차

- 잘못 추가된 규칙이나 더 이상 유지하지 않는 규칙을 삭제할 수 있어야 한다.
- 삭제 시에는 어떤 이유로 제거했는지 Git history와 문서에서 추적 가능해야 한다.

### FR-6. 규칙 수정 절차

- 제목, 요약, 카테고리, fix guidance, tags, trigger metadata 등을 수정할 수 있어야 한다.
- 수정 후 validate와 ingest를 일관된 절차로 실행할 수 있어야 한다.

### FR-7. import와 manual edit 분리

- 외부 문서에서 import한 결과와 사람이 직접 다듬은 canonical source를 구분해야 한다.
- raw import 결과를 그대로 운영 데이터로 쓰면 안 된다.

### FR-8. CLI 지원

최소한 아래 기능은 CLI로 지원 가능해야 한다.

- `validate`
- `list`
- `show`
- `ingest`
- `reindex`
- `disable`
- `enable`

후속 단계에서 추가 가능:

- `add`
- `delete`
- `import`

### FR-9. 웹 UI 호환성

- 나중에 웹 UI를 붙일 때도 canonical YAML을 수정하는 구조여야 한다.
- 웹 UI가 별도 저장소나 별도 데이터 모델을 만들면 안 된다.

### FR-10. 감사 가능성

- 누가 어떤 규칙을 언제 왜 바꿨는지 Git history와 metadata로 추적 가능해야 한다.
- 최소한 rule metadata에 다음 성격의 정보를 담을 수 있어야 한다.
  - 생성 출처
  - 상태
  - 비활성화 여부
  - 메모 또는 rationale

## 비기능 요구사항

### NFR-1. 사람이 관리 가능해야 함

- 전용 UI가 없어도 운영 가능해야 한다.

### NFR-2. 재현 가능해야 함

- 같은 canonical source에서 같은 dataset과 reindex 결과를 재생성할 수 있어야 한다.

### NFR-3. 변경 영향이 예측 가능해야 함

- 규칙 수정 후 어떤 테스트와 reindex가 필요한지 명확해야 한다.

## 비목표

- 완전한 GUI rule editor 즉시 구현
- 자동 rule generation 전면 도입
- 모든 변경을 데이터베이스 중심으로 운영

## 완료 조건

아래 조건을 만족하면 이 요구사항이 충족된 것으로 본다.

1. canonical rule source 형식과 디렉터리 구조가 확정된다.
2. add / modify / disable / delete의 표준 절차가 문서화된다.
3. validate / ingest / reindex 흐름이 정립된다.
4. generated artifact와 canonical source의 역할이 분리된다.
5. 최소 CLI 범위가 정의된다.

## 설계 문서에 반드시 포함되어야 할 항목

후속 설계 문서는 최소한 아래를 다뤄야 한다.

1. canonical YAML schema
2. directory layout
3. rule state model
4. validate / ingest / reindex CLI 설계
5. import pipeline과 manual edit pipeline 분리
6. Git-based 운영 절차
7. 향후 웹 UI 연계 방식

