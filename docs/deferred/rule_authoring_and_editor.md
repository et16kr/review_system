# Deferred Rule Authoring And Editor Work

## Purpose

이 문서는 rule lifecycle CLI, 수동 rule authoring UX, editor/UI처럼
rule 운영 자체를 더 편하게 만드는 deferred 작업을 모아 둔다.

마지막 코드 상태 점검일: `2026-04-24`

## 1. Manual Rule Editor / Authoring UX

현재 미루는 이유:

- canonical YAML과 Git history를 기준으로 수동 편집하는 토대는 이미 있다.
- 하지만 별도 editor/UI를 넣으려면 rule state model, validation, public/private extension 경계를 먼저 굳혀야 한다.
- 지금은 editor보다 rule gap closure와 운영 품질 유지가 더 직접적인 가치가 크다.

착수 전 선행 조건:

1. rule lifecycle CLI의 최소 범위를 먼저 정한다.
2. canonical YAML schema, profile/policy merge, extension boundary를 명확히 유지한다.
3. UI가 별도 저장 모델을 만들지 않도록 운영 원칙을 먼저 고정한다.

착수 후 해야 할 일:

1. 수동 편집 흐름에서 자주 틀리는 metadata 필드와 validation failure를 정리한다.
2. rule authoring form 또는 editor가 수정해야 할 canonical 파일 경로를 명확히 드러낸다.
3. preview, validate, ingest, regression 연결 방식을 설계한다.
4. 웹 UI를 붙이더라도 Git 기반 운영과 충돌하지 않도록 감사 경로를 유지한다.
