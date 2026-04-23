# Review Engine Evaluation Harness

## 목적

이 문서는 `review-engine`의 diff/code retrieval 회귀를 반복 검증하는 방법을 정리한다.

## 현재 자산

- retrieval 예제:
  - `review-engine/examples/expected_retrieval_examples.json`
- C++ diff contract 예제:
  - `review-engine/examples/cpp_diff_contracts.json`
- diff contract 예제 파일:
  - `review-engine/examples/*_diffs/*.diff`
- smoke fixture contract:
  - `ops/fixtures/review_smoke/*/expected_smoke.json`
  - `ops/fixtures/review_smoke/*/{base,feature}/`
  - `expected_engine_rules` entries for fixture-level retrieval expectations

현재 shipped corpus는 repo-local generic/multilang fixture만 기준으로 유지한다.
legacy organization-specific fixture는 evaluation contract에서 제거된 상태를 기준선으로 본다.

## 실행 명령

retrieval 예제:

```bash
uv run --project review-engine python -m review_engine.cli.evaluate_examples
```

C++ diff contract 예제:

```bash
uv run --project review-engine python -m review_engine.cli.evaluate_diff_contracts
```

테스트:

```bash
uv run --project review-engine pytest review-engine/tests -q
```

smoke fixture contract만 빠르게 볼 때:

```bash
cd review-engine && uv run pytest tests/test_smoke_fixture_contracts.py -q
```

## Corpus 확장 규칙

1. positive example은 실제 기대 rule이 왜 필요한지 설명 가능한 diff만 추가한다.
2. negative example은 false positive hotspot을 줄이는 목적일 때만 추가한다.
3. 한 rule family를 바꾸면 대응 positive/negative 예제를 같이 갱신한다.
4. shipped example/contract corpus에는 organization-specific legacy fixture를 다시 넣지 않는다.
5. local GitLab smoke fixture는 `base/`, `feature/`, `expected_smoke.json`을 함께 갱신한다.
6. 외부-derived fixture는 smoke 실행 중 live fetch하지 않고 pinned manifest를 먼저 남긴다.

## 권장 운영

- rule 변경 PR에는 최소 `evaluate_diff_contracts`를 한 번 실행한다.
- release 전에는 전체 `pytest`와 `evaluate_examples`, `evaluate_diff_contracts`를 함께 실행한다.
