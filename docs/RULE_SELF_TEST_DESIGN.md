# Rule Self-Test Design

마지막 코드 상태 점검일: `2026-04-26`

## 1. 결론

가능하다. GitLab smoke나 `review-bot` lifecycle 없이도 `review-engine` 안에서
language/rule별 self-test를 만들 수 있다.

다만 모든 rule을 같은 방식으로 "위배 코드를 넣으면 inline finding이 나온다"로 판정하면 안 된다.
현재 rule model은 `auto_review`와 `reference_only`를 의도적으로 분리한다. 따라서 self-test의
목표는 아래처럼 잡는다.

1. `auto_review` rule은 위배 코드에서 해당 rule이 검출되어야 한다.
2. 같은 rule의 적합 코드는 해당 rule을 검출하지 않아야 한다.
3. `reference_only` rule은 위배 성격의 specimen이 있어도 auto finding으로 나오면 안 된다.
4. 모든 enabled rule entry는 self-test case 또는 명시적인 waiver를 가져야 한다.

Codex나 LLM은 specimen을 생성하는 작성 보조로 쓸 수 있지만, CI에서 판정하는 oracle은
deterministic pytest와 `review-engine` runtime이어야 한다.

## 2. 현재 상태

현재 checkout 기준 rule entry 수:

| 구분 | 개수 |
| --- | ---: |
| 전체 enabled rule entry | 361 |
| `auto_review` | 265 |
| `reference_only` | 96 |
| `manual_only` | 0 |

현재 `examples/expected_retrieval_examples.json`는 retrieval expected case 91개를 갖고 있고,
서로 다른 `auto_review` rule 111개를 커버한다. 즉 이미 유용한 regression corpus가 있지만,
"각 rule별 적합/위배 specimen" 관점에서는 아직 coverage가 절반보다 작다.

Detector hint 기준 직접 검증 가능성:

| 언어 | 전체 | auto | reference | direct-hinted auto |
| --- | ---: | ---: | ---: | ---: |
| bash | 15 | 12 | 3 | 12 |
| c | 16 | 11 | 5 | 11 |
| cpp | 54 | 44 | 10 | 29 |
| cuda | 55 | 36 | 19 | 36 |
| dockerfile | 16 | 15 | 1 | 15 |
| go | 17 | 15 | 2 | 15 |
| java | 19 | 14 | 5 | 14 |
| javascript | 20 | 15 | 5 | 15 |
| python | 28 | 18 | 10 | 18 |
| rust | 18 | 13 | 5 | 13 |
| shared | 15 | 7 | 8 | 7 |
| sql | 30 | 22 | 8 | 22 |
| typescript | 29 | 22 | 7 | 22 |
| yaml | 29 | 21 | 8 | 21 |

판단:

- `auto_review` 265개 중 250개는 현재 query plugin의 direct hint 경로로 self-test gate를 만들 수 있다.
- 나머지 15개는 모두 C++ rule이다. trigger metadata는 있지만 direct hint mapping이 없어
  retrieval similarity에 더 의존한다.
- `shared` auto rule 7개는 shared plugin으로는 direct hint가 있지만, 일반 host language review가
  항상 shared detector를 함께 실행하는 구조는 아니다. self-test는 우선 explicit `language_id=shared`
  case로 막고, 이후 host-language 적용 테스트를 별도 추가한다.

## 3. Target Scope

### 필수 대상

필수 gate는 enabled `auto_review` rule 265개다.

각 rule은 최소 하나의 violating case와 하나의 compliant case를 가져야 한다.

- violating case:
  - `review_code` 또는 `review_diff` 결과에 target `rule_no`가 포함되어야 한다.
  - 필요한 경우 `expected_patterns`, `language_id`, `profile_id`, `context_id`, `dialect_id`도
    함께 검증한다.
- compliant case:
  - 같은 target `rule_no`가 결과에 없어야 한다.
  - 가능한 한 violating case와 구조를 같게 두고, rule 위배 조건만 제거한다.

### accountability 대상

전체 enabled rule entry 361개는 manifest coverage 대상이다.

- `auto_review`: detection gate가 있거나 `waiver.reason`이 있어야 한다.
- `reference_only`: auto finding으로 나오지 않는 것을 검증하거나, reference collection/inspect
  가능한 것을 검증한다.
- disabled rule이 생기면 self-test 대상에서 제외하되, lifecycle CLI나 rule metadata test에서
  disabled 상태를 별도로 확인한다.

## 4. Fixture Layout

권장 layout:

```text
review-engine/examples/rule_self_tests/
  manifest.yaml
  cases/
    python/
      PY.1/
        violating.py
        compliant.py
      PY.FAPI.1/
        violating.py
        compliant.py
    yaml/
      YAML.CI.6/
        violating.yml
        compliant.yml
    dockerfile/
      DOCKER.1/
        violating.Dockerfile
        compliant.Dockerfile
```

`manifest.yaml`이 source of truth다. pytest는 directory scan이 아니라 manifest만 읽는다.
이렇게 해야 case가 생겼지만 gate에 연결되지 않은 상태를 막을 수 있다.

예시:

```yaml
schema_version: 1
cases:
  - case_id: python/PY.1/mutable-default
    rule_no: PY.1
    language_id: python
    reviewability: auto_review
    input_kind: code
    violating_path: cases/python/PY.1/violating.py
    compliant_path: cases/python/PY.1/compliant.py
    expected_patterns: [mutable_default]
    expected_rules: [PY.1]
    forbidden_rules_in_compliant: [PY.1]
    top_k: 12
    judgment: accepted
    judgment_note: Minimal function differs only by mutable default versus None sentinel.

  - case_id: yaml/YAML.CI.6/gitlab-remote-bootstrap
    rule_no: YAML.CI.6
    language_id: yaml
    profile_id: gitlab_ci
    context_id: gitlab_ci
    input_kind: code
    review_path: .gitlab-ci.yml
    violating_path: cases/yaml/YAML.CI.6/violating.yml
    compliant_path: cases/yaml/YAML.CI.6/compliant.yml
    expected_patterns: [ci_remote_bootstrap]
    expected_rules: [YAML.CI.6]
    forbidden_rules_in_compliant: [YAML.CI.6]
    top_k: 12
    judgment: accepted

  - case_id: shared/SEC.1/hardcoded-secret
    rule_no: SEC.1
    language_id: shared
    reviewability: auto_review
    input_kind: code
    violating_path: cases/shared/SEC.1/violating.txt
    compliant_path: cases/shared/SEC.1/compliant.txt
    expected_patterns: [hardcoded_secret]
    expected_rules: [SEC.1]
    forbidden_rules_in_compliant: [SEC.1]
    top_k: 12
    judgment: accepted

waivers:
  - rule_no: R.33
    language_id: cpp
    reason: needs_detector
    detail: Trigger metadata exists, but direct hint mapping does not yet make this rule a stable hard gate.
```

## 5. Pytest Contract

새 테스트 파일:

```text
review-engine/tests/test_rule_self_tests.py
```

필수 테스트:

1. `test_rule_self_test_manifest_is_valid`
   - manifest schema를 검증한다.
   - 모든 path가 repo-local이고 존재하는지 확인한다.
   - `expected_rules`가 target `rule_no`를 포함하는지 확인한다.

2. `test_every_enabled_rule_entry_is_accounted_for`
   - runtime YAML에서 enabled rule entry를 읽는다.
   - 모든 enabled `auto_review` rule은 case 또는 waiver를 가져야 한다.
   - 모든 enabled `reference_only` rule은 reference case 또는 waiver를 가져야 한다.
   - waiver는 `needs_detector`, `semantic_only`, `reference_only`, `covered_by_group_case`,
     `not_applicable_to_code` 중 하나처럼 좁은 enum으로 제한한다.

3. `test_violating_cases_detect_expected_rules`
   - `review_code` 또는 `review_diff`를 실행한다.
   - response의 `language_id/profile_id/context_id/dialect_id`를 manifest와 비교한다.
   - `detected_patterns`가 `expected_patterns`를 포함하는지 확인한다.
   - `results`에 `expected_rules`가 모두 포함되는지 확인한다.

4. `test_compliant_cases_do_not_detect_forbidden_rules`
   - compliant specimen을 같은 route로 실행한다.
   - `forbidden_rules_in_compliant`가 결과에 없음을 확인한다.
   - 필요하면 `forbidden_patterns_in_compliant`도 확인한다.

5. `test_reference_only_cases_are_not_auto_findings`
   - reference-only specimen을 실행했을 때 해당 rule이 `results`에 나오지 않아야 한다.
   - `inspect_rule` 또는 reference collection 조회로 rule 자체가 로드되는지는 별도 확인한다.

6. `test_self_test_coverage_does_not_regress`
   - generated coverage summary를 만들고, committed baseline보다 coverage가 감소하면 실패한다.
   - 초기에는 `auto_review` hard-gated coverage만 baseline으로 둔다.

권장 명령:

```bash
cd /home/et16/work/review_system/review-engine
uv run pytest tests/test_rule_self_tests.py -q
```

기존 regression과 같이 볼 때:

```bash
cd /home/et16/work/review_system/review-engine
uv run pytest \
  tests/test_rule_self_tests.py \
  tests/test_query_conversion.py \
  tests/test_expected_examples.py \
  tests/test_multilang_regressions.py \
  -q
```

## 6. 판정 기준

### Accepted

아래를 모두 만족하면 accepted다.

- violating specimen이 문법적으로 그 언어의 코드로 보인다.
- 위배 조건이 target rule의 title/summary/fix guidance와 직접 연결된다.
- detector pattern이 의도한 pattern으로 나온다.
- retrieval/applicability 이후 target rule이 결과에 들어온다.
- compliant specimen은 같은 구조에서 위배 조건만 제거한다.
- compliant specimen에서 target rule이 나오지 않는다.

### Needs Detector

위배 코드는 명확하지만 `detected_patterns`가 target rule의 trigger와 연결되지 않으면
`needs_detector`다.

이 경우 specimen을 억지로 더 자극적으로 만들지 말고 query plugin의 `PatternSpec`,
`hinted_rules`, `direct_hint_patterns`, 또는 applicability alias를 보강한다.

### Semantic Only

코드가 위배인지 판단하려면 repository-wide context, ownership proof, runtime config, project policy가
필요한 rule은 `semantic_only`로 둔다. CI hard gate로 바로 삼지 않는다.

다만 "전 rule accountability"를 위해 specimen과 waiver는 남긴다.

### Reference Only

`reference_only` rule은 finding으로 검출되지 않는 것이 정상이다.

이 rule들은 아래를 확인한다.

- rule YAML이 로드된다.
- reference collection 또는 `inspect_rule`에서 조회된다.
- 같은 specimen을 `review_code`에 넣어도 auto finding으로 나오지 않는다.

## 7. Corpus 생성 방식

초기 생성은 자동화하되, 최종 판정은 사람이 읽을 수 있는 manifest로 남긴다.

권장 CLI:

```bash
cd /home/et16/work/review_system/review-engine
uv run python -m review_engine.cli.rule_self_test scaffold --missing-only
uv run python -m review_engine.cli.rule_self_test coverage
```

초기 scaffold 입력:

- rule YAML의 `rule_no`, `title`, `summary`, `text`, `trigger_patterns`, `fix_guidance`
- language query plugin의 `PatternSpec`
- 기존 `examples/multilang`와 `examples/multilang_safe`
- profile/context routing rule

생성 원칙:

1. violating specimen은 하나의 rule 위배를 가장 작게 드러낸다.
2. compliant specimen은 violating specimen에서 위배 조건만 고친다.
3. 한 specimen이 여러 rule을 검출해도 괜찮지만, target rule별 manifest entry는 따로 둔다.
4. 동일 fixture 파일을 여러 rule case가 공유할 수 있다. 단, 각 case의 target rule과 판정 note는 분리한다.
5. generated specimen은 commit 전에 Codex 또는 reviewer가 읽고 `judgment: accepted`로 바꾼다.

## 8. Coverage Plan

### Phase 1: Direct Detector-Backed Rules

목표:

- direct-hinted `auto_review` rule 250개를 hard gate로 만든다.
- `reference_only` 96개는 auto finding으로 나오지 않는지와 rule loadability를 확인한다.
- 현재 expected retrieval coverage 111개를 self-test manifest로 흡수하거나 cross-reference한다.

이 단계는 smoke 없이 deterministic하게 가능하다.

### Phase 2: C++ Semantic Gap

현재 direct hint가 없는 C++ auto rule 15개:

- `R.13`, `R.33`, `R.37`, `I.12`, `F.7`
- `NM.1`, `NM.2`, `NM.3`, `NM.4`
- `CPP.PROJ.1`, `CPP.PROJ.2`, `CPP.PROJ.3`, `CPP.PROJ.4`, `CPP.PROJ.5`, `CPP.PROJ.6`

이 rule들은 specimen을 먼저 만들되, hard gate는 아래 둘 중 하나를 한 뒤 켠다.

1. C++ query plugin에 rule-specific direct hint를 추가한다.
2. AST 또는 structured detector를 도입해서 regex보다 안정적인 pattern을 만든다.

retrieval similarity만으로 15개를 모두 hard gate로 삼는 것은 권장하지 않는다. rule text와 specimen
문구가 조금만 바뀌어도 rank가 흔들릴 수 있기 때문이다.

### Phase 3: Shared Rule Host-Language 적용

`SEC.*` shared auto rule은 explicit `language_id=shared` self-test로 먼저 막는다.

그 다음 별도 작업으로 host language review에서도 shared security detector가 실행되는지 검증한다.
예를 들면 Python, JavaScript, Java, Go 각각에서 hardcoded secret, shell execution, dynamic SQL
specimen을 넣고 `SEC.1` 또는 `SEC.2`가 나오는지 본다.

이 단계에서 일반 language detector와 shared detector를 함께 실행하는 runtime change가 필요할 수 있다.

## 9. 더 나은 방법

가장 좋은 방법은 "rule별 pytest 함수를 대량 생성"하는 것이 아니라 manifest-driven corpus를 두는 것이다.

이유:

- rule 추가/삭제/disable 시 coverage diff를 자동 계산할 수 있다.
- 같은 fixture를 여러 rule이 공유해도 target별 판정을 분리할 수 있다.
- generated code와 judgment note를 review 가능한 artifact로 남길 수 있다.
- `auto_review`와 `reference_only`의 기대 동작을 같은 test runner에서 다르게 처리할 수 있다.
- smoke와 달리 GitLab, DB, provider, network 없이 빠르게 실행된다.

추가로 권장하는 보강:

1. rule YAML에 self-test를 직접 넣지 말고, 별도 manifest로 시작한다.
   - rule source를 과하게 부풀리지 않고 self-test schema를 실험할 수 있다.
2. coverage baseline을 생성한다.
   - 예: `docs/baselines/review_engine/rule_self_test_coverage_YYYY-MM-DD.md`
3. false-positive decoy를 rule별로 최소 하나 둔다.
   - compliant specimen이 바로 decoy다.
4. profile/context routing도 같은 case에서 검증한다.
   - YAML CI/Kubernetes/Helm, SQL dbt/warehouse/migration, Next.js, FastAPI/Django,
     CUDA subprofile은 rule 검출보다 routing drift가 더 자주 난다.
5. regex detector가 복잡해지는 언어는 AST detector로 승격한다.
   - C++, TypeScript/JSX, Go handler validation, SQL/dbt, YAML/Kubernetes가 우선 후보다.

## 10. 최종 판단

이 self-test는 구현 가치가 높다.

현재 상태에서 곧바로 안정적으로 hard-gate할 수 있는 대상은 direct detector-backed `auto_review`
rule 250개다. 전체 `auto_review` 265개를 모두 hard-gate하려면 C++ semantic gap 15개에 detector
보강이 필요하다. 전체 rule entry 361개를 모두 accountability 대상으로 삼는 것도 가능하지만,
`reference_only` 96개는 "검출되어야 함"이 아니라 "auto finding으로 검출되면 안 됨"으로 판정해야 한다.

따라서 권장 순서는 다음이다.

1. `rule_self_tests/manifest.yaml`와 pytest runner를 먼저 만든다.
2. 기존 expected retrieval examples를 manifest에 연결한다.
3. direct-hinted auto rule부터 specimen을 채워 250개 hard gate를 목표로 한다.
4. C++ 15개와 shared host-language 적용은 detector 보강 작업으로 분리한다.
5. coverage baseline을 두고 rule 추가 시 self-test 또는 waiver가 없으면 실패하게 만든다.
