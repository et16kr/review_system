#!/usr/bin/env bash
set -euo pipefail

ROOT="${REVIEW_SYSTEM_ROOT:-/home/et16/work/review_system}"
REVIEW_ROADMAP_FILE="${REVIEW_ROADMAP_FILE:-docs/REVIEW_ROADMAP.md}"

export COMMIT_PREFIX="${COMMIT_PREFIX:-Advance review roadmap item}"

exec "$ROOT/ops/scripts/advance_roadmap_with_codex.sh" \
  --roadmap-file "$REVIEW_ROADMAP_FILE" \
  "$@"
