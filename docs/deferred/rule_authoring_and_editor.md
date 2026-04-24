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
4. canonical YAML authoring model이 unknown key를 silent ignore하지 않도록 fail-fast guardrail을 둔다.
5. missing/duplicate selected pack과 default profile selection 의미를 먼저 정리한다.

착수 후 해야 할 일:

1. 수동 편집 흐름에서 자주 틀리는 metadata 필드와 validation failure를 정리한다.
2. rule authoring form 또는 editor가 수정해야 할 canonical 파일 경로를 명확히 드러낸다.
3. preview, validate, ingest, regression 연결 방식을 설계한다.
4. 웹 UI를 붙이더라도 Git 기반 운영과 충돌하지 않도록 감사 경로를 유지한다.

## 2. Private Rule Packaging Readiness

현재 미루는 이유:

- filesystem extension root와 private extension runtime test는 있지만, 배포 가능한 package shape,
  version/compatibility metadata, install/update path는 아직 owner가 없다.
- private generated artifact와 public canonical artifact를 섞으면 review reproducibility가 약해진다.
- packaging을 먼저 구현하면 schema strictness와 extension boundary가 흔들릴 수 있다.

착수 전 선행 조건:

1. canonical YAML unknown key rejection과 pack/profile fail-fast guardrail을 먼저 닫는다.
2. package manifest가 포함해야 할 최소 metadata를 정한다.
   - package id
   - version
   - compatible engine schema/runtime version
   - included packs/profiles/policies/source manifests
3. private generated artifact를 repo canonical artifact와 분리하는 위치와 naming rule을 정한다.
4. install/update/rollback 절차와 validation gate를 정한다.

착수 후 해야 할 일:

1. `review-engine/examples/extensions/private_org_cpp/` 수준의 filesystem extension을
   installable package shape로 승격할지 결정한다.
2. package validation CLI 또는 existing ingest validation 확장 지점을 정한다.
3. private package가 runtime retrieval, source coverage, lifecycle CLI와 충돌하지 않는지
   deterministic test를 추가한다.
