#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="${REVIEW_SYSTEM_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd -P)}"
MODE="all"
UV_CACHE_DIR_VALUE="${UV_CACHE_DIR:-/tmp/uv-cache}"
PACKAGE_ROOT="${REVIEW_ENGINE_EXTENSION_PACKAGE_ROOT:-$ROOT/review-engine/examples/extensions/private_org_cpp}"
PRIVATE_ARTIFACT_ROOT="${REVIEW_ENGINE_PRIVATE_ARTIFACT_ROOT:-/tmp/review-engine-private-rule-packages}"

usage() {
  cat <<'EOF'
Usage: ops/scripts/run_review_engine_extension_ci.sh [--mode MODE]

Run the deterministic review-engine extension release gate in split paths:
- public-only: public core runtime/loader coverage without the repo sample private root
- private-enabled: private package split validation and repo sample private extension root coverage
- all: run both paths in order

Environment overrides:
- REVIEW_SYSTEM_ROOT: repository root
- UV_CACHE_DIR: uv cache directory (default: /tmp/uv-cache)
- REVIEW_ENGINE_EXTENSION_PACKAGE_ROOT: private package root for split validation
- REVIEW_ENGINE_PRIVATE_ARTIFACT_ROOT: base directory for private validation artifacts
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:?missing value for --mode}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

case "$MODE" in
  public-only|private-enabled|all)
    ;;
  *)
    echo "Unsupported mode: $MODE" >&2
    usage >&2
    exit 1
    ;;
esac

cd "$ROOT"

run_public_only() {
  env UV_CACHE_DIR="$UV_CACHE_DIR_VALUE" \
    uv run --project review-engine pytest \
      review-engine/tests/test_rule_runtime.py \
      review-engine/tests/test_source_coverage_matrix.py \
      -q
}

run_private_enabled() {
  env UV_CACHE_DIR="$UV_CACHE_DIR_VALUE" \
    uv run --project review-engine python -m review_engine.cli.rule_package split-gate \
      --package-root "$PACKAGE_ROOT" \
      --private-artifact-root "$PRIVATE_ARTIFACT_ROOT"

  env UV_CACHE_DIR="$UV_CACHE_DIR_VALUE" \
    uv run --project review-engine pytest review-engine/tests/test_rule_runtime_private_extension.py -q
}

if [[ "$MODE" == "public-only" || "$MODE" == "all" ]]; then
  run_public_only
fi

if [[ "$MODE" == "private-enabled" || "$MODE" == "all" ]]; then
  run_private_enabled
fi
